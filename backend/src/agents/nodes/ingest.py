"""E0 Nhận nguồn (code): nạp các nguồn trong spec vào schema `raw` của sandbox DuckDB."""

import logging

import duckdb

from src.agents.nodes.common import SANDBOX_DB, spec_of
from src.agents.state import PipelineState
from src.agents.tools.dbt_tools import prepare_workspace, write_sources_yml
from src.agents.tools.duckdb_tools import SourceInfo, ingest_sources
from src.models.schemas import RunStatus

logger = logging.getLogger(__name__)


def ingest_node(state: PipelineState) -> dict:
    """Tạo workspace, nạp nguồn dạng bảng; nguồn ảnh/PDF chỉ được ghi nhận (OCR là phần mở rộng)."""
    wanted = {s.name for s in spec_of(state).sources}
    infos = [SourceInfo.model_validate(i) for i in state.get("source_catalog", []) if i["name"] in wanted]
    workspace = prepare_workspace(state["run_id"])
    try:
        counts = ingest_sources(workspace / SANDBOX_DB, infos)
    except (duckdb.Error, OSError) as exc:
        logger.error("ingest failed", extra={"error": str(exc)})
        return {"status": RunStatus.FAILED.value, "error": f"Không nạp được nguồn dữ liệu: {str(exc)[:200]}"}
    write_sources_yml(workspace, sorted(counts))
    return {"workspace": str(workspace), "row_counts": counts}
