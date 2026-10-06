"""Gói "Pull Request" để duyệt: bằng chứng tách `measured` (code đo) và `claimed` (LLM nói)."""

from pathlib import Path

from src.agents.state import PipelineState
from src.models.evidence import Evidence, MeasuredItem
from src.models.schemas import RunStatus


def _spec_items(state: PipelineState) -> list[MeasuredItem]:
    spec = state.get("spec", {})
    rows = ", ".join(f"{k}: {v}" for k, v in state.get("row_counts", {}).items())
    return [
        MeasuredItem(node="V0 Soát spec", check="Đặc tả đủ trường, không còn điểm chưa rõ", result="Đạt", passed=True),
        MeasuredItem(
            node="V0 Soát spec", check="Chế độ pipeline", result=f"{spec.get('mode')} — {spec.get('mode_reason')}"
        ),
        MeasuredItem(node="E0 Nhận nguồn", check="Số dòng nạp vào sandbox", result=rows or "—"),
    ]


def _run_items(state: PipelineState) -> list[MeasuredItem]:
    sandbox, safety = state.get("sandbox", {}), state.get("safety", {})
    return [
        MeasuredItem(
            node="V1 An toàn",
            check="Lệnh nguy hiểm, tên bảng/cột bịa",
            result="Không phát hiện",
            passed=safety.get("passed"),
        ),
        MeasuredItem(
            node="V2 Sandbox",
            check="dbt build (model)",
            passed=sandbox.get("passed"),
            result=f"{sandbox.get('models_ok', 0)}/{sandbox.get('models_total', 0)} model chạy được",
        ),
        MeasuredItem(
            node="V2 Sandbox",
            check="dbt test (đối soát, grain, not_null)",
            passed=sandbox.get("passed"),
            result=f"{sandbox.get('tests_ok', 0)}/{sandbox.get('tests_total', 0)} test đạt",
        ),
        MeasuredItem(node="V2 Sandbox", check="Số dòng bảng đích", result=str(sandbox.get("target_rows", "—"))),
        MeasuredItem(
            node="Vòng sửa",
            check="Số lần sửa / cứu hộ",
            result=f"{state.get('fix_attempts', 0)} lần sửa, {state.get('rescue_count', 0)} lần cứu hộ",
        ),
    ]


def _optimization_items(state: PipelineState) -> list[MeasuredItem]:
    report = state.get("optimization", {})
    if not report:
        return []
    items = [
        MeasuredItem(node="V3 Đối chiếu", check=f"Kết quả bộ '{c['dataset']}'", result=c["detail"], passed=c["equal"])
        for c in report.get("equivalence", [])
    ]
    before, after = report.get("before") or {}, report.get("after") or {}
    timing = f"{before.get('median_ms', '—')} ms → {after.get('median_ms', '—')} ms" if before else "—"
    items.append(MeasuredItem(node="E4/V3 Tối ưu", check="Thời gian trung vị trên bộ large", result=timing))
    items.append(
        MeasuredItem(node="E4/V3 Tối ưu", check="Quyết định", result=f"{report['decision']}: {report['reason']}")
    )
    return items


def build_evidence(state: PipelineState) -> Evidence:
    """Bằng chứng đầy đủ cho Reviewer."""
    claimed = [*state.get("code_notes", []), *state.get("test_notes", [])]
    explanation = state.get("optimization", {}).get("explanation")
    if explanation:
        claimed.append(f"Optimizer: {explanation}")
    measured = _spec_items(state) + _run_items(state) + _optimization_items(state)
    return Evidence(measured=measured, claimed=claimed)


def _plan_lines(spec: dict) -> list[str]:
    """Kế hoạch DE đã duyệt ở J1b (lời LLM) — giúp người xem PR hiểu vì sao code viết như vậy."""
    steps = spec.get("plan") or []
    if not steps:
        return []
    numbered = [
        f"{i}. **{s.get('title')}** — {s.get('detail')} _(Vì sao: {s.get('reason')})_" for i, s in enumerate(steps, 1)
    ]
    return ["## Kế hoạch đã duyệt (J1b)", "", spec.get("plan_summary", ""), "", *numbered, ""]


def write_pr_description(state: PipelineState, evidence: Evidence) -> None:
    """Ghi PULL_REQUEST.md vào workspace (mô tả để Engineer mở PR thật sau khi được duyệt)."""
    lines = [
        f"# Pipeline: {state.get('spec', {}).get('target')}",
        "",
        f"Yêu cầu: {state.get('request_text')}",
        "",
        *_plan_lines(state.get("spec", {})),
        "## Code đo (measured)",
        *[f"- [{m.node}] {m.check}: {m.result}" for m in evidence.measured],
        "",
        "## LLM nói (claimed, chưa kiểm chứng)",
        *[f"- {c}" for c in evidence.claimed],
        "",
    ]
    (Path(state["workspace"]) / "PULL_REQUEST.md").write_text("\n".join(lines), encoding="utf-8")


def package_node(state: PipelineState) -> dict:
    """Đóng gói bằng chứng, chuyển sang chờ duyệt."""
    evidence = build_evidence(state)
    write_pr_description(state, evidence)
    return {"evidence": evidence.model_dump(), "status": RunStatus.WAITING_REVIEW.value}
