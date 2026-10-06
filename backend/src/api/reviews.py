"""Duyệt (J2): hàng đợi chờ duyệt, approve/reject theo luật `review_permission_error` (dùng chung với CLI)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.agents import runner
from src.agents.runner import PermissionDeniedError, RunStateError
from src.api.deps import CurrentUser, current_user, run_or_404
from src.api.requests import Accepted, ReviewBody
from src.models.evidence import ReviewDecision
from src.models.schemas import RunRecord, RunStatus
from src.services.jobs import get_jobs
from src.services.store import get_store

router = APIRouter(tags=["reviews"])


@router.get("/reviews/queue", response_model=list[RunRecord])
async def review_queue() -> list[RunRecord]:
    """Các lần chạy đang chờ duyệt (mới nhất trước)."""
    return [r for r in get_store().list_runs(100) if r.status == RunStatus.WAITING_REVIEW]


@router.post("/runs/{run_id}/review", status_code=status.HTTP_202_ACCEPTED, response_model=Accepted)
def review(run_id: str, body: ReviewBody, user: Annotated[CurrentUser, Depends(current_user)]) -> Accepted:
    """Duyệt hoặc từ chối; từ chối kèm ghi chú → agent sửa lại rồi chờ duyệt lần nữa."""
    run_or_404(run_id)
    if body.decision == "reject" and not body.note.strip():
        raise HTTPException(status_code=422, detail="Từ chối thì cần ghi chú để agent biết sửa gì.")
    if get_jobs().busy(run_id):
        raise HTTPException(status_code=409, detail="Lần chạy đang chạy, vui lòng đợi.")
    decision = ReviewDecision(run_id=run_id, reviewer=user.name, decision=body.decision, note=body.note.strip())
    try:
        runner.check_review(decision, user.role)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RunStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    get_jobs().submit(run_id, lambda sink: runner.submit_review(decision, user.role, sink))
    message = "Đã duyệt." if body.decision == "approve" else "Đã từ chối, agent đang sửa theo ghi chú."
    return Accepted(run_id=run_id, status="running", message=message)
