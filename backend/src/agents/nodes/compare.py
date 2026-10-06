"""V3 Đối chiếu (code thuần, không bao giờ hỏi LLM "hai query có tương đương không").

So kết quả hai chiều, không phụ thuộc thứ tự dòng, có sai số số thực; chỉ khi giống hệt trên MỌI bộ dữ liệu
mới đo thời gian và quyết định áp dụng hay giữ nguyên.
"""

import math
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

from src.agents.nodes.common import mart_path, spec_of
from src.agents.state import PipelineState
from src.agents.tools.duckdb_tools import QueryResult, benchmark_query, run_query
from src.agents.tools.sql_tools import same_query, to_dbt_refs
from src.config import get_settings
from src.models.evidence import DatasetCheck, OptimizationReport, QueryMetrics
from src.services.cost import compute_cost_usd

EQUIVALENCE_DATASETS = ("small", "dirty", "empty", "few", "dupkeys")
BENCH_DATASET = "large"


def _normalize(value: object, digits: int) -> object:
    if isinstance(value, float | Decimal):
        number = float(value)
        return "nan" if math.isnan(number) else round(number, digits)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def compare_results(a: QueryResult, b: QueryResult, abs_tol: float) -> tuple[bool, str]:
    """So hai kết quả: tên cột, kiểu cột, số dòng, rồi tập dòng hai chiều (bỏ qua thứ tự)."""
    if a.columns != b.columns:
        return False, f"Khác cột: {a.columns} ≠ {b.columns}"
    if a.types != b.types:
        return False, f"Khác kiểu cột: {a.types} ≠ {b.types}"
    if len(a.rows) != len(b.rows):
        return False, f"Khác số dòng: {len(a.rows)} ≠ {len(b.rows)}"
    digits = max(0, -math.floor(math.log10(abs_tol))) if abs_tol > 0 else 12
    rows_a = Counter(tuple(_normalize(v, digits) for v in row) for row in a.rows)
    rows_b = Counter(tuple(_normalize(v, digits) for v in row) for row in b.rows)
    only_a, only_b = rows_a - rows_b, rows_b - rows_a
    if only_a or only_b:
        return False, f"{sum(only_a.values())} dòng chỉ có ở bản gốc, {sum(only_b.values())} dòng chỉ có ở bản mới"
    return True, f"Giống hệt ({len(a.rows)} dòng)"


def check_on_dataset(original: str, candidate: str, db: Path) -> tuple[bool, str]:
    """Chạy cả hai query trên một bộ dữ liệu và so sánh."""
    try:
        before = run_query(db, original)
        after = run_query(db, candidate)
    except duckdb.Error as exc:
        return False, f"Lỗi khi chạy: {str(exc).splitlines()[0][:200]}"
    return compare_results(before, after, get_settings().compare_abs_tol)


def check_equivalence(original: str, candidate: str, datasets: dict[str, str]) -> list[DatasetCheck]:
    """Đối chiếu trên mọi bộ dữ liệu kiểm đúng (small, dirty, rỗng, ít dòng, khóa trùng)."""
    checks = []
    for name in EQUIVALENCE_DATASETS:
        if name in datasets:
            equal, detail = check_on_dataset(original, candidate, Path(datasets[name]))
            checks.append(DatasetCheck(dataset=name, equal=equal, detail=detail))
    return checks


def decide(before: QueryMetrics, after: QueryMetrics, llm_cost_usd: float) -> tuple[str, str, float]:
    """Cổng "đáng tối ưu không": lợi ích tối thiểu + hòa vốn trong 12 tháng. Trả (quyết định, lý do, %)."""
    settings = get_settings()
    gain = round(100 * (before.median_ms - after.median_ms) / before.median_ms, 1) if before.median_ms else 0.0
    if gain < settings.opt_min_gain_pct:
        change = f"chậm hơn {-gain}%" if gain < 0 else f"chỉ nhanh hơn {gain}%"
        return "skipped", f"Bản viết lại {change} (ngưỡng {settings.opt_min_gain_pct}%): giữ nguyên bản gốc.", gain
    saved_s = (before.median_ms - after.median_ms) / 1000 * settings.opt_runs_per_month
    saved_usd = compute_cost_usd(saved_s, settings.opt_compute_cost_per_hour_usd)
    if llm_cost_usd > 0 and saved_usd * 12 < llm_cost_usd:
        return "skipped", f"Nhanh hơn {gain}% nhưng tiết kiệm/năm < chi phí tối ưu ({llm_cost_usd:.4f} USD).", gain
    return (
        "applied",
        f"Nhanh hơn {gain}% (≥ {settings.opt_min_gain_pct}%), kết quả giống hệt trên mọi bộ dữ liệu.",
        gain,
    )


def build_report(candidate: dict, checks: list[DatasetCheck], after: QueryMetrics | None) -> OptimizationReport:
    """Gộp đề xuất + kết quả đối chiếu + số đo thành báo cáo (chưa có quyết định)."""
    return OptimizationReport(
        original_sql=candidate["original_sql"],
        proposed_sql=candidate["sql"],
        findings=candidate.get("findings", []),
        before=candidate.get("before"),
        after=after,
        attempts=candidate.get("attempt", 1),
        equivalence=checks,
        llm_cost_usd=candidate.get("llm_cost_usd", 0.0),
        explanation=candidate.get("explanation", ""),
        warehouse_hints=candidate.get("warehouse_hints", []),
    )


def check_assumptions(candidate: dict, datasets: dict[str, str]) -> list[DatasetCheck]:
    """Chạy SQL kiểm chứng giả định của luật trên mọi bộ dữ liệu; lỗi khi chạy = coi như giả định sai."""
    checks = []
    for assumption in candidate.get("assumptions", []):
        for name in EQUIVALENCE_DATASETS:
            if name not in datasets or not assumption.get("check_sql"):
                continue
            try:
                violations = run_query(Path(datasets[name]), assumption["check_sql"]).rows[0][0]
            except (duckdb.Error, IndexError) as exc:
                violations = f"không kiểm chứng được ({str(exc).splitlines()[0][:80]})"
            ok = violations == 0
            detail = assumption["text"] + ("" if ok else f" — vi phạm: {violations}")
            checks.append(DatasetCheck(dataset=f"giả định@{name}", equal=ok, detail=detail))
    return checks


def _early_reject(candidate: dict) -> OptimizationReport | None:
    if candidate.get("invalid"):
        checks = [DatasetCheck(dataset="V1", equal=False, detail=candidate["invalid"])]
        return build_report(candidate, checks, None).model_copy(update={"reason": "Bản viết lại không qua V1."})
    if same_query(candidate["original_sql"], candidate["sql"]):
        checks = [DatasetCheck(dataset="—", equal=True, detail="Đề xuất giống bản gốc")]
        reason = "Optimizer không đề xuất thay đổi nào an toàn; giữ nguyên bản gốc."
        return build_report(candidate, checks, None).model_copy(update={"reason": reason})
    return None


def evaluate_candidate(candidate: dict, datasets: dict[str, str]) -> OptimizationReport:
    """V1 → đối chiếu kết quả → kiểm chứng giả định → (nếu đều đạt) đo trên bộ `bench` (mặc định large) → quyết định."""
    rejected = _early_reject(candidate)
    if rejected is not None:
        return rejected
    checks = check_equivalence(candidate["original_sql"], candidate["sql"], datasets)
    if all(c.equal for c in checks):
        checks += check_assumptions(candidate, datasets)
    failed = [c for c in checks if not c.equal]
    if failed:
        what = "Giả định không đúng" if failed[0].dataset.startswith("giả định") else "Kết quả lệch"
        reason = f"{what} trên bộ: {', '.join(c.dataset.removeprefix('giả định@') for c in failed)}."
        return build_report(candidate, checks, None).model_copy(update={"reason": reason})
    bench = Path(datasets[candidate.get("bench", BENCH_DATASET)])
    after = benchmark_query(bench, candidate["sql"], get_settings().opt_bench_runs)
    report = build_report(candidate, checks, after)
    decision, reason, gain = decide(QueryMetrics.model_validate(candidate["before"]), after, report.llm_cost_usd)
    return report.model_copy(update={"decision": decision, "reason": reason, "improvement_pct": gain})


def _staging_models(state: PipelineState) -> list[str]:
    return [p.rsplit("/", 1)[-1].removesuffix(".sql") for p in state.get("code_files", {}) if p.startswith("models/")]


def _applied_code(state: PipelineState, report: OptimizationReport) -> dict[str, str]:
    path = mart_path(spec_of(state))
    header = "-- Bản đã tối ưu (E4), đối chiếu giống hệt bản gốc (V3)\n"
    return {**state["code_files"], path: header + to_dbt_refs(report.proposed_sql, _staging_models(state)) + "\n"}


def compare_node(state: PipelineState) -> dict:
    """V3: ứng viên không đạt → báo lý do cho E4 thử ứng viên kế (trong giới hạn); `applied` → ghi vào model đích."""
    candidate = state.get("opt_candidate", {})
    report = evaluate_candidate(candidate, state.get("datasets", {}))
    history = [*candidate.get("history", []), f"[{candidate.get('source', '?')}] {report.reason}"]
    if report.decision != "applied" and state.get("opt_attempts", 0) < get_settings().opt_max_attempts:
        return {"opt_candidate": {**candidate, "feedback": report.reason, "history": history}}
    if report.decision != "applied":
        summary = f"Đã thử {len(history)} đề xuất, không đề xuất nào đạt: " + " | ".join(history)
        report = report.model_copy(update={"decision": "skipped", "reason": summary})
    update: dict = {"optimization": report.model_dump(mode="json")}
    if report.decision == "applied":
        update["code_files"] = _applied_code(state, report)
    return update
