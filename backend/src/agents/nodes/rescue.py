"""Cứu hộ (J): sau 3 lần sửa thất bại hoặc cùng một lỗi lặp 2 lần, con người đưa gợi ý hoặc dừng."""

from langgraph.types import interrupt

from src.agents.nodes.codegen import last_error
from src.agents.state import PipelineState
from src.models.schemas import RunStatus


def rescue_node(state: PipelineState) -> dict:
    """Tạm dừng chờ con người: `{"action": "retry", "hint": "..."}` hoặc `{"action": "abort"}`."""
    reply = interrupt(
        {
            "kind": "rescue",
            "error": last_error(state),
            "fix_attempts": state.get("fix_attempts", 0),
        }
    )
    action = reply.get("action") if isinstance(reply, dict) else "abort"
    if action != "retry":
        return {"status": RunStatus.FAILED.value, "error": "Đã dừng ở bước cứu hộ theo yêu cầu của người dùng."}
    return {
        "rescue_hint": str(reply.get("hint", ""))[:2000],
        "rescue_count": state.get("rescue_count", 0) + 1,
        "fix_attempts": 0,
        "error_signatures": [],
    }
