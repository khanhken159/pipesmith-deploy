"""Shared authenticated API dependencies and CSRF checks."""

import logging
import re
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

from src.config import get_settings
from src.models.schemas import RunRecord
from src.services import auth
from src.services.store import get_store

logger = logging.getLogger(__name__)

SESSION_COOKIE = "p113_session"
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "p113-web"
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
FORBIDDEN = "Bạn không có quyền thực hiện thao tác này."
DEV_ORIGIN_REGEX = re.compile(r"^http://(localhost|127\.0\.0\.1|\[::1\]|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$")


class CurrentUser(BaseModel):
    """Người đang thao tác; danh tính và vai trò chỉ lấy từ phiên máy chủ."""

    id: int
    name: str
    display_name: str
    role: auth.Role


def client_ip(request: Request) -> str:
    """IP kết nối; chỉ dùng trong audit, không tin header do client gửi."""
    return request.client.host if request.client else ""


def require_auth_config() -> None:
    """Thiếu cấu hình auth thì dừng fail-closed, không có chế độ người dùng giả."""
    missing = get_settings().missing_auth_settings
    if missing:
        raise HTTPException(status_code=503, detail=f"Máy chủ chưa cấu hình đăng nhập: thiếu {', '.join(missing)}.")


def check_csrf(request: Request) -> None:
    """Require a non-simple header and validate browser Origin on every write."""
    if request.method in SAFE_METHODS:
        return
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise HTTPException(status_code=403, detail="Yêu cầu bị chặn: thiếu header bảo vệ CSRF.")

    origin = request.headers.get("origin")
    if not origin:
        return  # Trusted non-browser clients still need the unforgeable-from-a-form header above.
    allowed = {item.strip().rstrip("/") for item in get_settings().cors_origins.split(",") if item.strip()}
    if origin.rstrip("/") not in allowed and not (
        get_settings().app_env == "development" and DEV_ORIGIN_REGEX.fullmatch(origin.rstrip("/"))
    ):
        raise HTTPException(status_code=403, detail="Yêu cầu bị chặn: nguồn gửi không hợp lệ.")


def current_user(request: Request) -> CurrentUser:
    """Read the current account from its HttpOnly cookie and server-side session."""
    require_auth_config()
    check_csrf(request)
    token = request.cookies.get(SESSION_COOKIE, "")
    user = auth.user_for_token(token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Bạn cần đăng nhập.", headers={"WWW-Authenticate": "Cookie"})
    return CurrentUser(id=user.id, name=user.username, display_name=user.display_name, role=user.role)


def require_role(*roles: str) -> Callable[..., CurrentUser]:
    """Require one of the listed roles and record denied actions without policy details."""

    def dependency(request: Request, user: Annotated[CurrentUser, Depends(current_user)]) -> CurrentUser:
        if user.role not in roles:
            path = request.url.path
            logger.warning("permission denied", extra={"user": user.name, "role": user.role, "path": path})
            auth.audit(
                "permission.denied",
                user.name,
                target=f"{request.method} {path}",
                outcome="denied",
                ip=client_ip(request),
                detail={"role": user.role},
            )
            raise HTTPException(status_code=403, detail=FORBIDDEN)
        return user

    return dependency


def review_actor(request: Request, user: Annotated[CurrentUser, Depends(current_user)]) -> CurrentUser:
    """Preserve the target's policy: reviewer-only in separate mode, operator review otherwise."""
    permitted = {"reviewer"} if get_settings().require_separate_reviewer else {"engineer", "reviewer"}
    if user.role not in permitted:
        logger.warning("permission denied", extra={"user": user.name, "role": user.role, "path": request.url.path})
        auth.audit(
            "permission.denied",
            user.name,
            target=f"{request.method} {request.url.path}",
            outcome="denied",
            ip=client_ip(request),
            detail={"role": user.role},
        )
        raise HTTPException(status_code=403, detail=FORBIDDEN)
    return user


LoggedIn = Annotated[CurrentUser, Depends(current_user)]
Engineer = Annotated[CurrentUser, Depends(require_role("engineer"))]
Reviewer = Annotated[CurrentUser, Depends(require_role("reviewer"))]
Admin = Annotated[CurrentUser, Depends(require_role("admin"))]
DataViewer = Annotated[CurrentUser, Depends(require_role("engineer", "reviewer"))]
ReviewActor = Annotated[CurrentUser, Depends(review_actor)]


def run_or_404(run_id: str) -> RunRecord:
    """Look up a run or return the target API's existing 404 response."""
    record = get_store().get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần chạy này.")
    return record
