"""Hợp đồng `PipelineSpec` (đầu ra của Planner) và hàm tất định `decide_mode`."""

from enum import StrEnum

from pydantic import BaseModel, Field

TABULAR_KINDS = {"csv", "json", "parquet", "sqlite"}


class PipelineMode(StrEnum):
    """Kiểu pipeline: biến đổi trong kho (ELT), trước khi nạp (ETL) hoặc kết hợp."""

    ELT = "ELT"
    ETL = "ETL"
    HYBRID = "HYBRID"


class SourceRef(BaseModel):
    """Một nguồn dữ liệu được dùng trong pipeline."""

    name: str = Field(..., description="Tên bảng raw, ví dụ `shopee_orders`")
    kind: str = Field(..., description="csv | json | parquet | sqlite | image | pdf")
    path: str = Field(default="", description="Đường dẫn file nguồn")


class Metric(BaseModel):
    """Chỉ số cần tính, mô tả bằng lời thường."""

    name: str
    description: str


class OutputColumn(BaseModel):
    """Một cột của bảng đích — hợp đồng chung cho Codegen và Testgen."""

    name: str
    type: str = Field(..., description="Kiểu SQL, ví dụ DATE, BIGINT, VARCHAR")
    description: str = ""
    references: str = Field(default="", description="Khóa ngoại dạng `bang.cot` nếu có")


class ClarifyQuestion(BaseModel):
    """Câu hỏi làm rõ dạng trắc nghiệm (J1)."""

    id: str
    question: str
    options: list[str] = Field(..., min_length=2)


class PlanStep(BaseModel):
    """Một bước trong kế hoạch, viết bằng lời thường để DE duyệt trước khi sinh code (J1b)."""

    title: str = Field(..., description="Tên bước ngắn gọn, ví dụ 'Làm sạch đơn Shopee'")
    detail: str = Field(default="", description="Làm gì, với bảng/cột nào")
    reason: str = Field(default="", description="Vì sao cần bước này (dựa trên yêu cầu hoặc dữ liệu thấy được)")


class ModeSignals(BaseModel):
    """Tín hiệu để chọn ELT/ETL. LLM chỉ giúp rút tín hiệu, quyết định là code."""

    restricted_pii: bool = Field(default=False, description="Có dữ liệu cá nhân không được vào kho nguyên bản")
    non_tabular_source: bool = Field(default=False, description="Có nguồn không phải bảng (ảnh, PDF)")
    tabular_source: bool = Field(default=True, description="Có nguồn dạng bảng")
    small_subset_of_large: bool = Field(default=False, description="Chỉ cần phần rất nhỏ của dữ liệu lớn")


class PipelineSpec(BaseModel):
    """Đặc tả pipeline do Planner lập; V0 soát trước khi sinh code."""

    request_text: str
    mode: PipelineMode = PipelineMode.ELT
    mode_reason: str = ""
    sources: list[SourceRef] = Field(default_factory=list)
    target: str = Field(default="", description="Tên bảng đích (model dbt cuối)")
    grain: list[str] = Field(default_factory=list, description="Các cột xác định một dòng của bảng đích")
    output_columns: list[OutputColumn] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    questions: list[ClarifyQuestion] = Field(default_factory=list)
    decisions: dict[str, str] = Field(default_factory=dict, description="Câu trả lời J1: id câu hỏi → lựa chọn")
    signals: ModeSignals = Field(default_factory=ModeSignals)
    plan_summary: str = Field(default="", description="Tóm tắt kế hoạch 1–3 câu cho người không rành kỹ thuật")
    plan: list[PlanStep] = Field(default_factory=list, description="Các bước sẽ làm, có giải thích (DE duyệt ở J1b)")


def signals_from_sources(sources: list[SourceRef], signals: ModeSignals) -> ModeSignals:
    """Tính lại tín hiệu loại nguồn bằng code (không tin LLM cho phần đo được)."""
    kinds = {s.kind for s in sources}
    return signals.model_copy(
        update={
            "tabular_source": bool(kinds & TABULAR_KINDS),
            "non_tabular_source": bool(kinds - TABULAR_KINDS),
        }
    )


def decide_mode(signals: ModeSignals) -> tuple[PipelineMode, str]:
    """Chọn ELT/ETL/HYBRID theo luật cố định; trả về (mode, lý do)."""
    if signals.non_tabular_source and signals.tabular_source:
        return PipelineMode.HYBRID, "Có nguồn không phải bảng (xử lý ETL cục bộ) và nguồn dạng bảng (ELT)."
    if signals.non_tabular_source:
        return PipelineMode.ETL, "Nguồn không phải bảng (ảnh/PDF) phải trích xuất trước khi nạp."
    if signals.restricted_pii:
        return PipelineMode.ETL, "Có dữ liệu cá nhân không được nạp nguyên bản vào kho; phải che/lọc trước."
    if signals.small_subset_of_large:
        return PipelineMode.ETL, "Chỉ cần một phần rất nhỏ của dữ liệu lớn; lọc trước khi nạp để tiết kiệm."
    return PipelineMode.ELT, "Mặc định ELT: nạp dữ liệu thô vào kho rồi biến đổi bằng dbt."
