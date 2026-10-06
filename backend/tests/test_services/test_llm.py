"""Test cổng LLM: dựng prompt, parse JSON, chọn nhà cung cấp, báo lỗi thiếu khóa bằng tiếng Việt."""

import pytest

from src.config import Settings
from src.services.cost import compute_cost_usd, estimate_cost_usd
from src.services.llm import (
    LLMConfigError,
    LLMOutputError,
    LLMRequest,
    OpenAIProvider,
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
    assert settings.model_for("planner") == settings.model_for("codegen") == "gpt-5.6-luna"
    assert settings.model_for("optimizer") == "gpt-5.6-terra"
    assert settings.model_for("codegen", "google") == "gemini-3.1-flash-lite"
    assert "optimizer=gpt-5.6-terra" in settings.models_summary


def test_model_override_for_one_task():
    settings = Settings(llm_provider="openai", model_testgen="gpt-5.6-terra", **KEYS)
    assert settings.model_for("testgen") == "gpt-5.6-terra" and settings.model_for("planner") == "gpt-5.6-luna"


def test_get_provider_wraps_fallback_and_uses_task_model():
    from src.services.llm import FallbackProvider

    provider = get_provider(Settings(llm_provider="openai", llm_fallback="google", **KEYS), task="optimizer")
    assert isinstance(provider, FallbackProvider) and provider.primary.model == "gpt-5.6-terra"
    plain = get_provider(Settings(llm_provider="openai", llm_fallback="none", **KEYS), task="codegen")
    assert isinstance(plain, OpenAIProvider) and plain.model == "gpt-5.6-luna"


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
    assert estimate_cost_usd("gpt-5.6-luna", 1_000_000, 1_000_000) == pytest.approx(1.40)
    assert estimate_cost_usd("gpt-5.6-terra", 1_000_000, 1_000_000) == pytest.approx(14.00)
    assert estimate_cost_usd("gemini-3.1-flash-lite", 1_000_000, 1_000_000) == pytest.approx(1.75)


def test_openai_length_error_becomes_call_error_for_fallback(monkeypatch):
    """gpt-5.6-luna có thể dùng hết token cho suy luận ẩn → LengthFinishReasonError phải thành LLMCallError (dự phòng)."""
    import openai

    from src.services.llm import LLMCallError

    provider = OpenAIProvider(Settings(llm_provider="openai", **KEYS), "gpt-5.6-luna")

    class Boom:
        def invoke(self, messages):
            raise openai.OpenAIError("length limit reached")

    provider.client = Boom()
    with pytest.raises(LLMCallError):
        provider.complete(LLMRequest(task="planner", variables={}), ("", ""))
