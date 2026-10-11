"""Fixture dùng chung. Mọi test chạy không cần khóa: LLM_PROVIDER=mock, dữ liệu/ổ lưu trong thư mục tạm."""

import atexit
import copy
import os
import shutil
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_TMP = Path(tempfile.mkdtemp(prefix="p113-tests-"))
atexit.register(shutil.rmtree, _TMP, ignore_errors=True)  # dọn dữ liệu test khi kết thúc
os.environ.update(
    {
        "APP_ENV": "test",
        "CORS_ORIGINS": "https://test",
        "LLM_PROVIDER": "mock",
        "OPENAI_API_KEY": "",
        "GOOGLE_API_KEY": "",  # .env có thể có khóa thật: test không bao giờ gọi Gemini thật
        "LLM_FALLBACK": "none",
        "LANGCHAIN_TRACING_V2": "false",
        "LANGSMITH_TRACING": "false",
        "STORE_PATH": str(_TMP / "app.db"),
        "CHECKPOINT_PATH": str(_TMP / "checkpoints.db"),
        "SOURCES_DIR": str(_TMP / "sources"),
        "WORKSPACES_DIR": str(_TMP / "workspaces"),
        "TEMPLATE_DIR": str(REPO_ROOT / "pipelines" / "template"),
        "MOCK_LARGE_ROWS": "20000",
        "OPT_BENCH_RUNS": "3",
    }
)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.services.seed import SeedConfig, generate_sources  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session")
def seeded_sources() -> Path:
    """Dữ liệu giả lập 3 nguồn (seed cố định) trong thư mục tạm."""
    out = get_settings().sources_dir
    generate_sources(SeedConfig(out_dir=out, seed=42, dirty=0.05, rows_per_source=120))
    return out


@pytest_asyncio.fixture
async def client_factory(auth_database):
    """Create in-process API clients for the isolated auth database."""
    from src.main import app

    transport = ASGITransport(app=app)
    clients: list[AsyncClient] = []

    async def create() -> AsyncClient:
        ac = AsyncClient(
            transport=transport,
            base_url="https://test",
            headers={"X-Requested-With": "p113-web"},
        )
        clients.append(ac)
        return ac

    yield create
    for ac in clients:
        await ac.aclose()


@pytest.fixture
def auth_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use a new SQLite auth database for each API test; never touch external or persistent data."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    from src.config import get_settings
    from src.services import auth

    monkeypatch.setenv("APP_ENV", "test")
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'auth.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("MIGRATION_DATABASE_URL", f"sqlite+pysqlite:///{(tmp_path / 'migration.db').as_posix()}")
    monkeypatch.setenv("SESSION_SECRET", "test-only-secret-with-at-least-32-characters")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "lax")
    monkeypatch.setenv("CORS_ORIGINS", "https://test")
    get_settings.cache_clear()
    engine = create_engine(database_url, connect_args={"check_same_thread": False}, poolclass=NullPool)
    monkeypatch.setattr(auth, "get_engine", lambda: engine)
    auth.Base.metadata.create_all(engine)
    yield
    engine.dispose()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def anon(client_factory):
    """Unauthenticated client for session and fail-closed checks."""
    return await client_factory()


@pytest_asyncio.fixture
async def client(client_factory):
    """Signed-in Engineer client for existing business API regression tests."""
    from src.services import auth

    username = "test_engineer"
    password = "strong-test-password-123"
    auth.create_user(username, "Test Engineer", "engineer", password)
    ac = await client_factory()
    response = await ac.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": "https://test"},
    )
    assert response.status_code == 200
    return ac


@pytest_asyncio.fixture
async def login(client_factory):
    """Create and sign in an isolated role account; returned clients close at test teardown."""
    from src.services import auth

    serial = 0

    async def sign_in(role: str, username: str | None = None) -> AsyncClient:
        nonlocal serial
        serial += 1
        name = username or f"test_{role}_{serial}"
        password = "strong-test-password-123"
        auth.create_user(name, f"Test {role}", role, password)
        ac = await client_factory()
        response = await ac.post(
            "/api/v1/auth/login",
            json={"username": name, "password": password},
            headers={"Origin": "https://test"},
        )
        assert response.status_code == 200
        ac.username = name
        return ac

    return sign_in


@pytest.fixture
def make_user(auth_database):
    """Create a user directly in this test's isolated database."""
    from src.services import auth

    serial = 0

    def create(role: str, username: str | None = None, password: str = "strong-test-password-123"):
        nonlocal serial
        serial += 1
        name = username or f"make_{role}_{serial}"
        auth.create_user(name, f"Test {role}", role, password)
        return name, password

    return create


@pytest.fixture
def mock_llm(monkeypatch: pytest.MonkeyPatch):
    """Thay câu trả lời LLM của một tác vụ bằng dict cố định: `mock_llm("codegen", {...})`."""
    from src.services import llm_mock

    def _set(task: str, payload: dict) -> None:
        monkeypatch.setitem(llm_mock.HANDLERS, task, lambda variables: payload)

    return _set


@pytest.fixture(scope="session")
def built_state(seeded_sources: Path) -> dict:
    """State sau E1 → E0 → P → E2 → E3 → E3b (mock), chưa chạy V1/V2. Dùng chung, không sửa trực tiếp."""
    from src.agents.nodes.codegen import codegen_node
    from src.agents.nodes.ingest import ingest_node
    from src.agents.nodes.mock_data import mock_data_node
    from src.agents.nodes.planner import planner_node
    from src.agents.nodes.profiler import profiler_node
    from src.agents.nodes.testgen import testgen_node
    from src.services.llm_mock import DUPLICATE_OPTIONS, Q_DUPLICATES, Q_STATUS, STATUS_OPTIONS

    state: dict = {
        "run_id": "fixture-run",
        "request_text": "Gộp đơn hàng 3 nguồn, tính doanh thu ngày",
        "requester": "alice",
        "answers": {Q_STATUS: STATUS_OPTIONS[0], Q_DUPLICATES: DUPLICATE_OPTIONS[0]},
    }
    for node in (planner_node, ingest_node, profiler_node, mock_data_node, codegen_node, testgen_node):
        state.update(node(state))
    return state


@pytest.fixture
def separate_reviewer(monkeypatch: pytest.MonkeyPatch):
    """Bật chế độ 2 người (REQUIRE_SEPARATE_REVIEWER=true) cho một test; mặc định là 1 vai trò DE tự duyệt."""
    monkeypatch.setenv("REQUIRE_SEPARATE_REVIEWER", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("REQUIRE_SEPARATE_REVIEWER")
    get_settings.cache_clear()


@pytest.fixture
def pipeline_state(built_state: dict) -> dict:
    """Bản sao độc lập của `built_state` cho từng test."""
    return copy.deepcopy(built_state)
