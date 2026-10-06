"""V2 Sandbox (code thuần): ghi file đã qua V1 vào workspace, chạy `dbt build` trên DuckDB local, đo kết quả."""

import logging
from pathlib import Path

from src.agents.nodes.common import all_files, mart_path, register_failure, sandbox_db, spec_of
from src.agents.state import PipelineState
from src.agents.tools.dbt_tools import DbtResult, run_dbt_build, write_generated_files
from src.agents.tools.duckdb_tools import connect_read
from src.agents.tools.pii import mask_rows

logger = logging.getLogger(__name__)
SAMPLE_ROWS = 10


def failure_message(result: DbtResult) -> str:
    """Tóm tắt lỗi dbt: tối đa 3 model/test lỗi, hoặc cuối log nếu dbt dừng trước khi chạy."""
    if result.timed_out:
        return result.log_tail
    failed = [r for r in result.results if r.status not in ("success", "pass")]
    if failed:
        return "\n".join(f"{r.unique_id} [{r.status}]: {r.message}" for r in failed[:3])
    return result.log_tail or "dbt build thất bại không rõ lý do."


def mart_sample(db: Path, target: str) -> tuple[int, list[dict]]:
    """Số dòng và vài dòng đầu của bảng đích (đã che PII) — để người không rành SQL xem kết quả mẫu."""
    with connect_read(db) as con:
        rows = con.execute(f'SELECT count(*) FROM main."{target}"').fetchone()[0]
        rel = con.sql(f'SELECT * FROM main."{target}" LIMIT {SAMPLE_ROWS}')
        sample = [dict(zip(rel.columns, [str(v) for v in row], strict=True)) for row in rel.fetchall()]
    return rows, mask_rows(sample)


def _summary(result: DbtResult) -> dict:
    tests = [r for r in result.results if r.unique_id.startswith("test.")]
    models = [r for r in result.results if r.unique_id.startswith("model.")]
    return {
        "models_ok": sum(r.status == "success" for r in models),
        "models_total": len(models),
        "tests_ok": sum(r.status == "pass" for r in tests),
        "tests_total": len(tests),
    }


def sandbox_run_node(state: PipelineState) -> dict:
    """Chạy dbt build; lỗi được ghi sổ lỗi và quay lại Codegen (tối đa N lần)."""
    workspace = Path(state["workspace"])
    write_generated_files(workspace, all_files(state))
    result = run_dbt_build(workspace)
    spec = spec_of(state)
    if not result.ok:
        message = failure_message(result)
        sandbox = {"passed": False, "error": message, **_summary(result)}
        return {"sandbox": sandbox, **register_failure(state, message, state["code_files"].get(mart_path(spec), ""))}
    rows, sample = mart_sample(sandbox_db(state), spec.target)
    return {"sandbox": {"passed": True, "error": "", "target_rows": rows, "sample": sample, **_summary(result)}}
