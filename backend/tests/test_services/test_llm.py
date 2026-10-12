"""Test cổng LLM: dựng prompt, parse JSON, chọn nhà cung cấp, báo lỗi thiếu khóa bằng tiếng Việt."""

import pytest

from src.config import Settings
from src.services.cost import compute_cost_usd, estimate_cost_usd
from src.services.llm import (
    LLMConfigError,
    LLMOutputError,
    LLMRequest,
    OpenAIProvider,
    _openai_client_options,
    _openai_error_summary,
    call_llm,
    get_provider,
    parse_json_output,
    render_prompt,
)
from src.services.llm_mock import MockProvider


def test_render_prompt_splits_system_and_user_and_fills_variables():
    system, user = render_prompt(LLMRequest(task="planner", variables={"request_text": "doanh thu ngày"}))
    assert "Planner" in system
    assert "doanh thu ngày" in user
    assert '<data name="request">' in user


def test_render_prompt_unknown_task_raises():
    with pytest.raises(LLMConfigError):
        render_prompt(LLMRequest(task="khong-co", variables={}))


@pytest.mark.parametrize(
    "text",
    ['{"a": 1}', 'Kết quả:\n```json\n{"a": 1}\n```', 'trước {"a": 1} sau'],
)
def test_parse_json_output_accepts_common_formats(text):
    assert parse_json_output(text) == {"a": 1}


@pytest.mark.parametrize("text", ["không có json", "[1, 2]", "{sai"])
def test_parse_json_output_rejects_invalid(text):
    with pytest.raises(LLMOutputError):
        parse_json_output(text)


def test_default_provider_is_mock_and_marks_simulated():
    assert isinstance(get_provider(), MockProvider)
    response = call_llm("planner", {"request_text": "x", "source_catalog": "[]", "answers": "(chưa có)"})
    assert response.usage.simulated is True
    assert response.usage.cost_usd == 0


@pytest.mark.parametrize("key", ["", "sk-your-key-here"])
def test_openai_without_real_key_gives_vietnamese_instruction(key):
    settings = Settings(llm_provider="openai", openai_api_key=key)
    with pytest.raises(LLMConfigError, match="OPENAI_API_KEY"):
        OpenAIProvider(settings)


def test_unknown_mock_task_returns_empty_object():
    response = MockProvider().complete(LLMRequest(task="khac", variables={}), ("", ""))
    assert response.text == "{}"


def test_cost_estimates():
    assert estimate_cost_usd("gpt-4o-mini", 1_000_000, 1_000_000) == pytest.approx(0.75)
    assert estimate_cost_usd("model-la", 1000, 1000) == 0.0
    assert compute_cost_usd(3600, 0.5) == pytest.approx(0.5)


# ---- Hướng C: model theo từng bước + dự phòng Gemini (không gọi mạng) ----

KEYS = {"openai_api_key": "sk-test-123", "google_api_key": "AIza-test-123"}


def test_model_per_task_defaults():
    settings = Settings(llm_provider="openai", **KEYS)
    assert settings.model_for("planner") == settings.model_for("codegen") == "gpt-6-luna"
    assert settings.model_for("testgen") == "gpt-6-luna"
    assert settings.model_for("optimizer") == "gpt-6.1-sol"
    assert settings.model_for("codegen", "google") == "gemini-3.1-flash-lite"
    assert "optimizer=gpt-6.1-sol" in settings.models_summary


def test_model_override_for_one_task():
    settings = Settings(llm_provider="openai", model_testgen="gpt-6.1-sol", **KEYS)
    assert settings.model_for("testgen") == "gpt-6.1-sol" and settings.model_for("planner") == "gpt-6-luna"


def test_get_provider_wraps_fallback_and_uses_task_model():
    from src.services.llm import FallbackProvider

    provider = get_provider(Settings(llm_provider="openai", llm_fallback="google", **KEYS), task="optimizer")
    assert isinstance(provider, FallbackProvider) and provider.primary.model == "gpt-6.1-sol"
    plain = get_provider(Settings(llm_provider="openai", llm_fallback="none", **KEYS), task="codegen")
    assert isinstance(plain, OpenAIProvider) and plain.model == "gpt-6-luna"


class _Failing:
    def complete(self, request: LLMRequest, prompt: tuple[str, str]):
        from src.services.llm import LLMCallError

        raise LLMCallError("Gọi OpenAI thất bại (RateLimitError).")


def test_fallback_switches_to_gemini_only_on_call_error(monkeypatch):
    from src.services import llm

    class FakeGoogle:
        def __init__(self, settings: Settings, model: str = "") -> None:
            self.model = model or settings.google_model_name

        def complete(self, request: LLMRequest, prompt: tuple[str, str]):
            return MockProvider().complete(request, prompt).model_copy(update={"text": '{"from": "gemini"}'})

    monkeypatch.setattr(llm, "GoogleProvider", FakeGoogle)
    provider = llm.FallbackProvider(_Failing(), Settings(llm_provider="openai", **KEYS))
    response = provider.complete(LLMRequest(task="planner", variables={}), ("", ""))
    assert response.text == '{"from": "gemini"}'


def test_fallback_without_google_key_reports_both_errors():
    from src.services.llm import FallbackProvider, LLMCallError

    provider = FallbackProvider(_Failing(), Settings(llm_provider="openai", openai_api_key="sk-test-123"))
    with pytest.raises(LLMCallError, match="RateLimitError.*GOOGLE_API_KEY"):
        provider.complete(LLMRequest(task="planner", variables={}), ("", ""))


def test_google_provider_without_key_gives_vietnamese_instruction():
    from src.services.llm import GoogleProvider

    with pytest.raises(LLMConfigError, match="GOOGLE_API_KEY"):
        GoogleProvider(Settings(llm_provider="google", google_api_key=""))


def test_new_model_prices():
    assert estimate_cost_usd("gpt-6-luna", 1_000_000, 1_000_000) == pytest.approx(0.60)
    assert estimate_cost_usd("gpt-6.1-sol", 1_000_000, 1_000_000) == pytest.approx(12.00)
    assert estimate_cost_usd("gpt-5.6-luna", 1_000_000, 1_000_000) == pytest.approx(1.40)
    assert estimate_cost_usd("gpt-5.6-terra", 1_000_000, 1_000_000) == pytest.approx(14.00)
    assert estimate_cost_usd("gemini-3.1-flash-lite", 1_000_000, 1_000_000) == pytest.approx(1.75)


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6.1-sol"])
def test_gpt6_chat_completion_payload_uses_reasoning_and_json_without_temperature(model):
    from langchain_core.messages import HumanMessage, SystemMessage

    settings = Settings(llm_provider="openai", llm_temperature=0.0, llm_reasoning_effort="medium", **KEYS)
    provider = OpenAIProvider(settings, model)
    chat = provider.client.bound
    payload = chat._get_request_payload(
        [SystemMessage(content="Return a JSON object."), HumanMessage(content="Return {\"ok\":true}.")],
        **provider.client.kwargs,
    )

    assert payload["model"] == model
    assert payload["reasoning_effort"] == "medium"
    assert "temperature" not in payload
    assert payload["max_completion_tokens"] == settings.llm_max_tokens
    assert payload["response_format"] == {"type": "json_object"}


def test_non_gpt6_chat_model_keeps_configured_temperature():
    options = _openai_client_options(Settings(llm_provider="openai", **KEYS), "gpt-4.1")
    assert options["temperature"] == 0.0
    assert "reasoning_effort" not in options


@pytest.mark.parametrize(
    ("status", "code", "param", "expected"),
    [
        (400, "unsupported_parameter", "temperature", "tham số không hợp lệ"),
        (401, "invalid_api_key", None, "xác thực OpenAI thất bại"),
        (403, "model_not_found", None, "không có quyền"),
        (404, "model_not_found", None, "Không tìm thấy model"),
        (429, "rate_limit_exceeded", None, "giới hạn tốc độ"),
        (429, "insufficient_quota", None, "hết quota/credit"),
        (None, None, None, "Không kết nối được"),
    ],
)
def test_openai_error_summary_classifies_failure_without_raw_api_message(status, code, param, expected):
    from types import SimpleNamespace

    error = SimpleNamespace(
        status_code=status,
        body={"error": {"code": code, "param": param, "message": "provider detail with private input"}},
    )
    summary = _openai_error_summary(error, "gpt-6-luna")
    assert expected.lower() in summary.lower()
    assert "private input" not in summary
    if status:
        assert f"HTTP {status}" in summary
    if code:
        assert f"code={code}" in summary
    if param:
        assert f"param={param}" in summary


def test_openai_length_error_becomes_call_error_for_fallback(monkeypatch):
    """GPT-6 Luna hết token suy luận → LengthFinishReasonError phải thành LLMCallError (dự phòng)."""
    import openai

    from src.services.llm import LLMCallError

    provider = OpenAIProvider(Settings(llm_provider="openai", **KEYS), "gpt-6-luna")

    class Boom:
        def invoke(self, messages):
            raise openai.OpenAIError("length limit reached")

    provider.client = Boom()
    with pytest.raises(LLMCallError):
        provider.complete(LLMRequest(task="planner", variables={}), ("", ""))
