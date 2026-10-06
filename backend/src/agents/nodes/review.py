"""J2 Duyệt: graph tạm dừng chờ approve/reject.

Mặc định một vai trò DE (người tạo yêu cầu tự duyệt). REQUIRE_SEPARATE_REVIEWER=true: người tạo không được tự duyệt
(kiểm tra cả ở đây — lớp phòng thủ thứ hai sau `review_permission_error` của runner).
"""

from langgraph.types import interrupt
from pydantic import ValidationError

from src.agents.nodes.common import all_files
from src.agents.state import PipelineState
from src.config import get_settings
from src.models.evidence import ReviewDecision
from src.models.schemas import RunStatus


def validate_decision(reply: object, run_id: str, requester: str) -> ReviewDecision | None:
    """Quyết định hợp lệ hay không (sai định dạng, hoặc tự duyệt khi bật chế độ 2 người → None)."""
    try:
        decision = ReviewDecision.model_validate({**(reply if isinstance(reply, dict) else {}), "run_id": run_id})
    except ValidationError:
        return None
    self_review = decision.reviewer.strip().lower() == requester.strip().lower()
    if self_review and get_settings().require_separate_reviewer:
        return None
    return decision


def review_node(state: PipelineState) -> dict:
    """Chờ quyết định; reject kèm ghi chú → quay lại Codegen với bộ file hiện tại làm gốc so sánh."""
    reply = interrupt({"kind": "review", "run_id": state["run_id"], "requester": state.get("requester", "")})
    decision = validate_decision(reply, state["run_id"], state.get("requester", ""))
    if decision is None:
        return {"review": {"invalid": True}}
    if decision.decision == "approve":
        return {"review": decision.model_dump()}
    return {
        "review": decision.model_dump(),
        "review_notes": [*state.get("review_notes", []), decision.note or "(không có ghi chú)"],
        "review_rounds": state.get("review_rounds", 0) + 1,
        "previous_files": all_files(state),
        "fix_attempts": 0,
        "error_signatures": [],
        "status": RunStatus.RUNNING.value,
    }


def finalize_node(state: PipelineState) -> dict:
    """Đã duyệt: code trong workspace sẵn sàng để Engineer mở PR → CI/CD (không tự push)."""
    return {"status": RunStatus.APPROVED.value}


def fail_node(state: PipelineState) -> dict:
    """Dừng hẳn với lý do rõ ràng."""
    reason = state.get("error") or "Vượt quá số vòng cho phép (lập kế hoạch / sửa lỗi / duyệt)."
    return {"status": RunStatus.FAILED.value, "error": reason}
