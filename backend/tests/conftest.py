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
async def client():
    """HTTP client gọi thẳng ứng dụng FastAPI (không mở cổng)."""
    from src.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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
