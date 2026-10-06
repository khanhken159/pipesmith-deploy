"""State của LangGraph (TypedDict, total=False). Hợp đồng chi tiết ở `src/models/` lưu dưới dạng dict."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class PipelineState(TypedDict, total=False):
    """Bộ nhớ chung giữa các node. Mỗi node chỉ trả về các trường nó thay đổi."""

    # Đầu vào
    run_id: str  # id lần chạy (trùng thread_id của checkpointer)
    request_text: str  # yêu cầu bằng ngôn ngữ thường
    requester: str  # người tạo yêu cầu (không được tự duyệt)

    # E1 Planner ⇄ J1, V0
    source_catalog: list[dict]  # nguồn phát hiện được: schema thật + mẫu đã che PII
    answers: dict[str, str]  # câu trả lời làm rõ (J1): id câu hỏi → lựa chọn
    answered: list[dict]  # lịch sử J1 kèm nội dung câu hỏi: {id, question, answer} (để Planner hiểu ngữ cảnh)
    spec: dict  # PipelineSpec.model_dump()
    spec_errors: list[str]  # lỗi V0 (rỗng = đạt)
    plan_rounds: int  # số lần Planner đã chạy
    plan_review: dict  # quyết định J1b gần nhất: {"decision": "approve"|"revise", "note": "..."}
    plan_feedback: list[str]  # ghi chú DE yêu cầu sửa kế hoạch (Planner đọc khi lập lại)
    plan_reviews: int  # số lần DE yêu cầu sửa kế hoạch

    # E0, P, E2
    workspace: str  # đường dẫn workspace dbt
    row_counts: dict[str, int]  # số dòng mỗi bảng raw sau khi nạp
    profile: dict  # hồ sơ dữ liệu từng bảng raw
    datasets: dict[str, str]  # tên bộ dữ liệu thử → đường dẫn file DuckDB

    # E3, E3b, V1, V2
    code_files: dict[str, str]  # file do Codegen sinh: đường dẫn tương đối → nội dung
    code_notes: list[str]  # giải thích của Codegen (claimed)
    test_files: dict[str, str]  # file test do code + Testgen sinh
    test_notes: list[str]  # giải thích của Testgen (claimed)
    previous_files: dict[str, str]  # bộ file của vòng duyệt trước (để xem diff)
    safety: dict  # kết quả V1: {"passed": bool, "issues": [...]}
    sandbox: dict  # kết quả V2: {"passed", "error", "signature", "results", "sample", ...}
    fix_attempts: int  # số lần sửa sau lỗi V1/V2 trong vòng hiện tại
    error_signatures: list[str]  # chữ ký lỗi đã gặp (phát hiện lỗi lặp)
    rescue_hint: str  # gợi ý của con người ở bước cứu hộ
    rescue_count: int  # số lần cứu hộ

    # E4, V3
    optimization: dict  # OptimizationReport.model_dump(); rỗng = chưa tối ưu
    opt_attempts: int  # số lần đề xuất viết lại
    opt_candidate: dict  # đề xuất hiện tại của E4 chờ V3 kiểm tra

    # J2
    evidence: dict  # Evidence.model_dump(): measured tách claimed
    review: dict  # ReviewDecision.model_dump() gần nhất
    review_notes: list[str]  # ghi chú từ chối của Reviewer
    review_rounds: int  # số lần bị từ chối

    # Chung
    llm_usage: Annotated[list[dict], operator.add]  # mỗi lần gọi LLM thêm một mục (token, chi phí)
    status: str  # RunStatus hiện tại
    error: str  # lỗi dừng hẳn (FAILED)
