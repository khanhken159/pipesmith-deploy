"""Phụ thuộc dùng chung của API: người dùng hiện tại, lần chạy theo id.

Mức bảo mật tối thiểu (ghi rõ trong README): người dùng/vai trò lấy từ header `X-User` / `X-Role`, chưa có đăng nhập.
Mặc định một vai trò DE; vai trò chỉ có ý nghĩa khi bật REQUIRE_SEPARATE_REVIEWER.
"""

from typing import Annotated, Literal

from fastapi import Header, HTTPException
from pydantic import BaseModel

from src.models.schemas import RunRecord
from src.services.store import get_store


class CurrentUser(BaseModel):
    """Người đang thao tác."""

    name: str
    role: Literal["de", "engineer", "reviewer"]


def current_user(
    x_user: Annotated[str, Header(max_length=64)] = "de",
    x_role: Annotated[Literal["de", "engineer", "reviewer"], Header()] = "de",
) -> CurrentUser:
    """Đọc người dùng từ header (mặc định `de`)."""
    return CurrentUser(name=x_user.strip() or "de", role=x_role)


def run_or_404(run_id: str) -> RunRecord:
    """Lần chạy theo id, 404 (tiếng Việt) nếu không có."""
    record = get_store().get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần chạy này.")
    return record
