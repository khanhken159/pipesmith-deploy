"""Auth, role enforcement, CSRF, admin operations, and additive migration checks."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from httpx import AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from src.api.deps import SESSION_COOKIE
from src.services import auth

API = "/api/v1"
PASSWORD = "strong-test-password-123"
MIGRATION_ROOT = Path(__file__).resolve().parents[2]


def _actions(target: str) -> list[tuple[str, str]]:
    with Session(auth.get_engine()) as db:
        rows = db.scalars(sa.select(auth.AuditEntry).where(auth.AuditEntry.target.contains(target)))
        return [(row.action, row.outcome) for row in rows]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/status"),
        ("get", "/runs"),
        ("post", "/runs"),
        ("get", "/auth/me"),
        ("get", "/admin/users"),
        ("get", "/admin/audit"),
    ],
)
async def test_api_rejects_anonymous_and_ignores_identity_headers(anon: AsyncClient, method: str, path: str):
    response = await getattr(anon, method)(
        f"{API}{path}",
        **(
            {"json": {"request_text": "unauthorized"}, "headers": {"X-User": "admin", "X-Role": "admin"}}
            if method == "post"
            else {"headers": {"X-User": "admin", "X-Role": "admin"}}
        ),
    )
    assert response.status_code == 401


async def test_health_stays_public_and_checks_auth_database(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert response.json()["auth_database"] == "ok"


async def test_login_sets_secure_cookie_and_hashes_password(anon: AsyncClient, make_user):
    username, password = make_user("engineer")
    response = await anon.post(
        f"{API}/auth/login",
        json={"username": username.upper(), "password": password},
        headers={"Origin": "https://test"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "engineer"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie and "max-age=" in cookie
    assert (await anon.get(f"{API}/auth/me")).json()["name"] == username
    stored = auth.find_user(username)
    assert stored is not None and stored.password_hash.startswith("$argon2id$")
    assert password not in stored.password_hash


async def test_wrong_and_unknown_passwords_have_same_response(anon: AsyncClient, make_user):
    username, _ = make_user("engineer")
    wrong = await anon.post(f"{API}/auth/login", json={"username": username, "password": "wrong-password-123"})
    unknown = await anon.post(f"{API}/auth/login", json={"username": "missing-user", "password": "wrong-password-123"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]
    assert ("login", "fail") in _actions(username)


async def test_brute_force_limit_blocks_correct_password(anon: AsyncClient, make_user):
    username, password = make_user("engineer")
    for _ in range(auth.get_settings().login_max_failures):
        await anon.post(f"{API}/auth/login", json={"username": username, "password": "bad-password-123"})
    blocked = await anon.post(f"{API}/auth/login", json={"username": username, "password": password})
    assert blocked.status_code == 429


async def test_logout_revokes_session_on_server(anon: AsyncClient, make_user):
    username, password = make_user("engineer")
    await anon.post(f"{API}/auth/login", json={"username": username, "password": password})
    old_token = anon.cookies[SESSION_COOKIE]
    assert (await anon.post(f"{API}/auth/logout")).status_code == 204
    anon.cookies.set(SESSION_COOKIE, old_token)
    assert (await anon.get(f"{API}/auth/me")).status_code == 401
    assert ("logout", "ok") in _actions(username)


async def test_expired_session_is_rejected(login):
    client = await login("engineer")
    with Session(auth.get_engine()) as db, db.begin():
        user = db.scalar(sa.select(auth.User).where(auth.User.username == client.username))
        assert user is not None
        for session in db.scalars(sa.select(auth.AuthSession).where(auth.AuthSession.user_id == user.id)):
            session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    assert (await client.get(f"{API}/auth/me")).status_code == 401


async def test_csrf_header_and_origin_are_checked(anon: AsyncClient, client: AsyncClient):
    missing_header = await client.post(
        f"{API}/runs", json={"request_text": "valid request text"}, headers={"X-Requested-With": ""}
    )
    assert missing_header.status_code == 403
    hostile_origin = await anon.post(
        f"{API}/auth/login",
        json={"username": "nobody", "password": PASSWORD},
        headers={"Origin": "https://attacker.example"},
    )
    assert hostile_origin.status_code == 403


async def test_missing_auth_configuration_fails_closed(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from src.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("SESSION_SECRET", "")
    get_settings.cache_clear()
    response = await client.get(f"{API}/status")
    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"] and "SESSION_SECRET" in response.json()["detail"]


@pytest.mark.parametrize(
    ("role", "method", "path", "body"),
    [
        ("reviewer", "post", "/runs", {"request_text": "valid request text"}),
        ("reviewer", "post", "/runs/unknown/answers", {"answers": {}}),
        ("admin", "post", "/runs", {"request_text": "valid request text"}),
        ("admin", "post", "/runs/unknown/review", {"decision": "approve"}),
        ("engineer", "get", "/admin/users", None),
        ("reviewer", "get", "/admin/audit", None),
    ],
)
async def test_backend_enforces_role_permissions(login, role: str, method: str, path: str, body: dict | None):
    user = await login(role)
    response = await getattr(user, method)(f"{API}{path}", **({"json": body} if body is not None else {}))
    assert response.status_code == 403


async def test_client_role_headers_cannot_grant_admin_access(client: AsyncClient):
    response = await client.get(f"{API}/admin/users", headers={"X-User": "root", "X-Role": "admin"})
    assert response.status_code == 403


async def test_admin_user_crud_and_session_revocation(login, client: AsyncClient):
    admin = await login("admin")
    users = (await admin.get(f"{API}/admin/users")).json()
    target = next(user for user in users if user["username"] == "test_engineer")
    assert all("password_hash" not in user for user in users)

    short_password = await admin.post(
        f"{API}/admin/users", json={"username": "new_user", "role": "reviewer", "password": "short"}
    )
    assert short_password.status_code == 422
    created = await admin.post(
        f"{API}/admin/users",
        json={"username": "new_user", "display_name": "New User", "role": "reviewer", "password": PASSWORD},
    )
    assert created.status_code == 201 and created.json()["role"] == "reviewer"
    locked = await admin.patch(f"{API}/admin/users/{target['id']}", json={"is_active": False})
    assert locked.status_code == 200 and locked.json()["is_active"] is False
    assert (await client.get(f"{API}/auth/me")).status_code == 401

    me = (await admin.get(f"{API}/auth/me")).json()
    self_lock = await admin.patch(f"{API}/admin/users/{me['id']}", json={"is_active": False})
    assert self_lock.status_code == 422
    audit = (await admin.get(f"{API}/admin/audit")).json()
    assert any(entry["action"] == "user.create" and entry["target"] == "new_user" for entry in audit)
    assert not any(PASSWORD in str(entry["detail"]) for entry in audit)


def _alembic_config(database_url: str) -> Config:
    config = Config(str(MIGRATION_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _assert_auth_tables(engine: sa.Engine) -> None:
    inspector = sa.inspect(engine)
    assert {"users", "sessions", "audit_log", "alembic_version"} <= set(inspector.get_table_names())
    assert {"ix_audit_log_at", "ix_audit_log_actor_id", "ix_audit_log_action"} <= {
        index["name"] for index in inspector.get_indexes("audit_log")
    }
    assert {"ix_sessions_user_id", "ix_sessions_expires_at"} <= {
        index["name"] for index in inspector.get_indexes("sessions")
    }


def test_auth_migration_adds_only_auth_tables_to_new_sqlite_db(tmp_path: Path):
    url = f"sqlite+pysqlite:///{(tmp_path / 'migration-test.db').as_posix()}"
    config = _alembic_config(url)
    command.upgrade(config, "head")
    engine = sa.create_engine(url)
    try:
        _assert_auth_tables(engine)
        # Re-running the additive migration is safe and does not recreate or reset data.
        command.upgrade(config, "head")
        _assert_auth_tables(engine)
    finally:
        engine.dispose()


def test_postgres_migration_adds_auth_tables_only_when_explicit_test_database_is_configured():
    import os

    url = os.getenv("TEST_DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("Set TEST_DATABASE_URL to a dedicated PostgreSQL database to run this integration check.")
    if "test" not in (make_url(url).database or "").lower():
        pytest.skip("TEST_DATABASE_URL must name a database containing 'test' to guard against production use.")
    command.upgrade(_alembic_config(url), "head")
    engine = sa.create_engine(url)
    try:
        _assert_auth_tables(engine)
    finally:
        engine.dispose()
