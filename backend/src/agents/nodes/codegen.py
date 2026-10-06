"""E3 Codegen (LLM): spec + hồ sơ + danh mục thật → model dbt + DAG Airflow."""

import logging

from src.agents.nodes.common import sandbox_db, usage_of
from src.agents.state import PipelineState
from src.agents.tools.duckdb_tools import RAW_SCHEMA, read_catalog
from src.services.error_memory import classify_error, error_signature, get_error_memory
from src.services.llm import LLMOutputError, call_llm, parse_json_output, to_json

logger = logging.getLogger(__name__)


def last_error(state: PipelineState) -> str:
    """Lỗi gần nhất của V1/V2 (rỗng nếu chưa có)."""
    safety, sandbox = state.get("safety", {}), state.get("sandbox", {})
    if safety and not safety.get("passed", True):
        return "\n".join(safety.get("issues", []))
    if sandbox and not sandbox.get("passed", True):
        return sandbox.get("error", "")
    return ""


def code_error(state: PipelineState) -> str:
    """Lỗi thuộc phần Coder viết; lỗi của file test (tests/...) là việc của Testgen."""
    return "\n".join(line for line in last_error(state).splitlines() if not line.startswith("tests/"))


def previous_code(state: PipelineState) -> str:
    """Code vòng trước, chỉ gửi khi cần sửa (có lỗi, ghi chú Reviewer hoặc gợi ý cứu hộ)."""
    needs_fix = last_error(state) or state.get("review_notes") or state.get("rescue_hint")
    return to_json(state.get("code_files", {})) if needs_fix and state.get("code_files") else "(chưa có)"


def error_hints(error: str) -> list[dict]:
    """Tối đa 3 mục sổ lỗi ĐÃ DUYỆT giống lỗi hiện tại (chỉ là gợi ý)."""
    if not error:
        return []
    entries = get_error_memory().approved_hints(error_signature(error), classify_error(error))
    return [{"code": e.code, "description": e.description[:300], "fix": e.fix} for e in entries]


def codegen_variables(state: PipelineState) -> dict[str, str]:
    """Biến điền vào prompt codegen."""
    error = code_error(state)
    return {
        "spec": to_json(state.get("spec", {})),
        "catalog": to_json(read_catalog(sandbox_db(state)).get(RAW_SCHEMA, {})),
        "profile": to_json(state.get("profile", {})),
        "last_error": error or "(không có)",
        "previous_code": previous_code(state),
        "error_hints": to_json(error_hints(error)),
        "review_notes": to_json(state.get("review_notes", [])),
        "rescue_hint": state.get("rescue_hint") or "(không có)",
    }


def only_test_errors(state: PipelineState) -> bool:
    """Lỗi chỉ nằm ở file test và không có gợi ý cứu hộ → giữ nguyên code, không gọi LLM."""
    return bool(
        last_error(state) and not code_error(state) and state.get("code_files") and not state.get("rescue_hint")
    )


def normalize_file(path: str, content: str) -> str:
    """Bỏ dấu `;` cuối file SQL: dbt nhúng model ephemeral vào model khác nên `;` làm hỏng câu ở model gọi nó."""
    return content.rstrip().rstrip(";").rstrip() + "\n" if path.endswith(".sql") else content


SYSTEM_FILES = {"dbt_project.yml", "profiles.yml", "packages.yml", "sources.yml", "selectors.yml"}


def is_system_file(path: str) -> bool:
    """File cấu hình do hệ thống quản lý (dbt_project, khai báo source) hoặc yml trong models/ (của Testgen)."""
    normalized = path.replace("\\", "/")
    is_model_yml = normalized.startswith("models/") and normalized.endswith((".yml", ".yaml"))
    return normalized.rsplit("/", 1)[-1] in SYSTEM_FILES or is_model_yml


def drop_system_files(files: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Bỏ file hệ thống mà Coder tự viết (LLM thật hay viết lại dbt_project.yml/sources.yml → trùng source)."""
    dropped = sorted(p for p in files if is_system_file(p))
    kept = {p: c for p, c in files.items() if p not in dropped}
    note = [f"Hệ thống bỏ {', '.join(dropped)}: file cấu hình do hệ thống quản lý."] if dropped else []
    return kept, note


def _generate(state: PipelineState) -> dict:
    response = call_llm("codegen", codegen_variables(state))
    try:
        data = parse_json_output(response.text)
        files = {str(k): normalize_file(str(k), str(v)) for k, v in (data.get("files") or {}).items()}
        files, dropped_note = drop_system_files(files)
        notes = [str(n) for n in data.get("notes") or []] + dropped_note
    except LLMOutputError as exc:
        logger.warning("codegen output invalid", extra={"error": str(exc)})
        files, notes = {}, [f"Codegen trả về sai định dạng: {exc}"]
    return {"code_files": files, "code_notes": notes, "llm_usage": usage_of(response)}


def codegen_node(state: PipelineState) -> dict:
    """Sinh code (hoặc giữ nguyên khi chỉ test lỗi); reset kết quả tối ưu cũ vì code có thể đã đổi."""
    generated = {"code_files": state["code_files"]} if only_test_errors(state) else _generate(state)
    return {
        **generated,
        "optimization": {},
        "opt_candidate": {},
        "opt_attempts": 0,
        "rescue_hint": "",
    }
