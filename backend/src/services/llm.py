"""Cổng gọi LLM duy nhất của hệ thống: `openai`, `google` hoặc `mock` (LLM_PROVIDER); dự phòng Gemini (LLM_FALLBACK).

Mọi node gọi `call_llm(task, variables)`; prompt nằm ở `src/prompts/<task>.md`.
"""

import json
import logging
import re
import time
from pathlib import Path
from string import Template
from typing import Protocol

from pydantic import BaseModel

from src.config import Settings, get_settings
from src.models.schemas import LLMUsage
from src.services.cost import estimate_cost_usd

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
USER_MARKER = "<!-- USER -->"


class LLMConfigError(RuntimeError):
    """Cấu hình LLM chưa đủ (ví dụ thiếu khóa). Thông báo bằng tiếng Việt."""


class LLMCallError(RuntimeError):
    """Gọi LLM thất bại (mạng, hết hạn mức, ...)."""


class LLMOutputError(ValueError):
    """LLM trả về nội dung không đúng định dạng JSON yêu cầu."""


class LLMRequest(BaseModel):
    """Yêu cầu gọi LLM: tên tác vụ + biến điền vào prompt."""

    task: str
    variables: dict[str, str]


class LLMResponse(BaseModel):
    """Kết quả: văn bản trả về + thống kê token/chi phí."""

    text: str
    usage: LLMUsage


class LLMProvider(Protocol):
    """Giao diện chung cho mọi nhà cung cấp."""

    def complete(self, request: LLMRequest, prompt: tuple[str, str]) -> LLMResponse:
        """Gọi mô hình với (system, user) đã dựng sẵn."""
        ...


def _is_gpt6_reasoning_model(model: str) -> bool:
    """Nhận diện GPT-6 và các biến thể có reasoning effort trong API hiện tại."""
    return re.match(r"^gpt-6(?:\.\d+)?(?:-|$)", model.strip(), re.IGNORECASE) is not None


def _openai_client_options(settings: Settings, model: str) -> dict:
    """Tạo tham số tương thích với endpoint Chat Completions cho model đã chọn."""
    options = {
        "model": model,
        "api_key": settings.openai_api_key,
        "max_completion_tokens": settings.llm_max_tokens,
        "timeout": 120,
        "max_retries": 2,
    }
    if _is_gpt6_reasoning_model(model):
        # GPT-6 từ chối temperature/top_p khi reasoning đang bật.
        options["reasoning_effort"] = settings.llm_reasoning_effort
    else:
        options["temperature"] = settings.llm_temperature
    return options


def _openai_error_summary(exc: Exception, model: str) -> str:
    """Tóm tắt lỗi OpenAI cho người dùng mà không đưa message/body có thể chứa dữ liệu vào log/UI."""
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    detail = body.get("error", body) if isinstance(body, dict) else {}
    detail = detail if isinstance(detail, dict) else {}
    code = detail.get("code") or getattr(exc, "code", None)
    param = detail.get("param") or getattr(exc, "param", None)
    api_message = detail.get("message", "")
    api_message = api_message.lower() if isinstance(api_message, str) else ""

    def safe_field(value: object) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.\[\]-]{1,100}", value):
            return ""
        return value

    code, param = safe_field(code), safe_field(param)
    if status == 401:
        cause = "Xác thực OpenAI thất bại; kiểm tra API key và project đang dùng."
    elif status == 403:
        cause = f"Project/API key không có quyền gọi model '{model}'."
    elif code == "model_not_found" or status == 404:
        if "does not exist" in api_message and "do not have access" not in api_message:
            cause = f"Model '{model}' không tồn tại hoặc sai tên."
        elif "do not have access" in api_message and "does not exist" not in api_message:
            cause = f"Project/API key chưa được cấp quyền dùng model '{model}'."
        else:
            cause = f"Không tìm thấy model '{model}' hoặc project chưa được cấp quyền truy cập model này."
    elif status == 400:
        field = f" Tham số: {param}." if param else ""
        api_code = f" Mã: {code}." if code else ""
        cause = f"Request OpenAI có tham số không hợp lệ hoặc không được model hỗ trợ.{field}{api_code}"
    elif status == 429 and code in {
        "insufficient_quota",
        "credit_balance_exhausted",
        "organization_spend_limit_exceeded",
        "project_spend_limit_exceeded",
        "organization_usage_limit_exceeded",
    }:
        cause = "OpenAI đã hết quota/credit hoặc chạm giới hạn chi tiêu; kiểm tra billing và usage limit."
    elif status == 429:
        cause = "OpenAI đang giới hạn tốc độ request; chờ rồi thử lại hoặc kiểm tra rate limit."
    elif type(exc).__name__ == "APITimeoutError":
        cause = "Request OpenAI hết thời gian chờ; kiểm tra kết nối mạng rồi thử lại."
    elif type(exc).__name__ == "APIConnectionError" or status is None:
        cause = "Không kết nối được tới OpenAI; kiểm tra mạng, DNS, firewall và thử lại."
    elif isinstance(status, int) and status >= 500:
        cause = f"OpenAI tạm thời gặp lỗi máy chủ (HTTP {status}); thử lại sau."
    else:
        cause = "OpenAI từ chối request hoặc gặp lỗi chưa phân loại; kiểm tra cấu hình model và log mã lỗi."

    metadata = [f"HTTP {status}" if isinstance(status, int) else "không có HTTP status"]
    if code:
        metadata.append(f"code={code}")
    if param:
        metadata.append(f"param={param}")
    return f"{cause} ({', '.join(metadata)})."


def render_prompt(request: LLMRequest) -> tuple[str, str]:
    """Đọc `src/prompts/<task>.md`, điền biến `$ten_bien`, tách phần system và user."""
    path = PROMPTS_DIR / f"{request.task}.md"
    if not path.exists():
        raise LLMConfigError(f"Không tìm thấy prompt cho tác vụ '{request.task}' ({path}).")
    text = Template(path.read_text(encoding="utf-8")).safe_substitute(request.variables)
    system, _, user = text.partition(USER_MARKER)
    return system.strip(), user.strip()


class UsageInfo(BaseModel):
    """Số liệu một lần gọi để dựng LLMUsage."""

    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    started: float


def _usage(request: LLMRequest, info: UsageInfo) -> LLMUsage:
    return LLMUsage(
        task=request.task,
        provider=info.provider,
        model=info.model,
        input_tokens=info.input_tokens,
        output_tokens=info.output_tokens,
        cost_usd=estimate_cost_usd(info.model, info.input_tokens, info.output_tokens),
        latency_ms=round((time.perf_counter() - info.started) * 1000, 1),
    )


def _response(request: LLMRequest, message: object, info: UsageInfo) -> LLMResponse:
    """Dựng kết quả từ tin nhắn LangChain (`.text` gộp mọi khối văn bản, đúng cho cả OpenAI lẫn Gemini)."""
    meta = getattr(message, "usage_metadata", None) or {}
    info = info.model_copy(
        update={"input_tokens": meta.get("input_tokens", 0), "output_tokens": meta.get("output_tokens", 0)}
    )
    return LLMResponse(text=str(getattr(message, "text", "")), usage=_usage(request, info))


class OpenAIProvider:
    """Gọi OpenAI qua langchain-openai, ép đầu ra JSON. Mỗi bước có thể dùng model riêng."""

    def __init__(self, settings: Settings, model: str = "") -> None:
        if not settings.has_openai_key:
            raise LLMConfigError(
                "Bạn đang chọn LLM_PROVIDER=openai nhưng chưa có OPENAI_API_KEY. "
                "Mở file .env, điền OPENAI_API_KEY=<khóa của bạn>, hoặc đổi LLM_PROVIDER=mock để chạy mô phỏng."
            )
        from langchain_openai import ChatOpenAI

        self.model = model or settings.model_name
        client = ChatOpenAI(**_openai_client_options(settings, self.model))
        self.client = client.bind(response_format={"type": "json_object"})

    def complete(self, request: LLMRequest, prompt: tuple[str, str]) -> LLMResponse:
        """Gọi OpenAI và ghi lại token/chi phí ước tính."""
        import openai

        info = UsageInfo(
            provider="openai", model=self.model, input_tokens=0, output_tokens=0, started=time.perf_counter()
        )
        try:
            message = self.client.invoke([("system", prompt[0]), ("human", prompt[1])])
        except openai.OpenAIError as exc:  # gồm cả lỗi API và LengthFinishReasonError
            status = getattr(exc, "status_code", None)
            body = getattr(exc, "body", None)
            details = body.get("error", body) if isinstance(body, dict) else {}
            details = details if isinstance(details, dict) else {}
            code = details.get("code") or getattr(exc, "code", None)
            param = details.get("param") or getattr(exc, "param", None)
            logger.warning(
                "OpenAI request failed",
                extra={
                    "task": request.task,
                    "model": self.model,
                    "status": status,
                    "code": code if isinstance(code, str) else "",
                    "param": param if isinstance(param, str) else "",
                    "error_type": type(exc).__name__,
                },
            )
            raise LLMCallError(_openai_error_summary(exc, self.model)) from None
        return _response(request, message, info)


class GoogleProvider:
    """Gọi Google Gemini qua langchain-google-genai, ép đầu ra JSON."""

    def __init__(self, settings: Settings, model: str = "") -> None:
        if not settings.has_google_key:
            raise LLMConfigError(
                "Cần GOOGLE_API_KEY để dùng Gemini (LLM_PROVIDER=google hoặc dự phòng LLM_FALLBACK=google). "
                "Tạo khóa ở Google AI Studio rồi tự điền GOOGLE_API_KEY=<khóa> vào .env, hoặc đặt LLM_FALLBACK=none."
            )
        from langchain_google_genai import ChatGoogleGenerativeAI

        self.model = model or settings.google_model_name
        self.client = ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=settings.google_api_key,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=120,
            max_retries=2,
            response_mime_type="application/json",
        )

    def complete(self, request: LLMRequest, prompt: tuple[str, str]) -> LLMResponse:
        """Gọi Gemini và ghi lại token/chi phí ước tính."""
        from google.genai.errors import APIError
        from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError

        info = UsageInfo(
            provider="google", model=self.model, input_tokens=0, output_tokens=0, started=time.perf_counter()
        )
        try:
            message = self.client.invoke([("system", prompt[0]), ("human", prompt[1])])
        except (ChatGoogleGenerativeAIError, APIError) as exc:
            raise LLMCallError(f"Gọi Gemini thất bại ({type(exc).__name__}). Kiểm tra khóa, mạng và hạn mức.") from exc
        return _response(request, message, info)


class FallbackProvider:
    """Gọi nhà cung cấp chính; chỉ khi GỌI THẤT BẠI (mạng, hạn mức, model lỗi) mới chuyển sang dự phòng.

    Câu trả lời sai định dạng KHÔNG chuyển dự phòng (các node đã tự xử lý). Dự phòng chỉ dựng khi cần.
    """

    def __init__(self, primary: LLMProvider, settings: Settings) -> None:
        self.primary, self.settings = primary, settings

    def complete(self, request: LLMRequest, prompt: tuple[str, str]) -> LLMResponse:
        """Gọi chính, lỗi thì gọi Gemini; `usage.provider/model` ghi đúng bên đã trả lời."""
        try:
            return self.primary.complete(request, prompt)
        except LLMCallError as exc:
            logger.warning("llm primary failed, using fallback", extra={"task": request.task, "error": str(exc)})
            try:
                backup = GoogleProvider(self.settings)
            except LLMConfigError as config_exc:
                raise LLMCallError(f"{exc} Không dùng được dự phòng Gemini: {config_exc}") from exc
            return backup.complete(request, prompt)


def get_provider(settings: Settings | None = None, task: str = "") -> LLMProvider:
    """Chọn nhà cung cấp theo LLM_PROVIDER và model theo từng bước; bọc dự phòng nếu LLM_FALLBACK=google."""
    settings = settings or get_settings()
    if settings.llm_provider == "google":
        return GoogleProvider(settings, settings.model_for(task, "google"))
    if settings.llm_provider == "openai":
        primary = OpenAIProvider(settings, settings.model_for(task, "openai"))
        return FallbackProvider(primary, settings) if settings.llm_fallback == "google" else primary
    from src.services.llm_mock import MockProvider

    return MockProvider()


def call_llm(task: str, variables: dict[str, str]) -> LLMResponse:
    """Dựng prompt cho `task` và gọi nhà cung cấp hiện tại."""
    request = LLMRequest(task=task, variables=variables)
    response = get_provider(task=task).complete(request, render_prompt(request))
    logger.info("llm call", extra=response.usage.model_dump())
    return response


def parse_json_output(text: str) -> dict:
    """Lấy object JSON từ câu trả lời (chấp nhận khối ```json ... ```)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text[text.find("{") : text.rfind("}") + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"LLM không trả về JSON hợp lệ: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise LLMOutputError("LLM phải trả về một object JSON.")
    return data


def to_json(value: object) -> str:
    """Chuyển dữ liệu thành JSON gọn để chèn vào prompt."""
    return json.dumps(value, ensure_ascii=False, indent=1, default=str)
