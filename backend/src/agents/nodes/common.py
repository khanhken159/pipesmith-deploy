"""Hàm dùng chung cho các node."""

from pathlib import Path

from src.agents.state import PipelineState
from src.models.evidence import ErrorEntry
from src.models.spec import PipelineSpec
from src.services.error_memory import classify_error, error_signature, get_error_memory
from src.services.llm import LLMResponse

SANDBOX_DB = "sandbox.duckdb"


def spec_of(state: PipelineState) -> PipelineSpec:
    """Đặc tả hiện tại dưới dạng Pydantic."""
    return PipelineSpec.model_validate(state.get("spec") or {"request_text": state.get("request_text", "")})


def mart_path(spec: PipelineSpec) -> str:
    """Đường dẫn model đích trong dự án dbt."""
    return f"models/marts/{spec.target}.sql"


def sandbox_db(state: PipelineState) -> Path:
    """File DuckDB sandbox của lần chạy."""
    return Path(state["workspace"]) / SANDBOX_DB


def usage_of(response: LLMResponse) -> list[dict]:
    """Mục thống kê LLM để cộng dồn vào `llm_usage`."""
    return [response.usage.model_dump()]


def register_failure(state: PipelineState, message: str, sql_before: str = "") -> dict:
    """Ghi lỗi V-node vào sổ lỗi và tăng bộ đếm sửa; trả về phần cập nhật state."""
    signature = error_signature(message)
    entry = ErrorEntry(code=classify_error(message), signature=signature, description=message, sql_before=sql_before)
    get_error_memory().record(entry)
    return {
        "fix_attempts": state.get("fix_attempts", 0) + 1,
        "error_signatures": [*state.get("error_signatures", []), signature],
    }


def all_files(state: PipelineState) -> dict[str, str]:
    """Toàn bộ file sinh ra (code + test)."""
    return {**state.get("code_files", {}), **state.get("test_files", {})}
