"""E1 Planner: yêu cầu NL + danh mục nguồn thật → PipelineSpec (LLM rút thông tin, code quyết định mode)."""

import logging
import re

from pydantic import ValidationError

from src.agents.nodes.common import usage_of
from src.agents.state import PipelineState
from src.agents.tools.duckdb_tools import discover_sources
from src.config import get_settings
from src.models.schemas import RunStatus
from src.models.spec import ModeSignals, PipelineSpec, decide_mode, signals_from_sources
from src.services.llm import LLMOutputError, call_llm, parse_json_output, to_json

logger = logging.getLogger(__name__)


def _key(text: str) -> str:
    return re.sub(r"[\W_]+", " ", str(text)).strip().lower()


def drop_answered(data: dict, answered: list[dict]) -> dict:
    """Bỏ câu hỏi/điểm chưa rõ TRÙNG NGUYÊN VĂN câu người dùng đã trả lời; ghi câu trả lời vào giả định.

    LLM thật đôi khi hỏi lại y hệt câu đã trả lời; con người đã quyết định nên code không hỏi lại lần nữa.
    """
    done = {_key(item["question"]): f"{item['question']} → {item['answer']}" for item in answered}
    if not done:
        return data
    questions = [q for q in data.get("questions") or [] if _key(q.get("question", "")) not in done]
    unknowns = [u for u in data.get("unknowns") or [] if _key(u) not in done]
    assumptions = list(dict.fromkeys([*(data.get("assumptions") or []), *done.values()]))
    return {**data, "questions": questions, "unknowns": unknowns, "assumptions": assumptions}


def build_spec(data: dict, request_text: str, answers: dict[str, str]) -> PipelineSpec:
    """Dựng spec từ JSON của LLM; tín hiệu loại nguồn và `mode` do code tính lại."""
    spec = PipelineSpec.model_validate({**data, "request_text": request_text, "decisions": answers})
    signals = signals_from_sources(spec.sources, ModeSignals.model_validate(data.get("signals") or {}))
    mode, reason = decide_mode(signals)
    return spec.model_copy(update={"signals": signals, "mode": mode, "mode_reason": reason})


def _catalog(state: PipelineState) -> list[dict]:
    if state.get("source_catalog"):
        return state["source_catalog"]
    return [info.model_dump() for info in discover_sources(get_settings().sources_dir)]


def planner_node(state: PipelineState) -> dict:
    """Gọi LLM lập đặc tả; lỗi định dạng được trả về `spec_errors` để V0 cho làm lại."""
    catalog = _catalog(state)
    rounds = state.get("plan_rounds", 0) + 1
    if not catalog:
        return {
            "status": RunStatus.FAILED.value,
            "error": "Chưa có nguồn dữ liệu trong data/sources. Chạy: python -m src.cli seed",
        }
    answers = state.get("answers", {})
    last_round = rounds >= get_settings().max_plan_rounds
    response = call_llm(
        "planner",
        {
            "request_text": state["request_text"],
            "source_catalog": to_json(catalog),
            "answers": to_json(answers) if answers else "(chưa có)",
            "answered_questions": to_json(state.get("answered", [])) if state.get("answered") else "(chưa có)",
            "spec_errors": to_json(state.get("spec_errors", [])),
            "plan_feedback": to_json(state.get("plan_feedback", [])) if state.get("plan_feedback") else "(chưa có)",
            "round_note": "ĐÂY LÀ LƯỢT CUỐI: không được hỏi thêm." if last_round else "(chưa phải lượt cuối)",
        },
    )
    base = {"source_catalog": catalog, "plan_rounds": rounds, "llm_usage": usage_of(response)}
    try:
        data = drop_answered(parse_json_output(response.text), state.get("answered", []))
        spec = build_spec(data, state["request_text"], answers)
    except (LLMOutputError, ValidationError) as exc:
        logger.warning("planner output invalid", extra={"error": str(exc)[:300]})
        return {**base, "spec": {}, "spec_errors": [f"Planner trả về đặc tả sai định dạng: {str(exc)[:200]}"]}
    return {**base, "spec": spec.model_dump(mode="json")}
