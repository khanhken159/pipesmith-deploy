"""Mô tả ngắn gọn từng bước (✓/✗ + chi tiết) để in tiến trình cho người không rành kỹ thuật."""

from pydantic import BaseModel

NODE_LABELS = {
    "planner": "E1 Lập kế hoạch",
    "clarify": "J1 Hỏi làm rõ",
    "plan_review": "J1b Duyệt kế hoạch",
    "spec_check": "V0 Soát đặc tả",
    "ingest": "E0 Nhận nguồn",
    "profiler": "P  Soi dữ liệu",
    "mock_data": "E2 Dữ liệu thử",
    "codegen": "E3 Sinh code",
    "testgen": "E3b Sinh test",
    "safety": "V1 An toàn",
    "sandbox_run": "V2 Chạy sandbox",
    "rescue": "J  Cứu hộ",
    "optimizer": "E4 Tối ưu",
    "compare": "V3 Đối chiếu",
    "package": "Đóng gói bản duyệt",
    "review": "J2 Duyệt",
    "finalize": "Hoàn tất",
    "fail": "Dừng",
}


class StepEvent(BaseModel):
    """Một bước đã chạy xong."""

    node: str
    label: str
    ok: bool
    detail: str
    seconds: float
    tokens: int


def _detail_spec(update: dict) -> tuple[bool, str]:
    errors = update.get("spec_errors", [])
    return (not errors, "đạt" if not errors else errors[0][:120])


def _detail_safety(update: dict) -> tuple[bool, str]:
    safety = update.get("safety", {})
    issues = safety.get("issues", [])
    return safety.get(
        "passed", False
    ), "không phát hiện vấn đề" if not issues else f"{len(issues)} vấn đề: {issues[0][:100]}"


def _detail_sandbox(update: dict) -> tuple[bool, str]:
    box = update.get("sandbox", {})
    if box.get("passed"):
        return (
            True,
            f"{box.get('models_ok')}/{box.get('models_total')} model, {box.get('tests_ok')}/{box.get('tests_total')} test đạt",
        )
    return False, (box.get("error") or "lỗi").splitlines()[0][:120]


def _detail_compare(update: dict) -> tuple[bool, str]:
    report = update.get("optimization") or {}
    if not report:
        return False, "ứng viên chưa đạt, thử ứng viên kế tiếp"
    return True, f"{report.get('decision')}: {report.get('reason', '')[:110]}"


def _detail_optimizer(update: dict) -> tuple[bool, str]:
    if update.get("optimization"):
        return True, update["optimization"].get("reason", "")[:120]
    candidate = update.get("opt_candidate", {})
    before = candidate.get("before", {}).get("median_ms")
    found = len(candidate.get("findings", []))
    return True, f"{found} dấu hiệu chậm, baseline {before} ms, ứng viên từ {candidate.get('source', '?')}"


DETAILS = {
    "spec_check": _detail_spec,
    "safety": _detail_safety,
    "sandbox_run": _detail_sandbox,
    "compare": _detail_compare,
    "optimizer": _detail_optimizer,
}


def _detail_default(node: str, update: dict) -> tuple[bool, str]:
    if update.get("error"):
        return False, update["error"][:120]
    simple = {
        "ingest": lambda u: ", ".join(f"{k}: {v} dòng" for k, v in u.get("row_counts", {}).items()),
        "profiler": lambda u: f"{len(u.get('profile', {}))} bảng",
        "mock_data": lambda u: ", ".join(u.get("datasets", {})),
        "codegen": lambda u: f"{len(u.get('code_files', {}))} file",
        "testgen": lambda u: f"{len(u.get('test_files', {}))} file test",
        "planner": lambda u: (
            f"bảng đích {u.get('spec', {}).get('target', '?')}, mode {u.get('spec', {}).get('mode', '?')}"
        ),
    }
    return True, simple[node](update) if node in simple else ""


def describe(node: str, update: dict, seconds: float) -> StepEvent:
    """Chuyển một cập nhật của node thành dòng tiến trình."""
    ok, detail = DETAILS[node](update) if node in DETAILS else _detail_default(node, update)
    tokens = sum(u.get("input_tokens", 0) + u.get("output_tokens", 0) for u in update.get("llm_usage", []))
    return StepEvent(
        node=node, label=NODE_LABELS.get(node, node), ok=ok, detail=detail, seconds=round(seconds, 2), tokens=tokens
    )
