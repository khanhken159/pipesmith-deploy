"""Hợp đồng bằng chứng gửi Reviewer: `measured` (code đo) tách riêng `claimed` (LLM nói)."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class MeasuredItem(BaseModel):
    """Một kết quả do V-node (code tất định) đo."""

    node: str = Field(..., description="V-node đã đo, ví dụ V2 sandbox_run")
    check: str
    result: str
    passed: bool | None = None


class Evidence(BaseModel):
    """Gói bằng chứng: hai phần luôn tách biệt."""

    measured: list[MeasuredItem] = Field(default_factory=list)
    claimed: list[str] = Field(default_factory=list, description="Lời giải thích của LLM, chưa kiểm chứng")


class Finding(BaseModel):
    """Một dấu hiệu query chậm do sqlglot/EXPLAIN phát hiện."""

    rule: str
    message: str


class QueryMetrics(BaseModel):
    """Số đo thời gian chạy (trung vị của N lần, sau 1 lần khởi động)."""

    median_ms: float
    runs: int
    peak_memory_mb: float | None = None


class DatasetCheck(BaseModel):
    """Kết quả đối chiếu hai query trên một bộ dữ liệu."""

    dataset: str
    equal: bool
    detail: str = ""


class OptimizationReport(BaseModel):
    """Báo cáo E4 + V3: số liệu trước/sau và quyết định áp dụng hay giữ nguyên."""

    original_sql: str
    proposed_sql: str = ""
    findings: list[Finding] = Field(default_factory=list)
    before: QueryMetrics | None = None
    after: QueryMetrics | None = None
    improvement_pct: float | None = None
    decision: Literal["applied", "skipped"] = "skipped"
    reason: str = ""
    attempts: int = 0
    equivalence: list[DatasetCheck] = Field(default_factory=list)
    llm_cost_usd: float = 0.0
    explanation: str = Field(default="", description="Giải thích của LLM (claimed)")
    warehouse_hints: list[str] = Field(
        default_factory=list, description="Gợi ý chỉ áp dụng cho kho khác, không thực thi"
    )


class ReviewDecision(BaseModel):
    """Quyết định của Reviewer ở J2."""

    run_id: str
    reviewer: str
    decision: Literal["approve", "reject"]
    note: str = ""
    decided_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class ErrorEntry(BaseModel):
    """Một mục trong sổ lỗi; chỉ mục `approved=True` mới được gợi ý cho Codegen."""

    id: int | None = None
    code: str
    signature: str
    description: str
    cause: str = ""
    fix: str = ""
    sql_before: str = ""
    sql_after: str = ""
    occurrences: int = 1
    approved: bool = False
