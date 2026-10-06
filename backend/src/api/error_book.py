"""Sổ lỗi: xem mục chờ duyệt, duyệt (kèm cách sửa) hoặc bỏ. Chỉ mục đã duyệt mới được gợi ý cho Codegen."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import CurrentUser, current_user
from src.api.requests import ErrorFixBody
from src.config import get_settings
from src.models.evidence import ErrorEntry
from src.services.error_memory import get_error_memory

router = APIRouter(prefix="/errors", tags=["errors"])


def _require_permission(user: CurrentUser) -> None:
    """Chế độ 2 người: chỉ Reviewer được duyệt/bỏ; mặc định (1 vai trò DE) ai cũng được."""
    if get_settings().require_separate_reviewer and user.role != "reviewer":
        raise HTTPException(status_code=403, detail="Chỉ Reviewer được duyệt hoặc bỏ mục sổ lỗi.")


@router.get("", response_model=list[ErrorEntry])
def pending_errors() -> list[ErrorEntry]:
    """Các mục sổ lỗi chờ duyệt (gặp nhiều nhất trước)."""
    return get_error_memory().pending()


@router.post("/{entry_id}/approve")
def approve_error(entry_id: int, body: ErrorFixBody, user: Annotated[CurrentUser, Depends(current_user)]) -> dict:
    """Duyệt một mục để Codegen dùng làm gợi ý lần sau."""
    _require_permission(user)
    if not get_error_memory().approve(entry_id, body.fix.strip()):
        raise HTTPException(status_code=404, detail="Không tìm thấy mục sổ lỗi này.")
    return {"id": entry_id, "approved": True}


@router.post("/{entry_id}/discard")
def discard_error(entry_id: int, user: Annotated[CurrentUser, Depends(current_user)]) -> dict:
    """Bỏ một mục không hữu ích."""
    _require_permission(user)
    if not get_error_memory().discard(entry_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy mục sổ lỗi này.")
    return {"id": entry_id, "discarded": True}
