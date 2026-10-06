"""Cấu trúc dữ liệu cho DE: bảng, schema cột, lineage, khóa nối (suy ra bằng code, 0 token)."""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.agents import runner
from src.api.deps import run_or_404
from src.config import get_settings
from src.services.catalog import CatalogView, run_catalog
from src.services.jobs import get_jobs
from src.services.source_catalog import source_catalog

router = APIRouter(tags=["catalog"])


@router.get("/catalog/sources", response_model=CatalogView)
def sources_catalog() -> CatalogView:
    """Bảng nguồn hiện có (chưa chạy pipeline), nhóm theo hệ thống, kèm số dòng/% rỗng/trùng khóa + gợi ý khóa nối."""
    return source_catalog(get_settings().sources_dir)


@router.get("/runs/{run_id}/catalog", response_model=CatalogView)
def runs_catalog(run_id: str) -> CatalogView:
    """Toàn cảnh một lần chạy: raw → staging → mart, kiểu cột, % rỗng, khóa, lineage, JOIN thật trong SQL."""
    run_or_404(run_id)
    if get_jobs().busy(run_id):  # agent đang ghi sandbox: mở DuckDB lúc này làm hỏng bước chạy (khóa tệp)
        raise HTTPException(
            status_code=409, detail="Lần chạy đang xử lý, cấu trúc dữ liệu sẽ có khi tới bước chờ duyệt."
        )
    values = runner.get_values(run_id)
    if not values.get("workspace") or not Path(values["workspace"]).exists():
        raise HTTPException(status_code=409, detail="Lần chạy chưa nạp dữ liệu nên chưa có cấu trúc để hiển thị.")
    return run_catalog(values)
