"""J1 Hỏi làm rõ: graph tạm dừng, chờ con người chọn đáp án cho từng câu hỏi trắc nghiệm."""

from langgraph.types import interrupt

from src.agents.state import PipelineState
from src.models.spec import ClarifyQuestion


def valid_answers(questions: list[ClarifyQuestion], reply: object) -> dict[str, str]:
    """Chỉ giữ câu trả lời đúng id câu hỏi và nằm trong danh sách lựa chọn."""
    answers = reply.get("answers", {}) if isinstance(reply, dict) else {}
    options = {q.id: q.options for q in questions}
    return {qid: value for qid, value in answers.items() if value in options.get(qid, [])}


def clarify_node(state: PipelineState) -> dict:
    """Tạm dừng (interrupt) để hỏi; khi tiếp tục, gộp câu trả lời hợp lệ vào `answers`."""
    spec = state.get("spec", {})
    questions = [ClarifyQuestion.model_validate(q) for q in spec.get("questions", [])]
    reply = interrupt(
        {
            "kind": "clarify",
            "unknowns": spec.get("unknowns", []),
            "questions": [q.model_dump() for q in questions],
        }
    )
    chosen = valid_answers(questions, reply)
    answered = [{"id": q.id, "question": q.question, "answer": chosen[q.id]} for q in questions if q.id in chosen]
    return {
        "answers": {**state.get("answers", {}), **chosen},
        "answered": [*state.get("answered", []), *answered],
    }
