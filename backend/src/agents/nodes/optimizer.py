"""E4 Optimizer: phát hiện dấu hiệu chậm (code) → đo baseline → đề xuất viết lại → (V3 kiểm tra).

Thứ tự ứng viên: luật tất định (0 token) → sqlglot.optimizer (0 token) → LLM. LLM chỉ được gọi khi hai nguồn
tất định không còn ứng viên. Mọi ứng viên đều qua V1 (an toàn, tên bảng/cột) trước khi chạy.
"""

import logging
from pathlib import Path

import duckdb
from pydantic import BaseModel, Field

from src.agents.nodes.common import mart_path, spec_of
from src.agents.nodes.compare import BENCH_DATASET, evaluate_candidate
from src.agents.nodes.safety import check_sql
from src.agents.state import PipelineState
from src.agents.tools.duckdb_tools import benchmark_query, explain_analyze, materialize_views, read_catalog
from src.agents.tools.rewrite_rules import rules_candidate, sqlglot_candidate
from src.agents.tools.slow_patterns import detect_slow_patterns
from src.agents.tools.sql_tools import SqlCheckError, render_dbt_sql
from src.config import get_settings
from src.models.evidence import Finding, OptimizationReport
from src.models.schemas import LLMUsage
from src.services.llm import LLMOutputError, call_llm, parse_json_output, to_json

logger = logging.getLogger(__name__)
EXPLAIN_LIMIT = 3000
DETERMINISTIC_SOURCES = {"rules": rules_candidate, "sqlglot": sqlglot_candidate}


class ProposalInput(BaseModel):
    """Đầu vào cho bước đề xuất viết lại."""

    sql: str
    findings: list[Finding]
    bench_db: str
    feedback: str = Field(default="", description="Vì sao ứng viên trước bị loại (phản hồi cho lần sau)")
    tried: list[str] = Field(default_factory=list, description="Nguồn tất định đã thử")


def validate_candidate(candidate: dict, db: Path) -> dict:
    """V1 cho bản viết lại: lỗi → đánh dấu `invalid` (V3 sẽ loại)."""
    if candidate.get("invalid"):
        return candidate
    issues = check_sql(candidate["sql"], read_catalog(db))[0] if candidate["sql"] else ["Không có SQL đề xuất."]
    return {**candidate, "invalid": "; ".join(issues)} if issues else candidate


def llm_rewrite(job: ProposalInput) -> tuple[dict, LLMUsage]:
    """Gọi LLM đề xuất viết lại dựa trên dấu hiệu chậm + kế hoạch thực thi + phản hồi lần trước."""
    db = Path(job.bench_db)
    findings = [f.model_dump() for f in job.findings]
    if job.feedback:
        findings.append({"rule": "previous_attempt_rejected", "message": job.feedback})
    response = call_llm(
        "optimizer",
        {
            "sql": job.sql,
            "findings": to_json(findings),
            "explain": explain_analyze(db, job.sql)[:EXPLAIN_LIMIT],
            "schema": to_json(read_catalog(db)),
        },
    )
    try:
        data = parse_json_output(response.text)
        candidate = {
            "sql": str(data.get("sql", "")).strip().rstrip(";"),
            "explanation": str(data.get("explanation", "")),
            "warehouse_hints": [str(h) for h in data.get("warehouse_hints") or []],
        }
    except LLMOutputError as exc:
        candidate = {"sql": "", "explanation": "", "warehouse_hints": [], "invalid": str(exc)}
    return {**candidate, "source": "llm", "assumptions": []}, response.usage


def next_proposal(job: ProposalInput) -> tuple[dict, LLMUsage | None, list[str]]:
    """Ứng viên kế tiếp: nguồn tất định chưa thử trước, hết thì LLM. Trả (ứng viên, usage LLM, nguồn đã thử)."""
    tried, db = list(job.tried), Path(job.bench_db)
    for source, build in DETERMINISTIC_SOURCES.items():
        if source in tried:
            continue
        tried.append(source)
        found = build(job.sql, read_catalog(db))
        if found is not None:
            candidate = {**found.model_dump(), "explanation": f"[{source}] {found.explanation}", "warehouse_hints": []}
            return validate_candidate(candidate, db), None, tried
    candidate, usage = llm_rewrite(job)
    return validate_candidate(candidate, db), usage, tried


def prepare_datasets(state: PipelineState) -> None:
    """Tạo bảng staging (đã qua V1, V2) trên mọi bộ dữ liệu thử để chạy model đích."""
    staging = {
        p.rsplit("/", 1)[-1].removesuffix(".sql"): render_dbt_sql(sql)
        for p, sql in sorted(state.get("code_files", {}).items())
        if p.startswith("models/staging/")
    }
    for db in state.get("datasets", {}).values():
        materialize_views(Path(db), staging)


def skipped_report(sql: str, reason: str) -> dict:
    """Báo cáo `skipped` (hợp lệ: tối ưu chỉ khi đáng)."""
    return OptimizationReport(original_sql=sql, decision="skipped", reason=reason).model_dump(mode="json")


def _first_attempt(state: PipelineState, sql: str) -> dict:
    prepare_datasets(state)
    bench_db = Path(state["datasets"][BENCH_DATASET])
    before = benchmark_query(bench_db, sql, get_settings().opt_bench_runs)
    return {"original_sql": sql, "before": before.model_dump(), "llm_cost_usd": 0.0, "tried": [], "history": []}


def optimizer_node(state: PipelineState) -> dict:
    """E4: không có dấu hiệu chậm → `skipped`; ngược lại tạo ứng viên kế tiếp cho V3 kiểm tra."""
    sql = render_dbt_sql(state["code_files"][mart_path(spec_of(state))])
    findings = detect_slow_patterns(sql)
    if not findings:
        return {"optimization": skipped_report(sql, "Không phát hiện dấu hiệu query chậm; giữ nguyên.")}
    try:
        base = state.get("opt_candidate") or _first_attempt(state, sql)
    except (duckdb.Error, SqlCheckError) as exc:
        logger.warning("optimizer baseline failed", extra={"error": str(exc)})
        return {"optimization": skipped_report(sql, f"Không đo được baseline: {str(exc)[:200]}")}
    job = ProposalInput(
        sql=sql,
        findings=findings,
        bench_db=state["datasets"][BENCH_DATASET],
        feedback=base.get("feedback", ""),
        tried=base.get("tried", []),
    )
    proposal, usage, tried = next_proposal(job)
    attempt = state.get("opt_attempts", 0) + 1
    cost = base.get("llm_cost_usd", 0.0) + (usage.cost_usd if usage else 0.0)
    candidate = {
        **base,
        **proposal,
        "tried": tried,
        "findings": [f.model_dump() for f in findings],
        "attempt": attempt,
        "llm_cost_usd": cost,
    }
    candidate.pop("feedback", None)
    update = {"opt_candidate": candidate, "opt_attempts": attempt}
    return {**update, "llm_usage": [usage.model_dump()]} if usage else update


class OptimizeJob(BaseModel):
    """Lệnh `optimize` chạy riêng E4 + V3 trên các bộ dữ liệu có sẵn."""

    sql: str
    datasets: dict[str, str]
    bench: str = BENCH_DATASET


def optimize_standalone(job: OptimizeJob) -> tuple[OptimizationReport, list[LLMUsage]]:
    """Vòng E4 → V3 không cần graph (CLI `optimize`): dừng ở ứng viên đầu tiên được áp dụng."""
    findings = detect_slow_patterns(job.sql)
    if not findings:
        return OptimizationReport.model_validate(skipped_report(job.sql, "Không phát hiện dấu hiệu query chậm.")), []
    bench_db = Path(job.datasets[job.bench])
    base = {
        "original_sql": job.sql,
        "findings": [f.model_dump() for f in findings],
        "llm_cost_usd": 0.0,
        "bench": job.bench,
        "before": benchmark_query(bench_db, job.sql, get_settings().opt_bench_runs).model_dump(),
    }
    usages: list[LLMUsage] = []
    proposal_job = ProposalInput(sql=job.sql, findings=findings, bench_db=str(bench_db))
    report = OptimizationReport(original_sql=job.sql)
    for attempt in range(1, get_settings().opt_max_attempts + 1):
        proposal, usage, tried = next_proposal(proposal_job)
        usages += [usage] if usage else []
        base["llm_cost_usd"] += usage.cost_usd if usage else 0.0
        report = evaluate_candidate({**base, **proposal, "attempt": attempt}, job.datasets)
        if report.decision == "applied":
            break
        proposal_job = proposal_job.model_copy(update={"tried": tried, "feedback": report.reason})
    return report, usages
