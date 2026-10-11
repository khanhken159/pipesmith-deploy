"""Đăng nhập, đăng xuất, người dùng hiện tại; quản lý tài khoản cho Admin.

Không có API đăng ký: tài khoản do doanh nghiệp cấp (Admin trên web, hoặc `python -m src.cli users ...`).
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from src.api.deps import (
    SESSION_COOKIE,
    Admin,
    CurrentUser,
    LoggedIn,
    check_csrf,
    client_ip,
    require_auth_config,
)
from src.config import get_settings
from src.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])

BAD_LOGIN = "Tên đăng nhập hoặc mật khẩu không đúng."


class LoginBody(BaseModel):
    """Thông tin đăng nhập (không bao giờ ghi log)."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserView(BaseModel):
    """Tài khoản trả cho web (không có chuỗi băm mật khẩu)."""

    id: int
    username: str
    display_name: str
    role: auth.Role
    is_active: bool = True
    last_login_at: datetime | None = None


class CreateUserBody(BaseModel):
    """Admin tạo tài khoản kèm mật khẩu tạm."""

    username: str = Field(min_length=2, max_length=32)
    display_name: str = Field(default="", max_length=80)
    role: auth.Role
    password: str = Field(min_length=1, max_length=256)


class UpdateUserBody(BaseModel):
    """Admin đổi vai trò, khóa/mở, đặt lại mật khẩu (trường nào bỏ trống thì giữ nguyên)."""

    display_name: str | None = Field(default=None, max_length=80)
    role: auth.Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, max_length=256)


def _view(user: auth.User) -> UserView:
    return UserView(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
    )


def _set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


@router.post("/login", response_model=UserView)
def login(body: LoginBody, request: Request, response: Response) -> UserView:
    """Đăng nhập: đúng thì đặt cookie phiên HttpOnly; sai trả thông báo chung (không lộ tài khoản nào tồn tại)."""
    require_auth_config()
    check_csrf(request)
    try:
        user = auth.authenticate(body.username, body.password, client_ip(request))
    except auth.LoginLockedError as exc:
        minutes = get_settings().login_lock_minutes
        raise HTTPException(status_code=429, detail=f"Đăng nhập sai nhiều lần. Thử lại sau {minutes} phút.") from exc
    if user is None:
        raise HTTPException(status_code=401, detail=BAD_LOGIN)
    token, _ = auth.create_session(user)
    _set_cookie(response, token)
    return _view(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> None:
    """Đăng xuất: thu hồi phiên ở máy chủ rồi xóa cookie."""
    require_auth_config()
    check_csrf(request)
    token = request.cookies.get(SESSION_COOKIE, "")
    user = auth.user_for_token(token) if token else None
    if token:
        auth.revoke_session(token)
    if user is not None:
        auth.audit("logout", user, target=user.username, ip=client_ip(request))
    settings = get_settings()
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )


@router.get("/me", response_model=CurrentUser)
def me(user: LoggedIn) -> CurrentUser:
    """Người dùng của phiên hiện tại (web dùng để biết đã đăng nhập và vai trò gì)."""
    return user


# ---------- Admin ----------


class AuditView(BaseModel):
    """Một dòng nhật ký kiểm toán (không bao giờ chứa mật khẩu/token)."""

    at: datetime
    actor_name: str
    action: str
    target: str
    outcome: str
    ip: str
    detail: dict


@admin_router.get("/audit", response_model=list[AuditView])
def audit_log(admin: Admin, limit: int = Query(default=50, ge=1, le=200)) -> list[AuditView]:
    """Nhật ký mới nhất trước (chỉ đọc; bảng chỉ ghi thêm)."""
    return [AuditView.model_validate(e, from_attributes=True) for e in auth.recent_audit(limit)]


@admin_router.get("/users", response_model=list[UserView])
def list_users(admin: Admin) -> list[UserView]:
    """Mọi tài khoản."""
    return [_view(u) for u in auth.list_users()]


@admin_router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserView)
def create_user(body: CreateUserBody, admin: Admin, request: Request) -> UserView:
    """Cấp tài khoản mới (mật khẩu tạm đưa riêng cho người dùng, không gửi qua kênh chung)."""
    try:
        user = auth.create_user(body.username, body.display_name, body.role, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    auth.audit("user.create", admin.name, target=user.username, ip=client_ip(request), detail={"role": user.role})
    return _view(user)


@admin_router.patch("/users/{user_id}", response_model=UserView)
def update_user(user_id: int, body: UpdateUserBody, admin: Admin, request: Request) -> UserView:
    """Đổi vai trò / khóa-mở / đặt lại mật khẩu; Admin không tự khóa hay tự bỏ quyền Admin của mình."""
    if user_id == admin.id and (body.is_active is False or (body.role and body.role != "admin")):
        raise HTTPException(status_code=422, detail="Không thể tự khóa hoặc tự bỏ quyền Admin của chính mình.")
    try:
        user = auth.update_user(
            user_id, role=body.role, is_active=body.is_active, password=body.password, display_name=body.display_name
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if user is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản này.")
    changes = {k: v for k, v in body.model_dump(exclude={"password"}).items() if v is not None}
    if body.password is not None:
        changes["password"] = "đã đặt lại"  # chỉ ghi là có đổi, không ghi giá trị
    auth.audit("user.update", admin.name, target=user.username, ip=client_ip(request), detail=changes)
    return _view(user)
