"""Tài khoản, phiên đăng nhập và nhật ký kiểm toán (PostgreSQL qua SQLAlchemy 2; cấu trúc bảng do Alembic quản lý).

- Mật khẩu: BĂM argon2id bằng `argon2-cffi` (thư viện đã kiểm chứng), không lưu chữ thường ở đâu cả.
- Phiên: chuỗi ngẫu nhiên 256 bit (`secrets`) nằm trong cookie HttpOnly; máy chủ chỉ lưu HMAC-SHA256 của nó (khóa
  SESSION_SECRET) nên lộ bảng `sessions` cũng không dùng lại được phiên. Đăng xuất = đánh dấu thu hồi ở máy chủ.
- `audit_log` chỉ ghi thêm: code ở đây không bao giờ UPDATE/DELETE; tài khoản ứng dụng chỉ có quyền SELECT/INSERT.
- KHÔNG ghi mật khẩu, token hay chuỗi kết nối vào log hoặc vào `audit_log.detail`.
"""

import hashlib
import hmac
import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Literal, get_args

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    String,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from src.config import get_settings

logger = logging.getLogger(__name__)

Role = Literal["engineer", "reviewer", "admin"]
ROLES: tuple[str, ...] = get_args(Role)
USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,31}$")
MIN_PASSWORD_LENGTH = 12
SSL_MODES_OK = ("sslmode=require", "sslmode=verify-ca", "sslmode=verify-full")

_hasher = PasswordHasher()  # mặc định của argon2-cffi là argon2id, tham số theo RFC 9106
# Băm sẵn một mật khẩu giả: tên đăng nhập không tồn tại vẫn tốn thời gian kiểm như thật (không lộ ai có tài khoản).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


class AuthConfigError(RuntimeError):
    """Thiếu hoặc sai cấu hình đăng nhập (DATABASE_URL, SESSION_SECRET, SSL)."""


class LoginLockedError(RuntimeError):
    """Đăng nhập sai quá nhiều lần trong khoảng khóa."""


class Base(DeclarativeBase):
    """Gốc khai báo bảng của cơ sở dữ liệu ứng dụng."""


ID = BigInteger().with_variant(Integer, "sqlite")  # SQLite chỉ tự tăng với INTEGER PRIMARY KEY
DETAIL = JSON().with_variant(JSONB, "postgresql")


class User(Base):
    """Tài khoản do doanh nghiệp cấp (không có đăng ký tự do); khóa bằng `is_active`, không xóa."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(16), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthSession(Base):
    """Phiên đăng nhập phía máy chủ; chỉ lưu HMAC của token."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEntry(Base):
    """Ai làm gì, khi nào (chỉ ghi thêm)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    actor_name: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(48), index=True)
    target: Mapped[str] = mapped_column(String(200), default="")
    outcome: Mapped[str] = mapped_column(String(16), default="ok")
    ip: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict] = mapped_column(DETAIL, default=dict)


def _now() -> datetime:
    return datetime.now(UTC)


def _utc(value: datetime) -> datetime:
    """SQLite trả thời gian không kèm múi giờ; mọi giá trị đều ghi theo UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# ---------- Kết nối ----------


def check_database_url(url: str, app_env: str) -> None:
    """Production: PostgreSQL bắt buộc SSL (ưu tiên verify-full). Không đưa chuỗi kết nối vào thông báo lỗi."""
    if not url:
        raise AuthConfigError("Thiếu biến môi trường DATABASE_URL.")
    if app_env == "production":
        if not url.startswith("postgresql"):
            raise AuthConfigError("Production chỉ dùng PostgreSQL cho DATABASE_URL.")
        if not any(mode in url for mode in SSL_MODES_OK):
            raise AuthConfigError("Production phải bật SSL tới PostgreSQL (thêm sslmode=verify-full vào DATABASE_URL).")


@lru_cache(maxsize=4)
def _engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def get_engine() -> Engine:
    """Engine theo DATABASE_URL hiện tại (tài khoản ứng dụng, KHÔNG phải tài khoản migration)."""
    settings = get_settings()
    check_database_url(settings.database_url, settings.app_env)
    return _engine(settings.database_url)


def ping() -> bool:
    """Check connectivity and that the auth migration has created its user table."""
    try:
        with get_engine().connect() as conn:
            conn.execute(select(User.id).limit(1))
        return True
    except Exception as exc:  # noqa: BLE001 — health chỉ báo ok/error, không làm sập endpoint
        logger.error("auth db ping failed", extra={"error": type(exc).__name__})
        return False


# ---------- Mật khẩu ----------


def hash_password(password: str) -> str:
    """Băm argon2id (muối ngẫu nhiên nằm sẵn trong chuỗi băm)."""
    return _hasher.hash(password)


def password_problem(password: str) -> str:
    """Chuỗi rỗng = mật khẩu đạt yêu cầu tối thiểu."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Mật khẩu cần ít nhất {MIN_PASSWORD_LENGTH} ký tự."
    if len(password) > 256:
        return "Mật khẩu quá dài (tối đa 256 ký tự)."
    return ""


def _verify(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# ---------- Nhật ký kiểm toán ----------


def audit(
    action: str,
    actor: User | str | None,
    target: str = "",
    outcome: str = "ok",
    ip: str = "",
    detail: dict | None = None,
) -> None:
    """Ghi một dòng `audit_log`. Lỗi ghi không làm hỏng thao tác chính nhưng luôn được log (không kèm bí mật)."""
    if not get_settings().database_url:
        logger.warning("audit skipped: DATABASE_URL not set", extra={"action": action})
        return
    entry = AuditEntry(
        at=_now(),
        actor_id=actor.id if isinstance(actor, User) else None,
        actor_name=(actor.username if isinstance(actor, User) else actor or "anonymous")[:64],
        action=action,
        target=target[:200],
        outcome=outcome,
        ip=ip[:64],
        detail=detail or {},
    )
    try:
        with Session(get_engine()) as db, db.begin():
            db.add(entry)
    except Exception as exc:  # noqa: BLE001
        logger.error("audit write failed", extra={"action": action, "error": type(exc).__name__})


def recent_audit(limit: int = 100) -> list[AuditEntry]:
    """Các dòng nhật ký mới nhất trước."""
    with Session(get_engine()) as db:
        return list(db.scalars(select(AuditEntry).order_by(AuditEntry.id.desc()).limit(limit)))


def _recent_failures(db: Session, username: str) -> int:
    since = _now() - timedelta(minutes=get_settings().login_lock_minutes)
    query = select(func.count(AuditEntry.id)).where(
        AuditEntry.action == "login",
        AuditEntry.outcome == "fail",
        AuditEntry.target == username,
        AuditEntry.at >= since,
    )
    return db.scalar(query) or 0


# ---------- Đăng nhập / phiên ----------


def _session_secret() -> bytes:
    secret = get_settings().session_secret
    if len(secret) < 32:
        raise AuthConfigError("SESSION_SECRET phải có ít nhất 32 ký tự ngẫu nhiên.")
    return secret.encode()


def _token_hash(token: str) -> str:
    return hmac.new(_session_secret(), token.encode(), hashlib.sha256).hexdigest()


def authenticate(username: str, password: str, ip: str = "") -> User | None:
    """Đúng tên + mật khẩu + tài khoản còn hoạt động → User; sai → None. Sai quá nhiều lần → LoginLockedError."""
    name = username.strip().lower()
    with Session(get_engine()) as db:
        if _recent_failures(db, name) >= get_settings().login_max_failures:
            audit("login", name, target=name, outcome="locked", ip=ip)
            raise LoginLockedError
        user = db.scalar(select(User).where(User.username == name))
        ok = _verify(user.password_hash if user else _DUMMY_HASH, password) and bool(user and user.is_active)
        if not ok or user is None:
            audit("login", name, target=name, outcome="fail", ip=ip)
            return None
        if _hasher.check_needs_rehash(user.password_hash):  # tham số argon2 mới hơn → băm lại
            user.password_hash = hash_password(password)
        user.last_login_at = _now()
        db.commit()
        db.refresh(user)
        db.expunge(user)
    audit("login", user, target=name, ip=ip)
    return user


def create_session(user: User) -> tuple[str, datetime]:
    """Tạo phiên mới; trả token gốc (chỉ đặt vào cookie, không lưu, không log) và hạn dùng."""
    token = secrets.token_urlsafe(32)
    expires = _now() + timedelta(minutes=get_settings().session_ttl_minutes)
    with Session(get_engine()) as db, db.begin():
        db.add(AuthSession(token_hash=_token_hash(token), user_id=user.id, created_at=_now(), expires_at=expires))
    return token, expires


def user_for_token(token: str) -> User | None:
    """Người dùng của phiên còn hạn, chưa thu hồi, tài khoản còn hoạt động; ngược lại None."""
    with Session(get_engine()) as db:
        row = db.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(AuthSession.token_hash == _token_hash(token))
        ).first()
        if row is None:
            return None
        session, user = row
        if session.revoked_at is not None or _utc(session.expires_at) <= _now() or not user.is_active:
            return None
        db.expunge(user)
        return user


def revoke_session(token: str) -> None:
    """Đăng xuất: phiên mất hiệu lực ngay ở máy chủ (cookie cũ dùng lại cũng bị 401)."""
    with Session(get_engine()) as db, db.begin():
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
        if session and session.revoked_at is None:
            session.revoked_at = _now()


def _revoke_all(db: Session, user_id: int) -> None:
    for session in db.scalars(
        select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    ):
        session.revoked_at = _now()


# ---------- Quản lý tài khoản (Admin / CLI) ----------


def list_users() -> list[User]:
    """Mọi tài khoản, theo tên."""
    with Session(get_engine()) as db:
        return list(db.scalars(select(User).order_by(User.username)))


def create_user(username: str, display_name: str, role: str, password: str) -> User:
    """Tạo tài khoản (ValueError nếu tên/vai trò/mật khẩu không hợp lệ hoặc tên đã có)."""
    name = username.strip().lower()
    if not USERNAME_PATTERN.fullmatch(name):
        raise ValueError("Tên đăng nhập 2–32 ký tự: chữ thường không dấu, số, . _ -")
    if role not in ROLES:
        raise ValueError("Vai trò không hợp lệ.")
    problem = password_problem(password)
    if problem:
        raise ValueError(problem)
    now = _now()
    with Session(get_engine()) as db:
        if db.scalar(select(User.id).where(User.username == name)) is not None:
            raise ValueError("Tên đăng nhập đã tồn tại.")
        user = User(
            username=name,
            display_name=display_name.strip()[:80] or name,
            role=role,
            password_hash=hash_password(password),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
    return user


def update_user(
    user_id: int,
    *,
    role: str | None = None,
    is_active: bool | None = None,
    password: str | None = None,
    display_name: str | None = None,
) -> User | None:
    """Đổi vai trò / khóa-mở / đặt lại mật khẩu. Đổi vai trò, khóa, đổi mật khẩu đều thu hồi mọi phiên đang mở."""
    if role is not None and role not in ROLES:
        raise ValueError("Vai trò không hợp lệ.")
    if password is not None and password_problem(password):
        raise ValueError(password_problem(password))
    with Session(get_engine()) as db:
        user = db.get(User, user_id)
        if user is None:
            return None
        if display_name is not None:
            user.display_name = display_name.strip()[:80] or user.username
        changed_access = False
        if role is not None and role != user.role:
            user.role, changed_access = role, True
        if is_active is not None and is_active != user.is_active:
            user.is_active, changed_access = is_active, True
        if password is not None:
            user.password_hash, changed_access = hash_password(password), True
        if changed_access:
            _revoke_all(db, user.id)
        user.updated_at = _now()
        db.commit()
        db.refresh(user)
        db.expunge(user)
    return user


def find_user(username: str) -> User | None:
    """Tài khoản theo tên đăng nhập."""
    with Session(get_engine()) as db:
        user = db.scalar(select(User).where(User.username == username.strip().lower()))
        if user is not None:
            db.expunge(user)
        return user
