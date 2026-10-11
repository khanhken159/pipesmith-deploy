"""Sổ lỗi: xem mục chờ duyệt, duyệt (kèm cách sửa) hoặc bỏ. Chỉ mục đã duyệt mới được gợi ý cho Codegen."""

from fastapi import APIRouter, HTTPException

from src.api.deps import ReviewActor
from src.api.requests import ErrorFixBody
from src.models.evidence import ErrorEntry
from src.services.error_memory import get_error_memory

router = APIRouter(prefix="/errors", tags=["errors"])


@router.get("", response_model=list[ErrorEntry])
def pending_errors() -> list[ErrorEntry]:
    """Các mục sổ lỗi chờ duyệt (gặp nhiều nhất trước)."""
    return get_error_memory().pending()


@router.post("/{entry_id}/approve")
def approve_error(entry_id: int, body: ErrorFixBody, user: ReviewActor) -> dict:
    """Duyệt một mục để Codegen dùng làm gợi ý lần sau."""
    if not get_error_memory().approve(entry_id, body.fix.strip()):
        raise HTTPException(status_code=404, detail="Không tìm thấy mục sổ lỗi này.")
    return {"id": entry_id, "approved": True}


@router.post("/{entry_id}/discard")
def discard_error(entry_id: int, user: ReviewActor) -> dict:
    """Bỏ một mục không hữu ích."""
    if not get_error_memory().discard(entry_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy mục sổ lỗi này.")
    return {"id": entry_id, "discarded": True}
