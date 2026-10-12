"""Kiểm thử OpenAI thật: chạy bằng `pytest -m network -s` với OPENAI_API_KEY được nạp an toàn."""

import json

import openai
import pytest
from dotenv import dotenv_values
from openai import OpenAI

from src.config import Settings, is_real_secret
from src.services.llm import LLMRequest, OpenAIProvider, parse_json_output

pytestmark = pytest.mark.network


def _settings_or_skip() -> Settings:
    # conftest.py deliberately clears process env keys for every test. Live tests
    # are explicit opt-in, so read only the ignored local backend/.env file.
    api_key = dotenv_values(".env").get("OPENAI_API_KEY", "") or ""
    if not is_real_secret(api_key):
        pytest.skip("Cần OPENAI_API_KEY trong môi trường test để gửi request OpenAI thật.")
    return Settings(llm_provider="openai", openai_api_key=api_key, llm_max_tokens=256)


def _safe_error_fields(exc: openai.OpenAIError, api_key: str) -> dict:
    """Chỉ in bốn trường lỗi yêu cầu; che khóa nếu API bất ngờ đưa nó vào message."""
    body = getattr(exc, "body", None)
    error = body.get("error", body) if isinstance(body, dict) else {}
    error = error if isinstance(error, dict) else {}
    message = error.get("message", "")
    if not isinstance(message, str):
        message = ""
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    for test_input in ("Return a JSON object containing only ok=true.", "Return only {\"ok\":true}."):
        message = message.replace(test_input, "[TEST INPUT]")
    return {
        "http_status": getattr(exc, "status_code", None),
        "error_code": error.get("code"),
        "param": error.get("param"),
        "message": message,
    }


def test_reproduce_original_gpt6_temperature_request_error():
    """Tái hiện request cũ với temperature=0 khi GPT-6 reasoning=medium."""
    settings = _settings_or_skip()
    client = OpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=0)
    try:
        client.chat.completions.create(
            model="gpt-6-luna",
            messages=[
                {"role": "system", "content": "Return a JSON object containing only ok=true."},
                {"role": "user", "content": "Return only {\"ok\":true}."},
            ],
            reasoning_effort="medium",
            temperature=0.0,
            max_completion_tokens=256,
            response_format={"type": "json_object"},
        )
    except openai.BadRequestError as exc:
        fields = _safe_error_fields(exc, settings.openai_api_key)
        print("Original request diagnostic: " + json.dumps(fields, ensure_ascii=False))
        assert fields["http_status"] == 400
        assert fields["param"] == "temperature"
    except openai.OpenAIError as exc:
        fields = _safe_error_fields(exc, settings.openai_api_key)
        pytest.fail(
            "Original request returned an unexpected OpenAI error: "
            + json.dumps(fields, ensure_ascii=False)
        )
    else:
        pytest.fail("The old GPT-6 request unexpectedly accepted temperature=0 with reasoning enabled.")


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6.1-sol"])
def test_gpt6_model_returns_valid_json_from_real_openai_request(model):
    settings = _settings_or_skip()
    provider = OpenAIProvider(settings, model)
    response = provider.complete(
        LLMRequest(task="planner", variables={}),
        (
            "Return exactly one JSON object with the boolean key ok set to true.",
            "Return only {\"ok\":true}.",
        ),
    )
    assert parse_json_output(response.text) == {"ok": True}
    print(f"Live OpenAI request succeeded: model={model}, valid_json=true")
