"""Hàm rẽ nhánh của graph (thuần, dễ test bằng parametrize)."""

from src.agents.state import PipelineState
from src.config import get_settings


def after_planner(state: PipelineState) -> str:
    """Planner lỗi dừng hẳn (ví dụ chưa có nguồn) → fail; còn lại → V0."""
    return "fail" if state.get("error") else "spec_check"


def after_spec_check(state: PipelineState) -> str:
    """V0 đạt → DE duyệt kế hoạch (J1b); còn câu hỏi → J1; lỗi khác → lập lại kế hoạch (có giới hạn)."""
    if not state.get("spec_errors"):
        return "plan_review"
    spec, rounds, limit = state.get("spec", {}), state.get("plan_rounds", 0), get_settings().max_plan_rounds
    if spec.get("unknowns") and spec.get("questions") and rounds <= limit:
        return "clarify"
    return "fail" if rounds >= limit else "planner"


def after_plan_review(state: PipelineState) -> str:
    """J1b: đồng ý → nạp nguồn; yêu cầu sửa → Planner lập lại (có giới hạn); quyết định không hợp lệ → hỏi lại."""
    review = state.get("plan_review", {})
    if review.get("invalid"):
        return "plan_review"
    if review.get("decision") == "approve":
        return "ingest"
    return "fail" if state.get("plan_reviews", 0) > get_settings().max_review_rounds else "planner"


def after_ingest(state: PipelineState) -> str:
    """Nạp nguồn lỗi → fail."""
    return "fail" if state.get("error") else "profiler"


def fix_route(state: PipelineState) -> str:
    """Sau lỗi V1/V2: cùng lỗi lặp 2 lần hoặc quá số lần sửa → cứu hộ; còn lại → Codegen sửa."""
    signatures = state.get("error_signatures", [])
    if signatures and signatures[-1] in signatures[:-1]:
        return "rescue"
    if state.get("fix_attempts", 0) >= get_settings().max_fix_attempts:
        return "rescue"
    return "codegen"


def after_safety(state: PipelineState) -> str:
    """V1 đạt → sandbox; không đạt → vòng sửa."""
    return "sandbox_run" if state.get("safety", {}).get("passed") else fix_route(state)


def after_sandbox(state: PipelineState) -> str:
    """V2 đạt → tối ưu (nếu chưa) hoặc đóng gói; không đạt → vòng sửa."""
    if not state.get("sandbox", {}).get("passed"):
        return fix_route(state)
    return "package" if state.get("optimization") else "optimizer"


def after_rescue(state: PipelineState) -> str:
    """Người dùng dừng → fail; có gợi ý → Codegen."""
    return "fail" if state.get("error") else "codegen"


def after_optimizer(state: PipelineState) -> str:
    """Đã có kết luận (ví dụ `skipped` sớm) → đóng gói; có đề xuất → V3."""
    return "package" if state.get("optimization") else "compare"


def after_compare(state: PipelineState) -> str:
    """Lệch → thử lại E4; áp dụng → kiểm tra lại V1+V2 với code mới; giữ nguyên → đóng gói."""
    report = state.get("optimization")
    if not report:
        return "optimizer"
    return "safety" if report.get("decision") == "applied" else "package"


def after_review(state: PipelineState) -> str:
    """Duyệt → hoàn tất; từ chối → Codegen (có giới hạn); quyết định không hợp lệ → hỏi lại."""
    review = state.get("review", {})
    if review.get("invalid"):
        return "review"
    if review.get("decision") == "approve":
        return "finalize"
    return "fail" if state.get("review_rounds", 0) >= get_settings().max_review_rounds else "codegen"
