"""Khuôn dữ liệu vào/ra của API (chỉ tầng API; hợp đồng giữa các agent nằm ở `src/models/`)."""

from typing import Literal

from pydantic import BaseModel, Field

from src.models.schemas import RunRecord


class CreateRunBody(BaseModel):
    """Yêu cầu nghiệp vụ bằng lời."""

    request_text: str = Field(min_length=5, max_length=4000, examples=["Gộp đơn hàng 3 nguồn, tính doanh thu ngày"])


class AnswerBody(BaseModel):
    """Câu trả lời J1: id câu hỏi → lựa chọn (đúng nguyên văn một lựa chọn)."""

    answers: dict[str, str] = Field(min_length=1)


class PlanBody(BaseModel):
    """Quyết định J1b: đồng ý kế hoạch, hoặc yêu cầu sửa kèm ghi chú cho Planner."""

    decision: Literal["approve", "revise"]
    note: str = Field(default="", max_length=2000)


class ReviewBody(BaseModel):
    """Quyết định J2; từ chối thì phải có ghi chú cho Coder."""

    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=2000)


class RescueBody(BaseModel):
    """Cứu hộ: gợi ý cho Coder rồi thử lại, hoặc dừng."""

    action: Literal["retry", "abort"]
    hint: str = Field(default="", max_length=2000)


class ErrorFixBody(BaseModel):
    """Duyệt một mục sổ lỗi kèm cách sửa."""

    fix: str = Field(default="", max_length=2000)


class Accepted(BaseModel):
    """Đã nhận, đang chạy nền."""

    run_id: str
    status: str
    message: str


class RunDetail(BaseModel):
    """Chi tiết một lần chạy cho màn hình web."""

    record: RunRecord
    busy: bool
    pending: dict | None
    events: list[dict]
    spec: dict
    answered: list[dict]  # các câu J1 đã trả lời (câu hỏi + lựa chọn)
    evidence: dict
    optimization: dict
    sandbox: dict
    code_notes: list[str]
    test_notes: list[str]


class RunFiles(BaseModel):
    """Code + test hiện tại và bộ file của vòng duyệt trước (để xem diff)."""

    code_files: dict[str, str]
    test_files: dict[str, str]
    previous_files: dict[str, str]
