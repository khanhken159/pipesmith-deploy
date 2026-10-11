"""Bảng đăng nhập: users, sessions, audit_log (chỉ ghi thêm) + quyền cho tài khoản ứng dụng.

Revision ID: 0001_auth_tables
Revises:
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from src.config import get_settings

revision: str = "0001_auth_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(32), nullable=False, unique=True),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.Column("last_login_at", TS, nullable=True),
        sa.CheckConstraint("role IN ('engineer', 'reviewer', 'admin')", name="ck_users_role"),
    )
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    op.create_table(
        "sessions",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", ID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS, nullable=True),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "audit_log",
        sa.Column("id", ID, primary_key=True, autoincrement=True),
        sa.Column("at", TS, nullable=False),
        sa.Column("actor_id", ID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_name", sa.String(64), nullable=False),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("target", sa.String(200), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("ip", sa.String(64), nullable=False, server_default=""),
        sa.Column("detail", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
    )
    op.create_index("ix_audit_log_at", "audit_log", ["at"])
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])

    if op.get_bind().dialect.name == "postgresql":
        _grant_app_role(get_settings().db_app_role)


def _grant_app_role(role: str) -> None:
    """Tài khoản ứng dụng: đọc/ghi users, sessions; audit_log CHỈ SELECT + INSERT (không UPDATE/DELETE/TRUNCATE).

    Tên role đã kiểm bằng regex trong Settings (chỉ a-z, 0-9, _) nên ghép vào câu lệnh an toàn.
    Role chưa tồn tại thì bỏ qua và báo để DBA có thể tạo role trước rồi chạy lại migration.
    """
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                GRANT SELECT, INSERT, UPDATE ON users, sessions TO {role};
                GRANT SELECT, INSERT ON audit_log TO {role};
                REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM {role};
                GRANT USAGE, SELECT ON SEQUENCE users_id_seq, sessions_id_seq, audit_log_id_seq TO {role};
            ELSE
                RAISE NOTICE 'Role {role} chưa có: bỏ qua cấp quyền';
            END IF;
        END $$;
        """
    )
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC")


def downgrade() -> None:
    raise RuntimeError("This auth migration is intentionally irreversible to prevent accidental account-data deletion.")
