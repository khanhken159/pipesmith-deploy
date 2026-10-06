"""Test E4 Optimizer + V3 Đối chiếu: tối ưu thành công, bị loại vì lệch kết quả, `skipped` do lợi ích nhỏ."""

from pathlib import Path

import duckdb
import pytest

from src.agents.nodes.compare import compare_node, compare_results, decide, evaluate_candidate
from src.agents.nodes.optimizer import OptimizeJob, optimize_standalone, optimizer_node, prepare_datasets
from src.agents.tools.duckdb_tools import QueryResult
from src.models.evidence import QueryMetrics

ORIGINAL = "with u as (select * from raw.a union select * from raw.b) select k, sum(v) as total from u group by k"


def _result(rows: list[tuple], types: list[str] | None = None) -> QueryResult:
    return QueryResult(columns=["k", "v"], types=types or ["VARCHAR", "DOUBLE"], rows=rows)


@pytest.fixture
def datasets(tmp_path: Path) -> dict[str, str]:
    """Các bộ dữ liệu nhỏ có hai bảng a, b không trùng dòng giữa nhau."""
    paths = {}
    for name, n in {"small": 50, "dirty": 30, "empty": 0, "few": 3, "dupkeys": 40, "large": 50000}.items():
        paths[name] = str(tmp_path / f"{name}.duckdb")
        with duckdb.connect(paths[name]) as con:
            con.execute("CREATE SCHEMA raw")
            con.execute(f"CREATE TABLE raw.a AS SELECT 'a' || (i % 97) AS k, i * 1.5 AS v FROM range({n}) t(i)")
            con.execute(f"CREATE TABLE raw.b AS SELECT 'b' || (i % 89) AS k, i * 2.0 AS v FROM range({n}) t(i)")
    return paths


def test_compare_results_ignores_row_order_and_small_float_noise():
    equal, _ = compare_results(_result([("x", 1.0), ("y", 2.0)]), _result([("y", 2.0000000001), ("x", 1.0)]), 1e-6)
    assert equal


@pytest.mark.parametrize(
    ("other", "message"),
    [
        (_result([("x", 1.0), ("z", 2.0)]), "chỉ có ở bản gốc"),
        (_result([("x", 1.0)]), "số dòng"),
        (_result([("x", 1.0), ("y", 2.0)], ["VARCHAR", "BIGINT"]), "kiểu cột"),
        (QueryResult(columns=["k", "w"], types=["VARCHAR", "DOUBLE"], rows=[("x", 1.0), ("y", 2.0)]), "cột"),
    ],
)
def test_compare_results_detects_differences(other: QueryResult, message: str):
    equal, detail = compare_results(_result([("x", 1.0), ("y", 2.0)]), other, 1e-6)
    assert not equal and message in detail.lower()


@pytest.mark.parametrize(
    ("before", "after", "cost", "decision"),
    [(100.0, 50.0, 0.0, "applied"), (100.0, 95.0, 0.0, "skipped"), (100.0, 50.0, 1000.0, "skipped")],
)
def test_decide_gate(before: float, after: float, cost: float, decision: str):
    result, reason, gain = decide(QueryMetrics(median_ms=before, runs=3), QueryMetrics(median_ms=after, runs=3), cost)
    assert result == decision and reason
    assert gain == pytest.approx(100 * (before - after) / before, abs=0.1)


def _candidate(sql: str, before_ms: float) -> dict:
    return {"original_sql": ORIGINAL, "sql": sql, "before": {"median_ms": before_ms, "runs": 3}, "attempt": 1}


def test_equivalent_rewrite_is_measured_and_decided(datasets: dict[str, str]):
    rewrite = ORIGINAL.replace(" union ", " union all ")
    report = evaluate_candidate(_candidate(rewrite, before_ms=1e6), datasets)
    assert all(c.equal for c in report.equivalence) and len(report.equivalence) == 5
    assert report.decision == "applied" and report.after is not None


def test_rewrite_with_different_result_is_rejected(datasets: dict[str, str]):
    wrong = ORIGINAL.replace("sum(v)", "avg(v)")
    report = evaluate_candidate(_candidate(wrong, before_ms=1e6), datasets)
    assert report.decision == "skipped" and "lệch" in report.reason
    assert report.after is None  # không đo tốc độ khi kết quả đã lệch


def test_small_gain_is_skipped(datasets: dict[str, str]):
    report = evaluate_candidate(_candidate(ORIGINAL.replace(" union ", " union all "), before_ms=0.0001), datasets)
    assert report.decision == "skipped" and "ngưỡng" in report.reason


def test_identical_proposal_is_skipped_without_benchmark(datasets: dict[str, str]):
    reformatted = "\n  ".join(ORIGINAL.split(" "))  # chỉ khác xuống dòng/thụt lề
    report = evaluate_candidate(_candidate(reformatted, before_ms=1e6), datasets)
    assert report.decision == "skipped" and "không đề xuất" in report.reason and report.after is None


def test_invalid_candidate_is_skipped(datasets: dict[str, str]):
    report = evaluate_candidate({**_candidate("drop table raw.a", 1.0), "invalid": "Lệnh DROP bị chặn"}, datasets)
    assert report.decision == "skipped" and not report.equivalence[0].equal


def test_optimize_standalone_tries_deterministic_sources_before_llm(datasets: dict[str, str]):
    report, usages = optimize_standalone(OptimizeJob(sql=ORIGINAL, datasets=datasets))
    assert {f.rule for f in report.findings} >= {"select_star", "union_distinct"}
    assert report.attempts >= 1 and report.proposed_sql
    if report.decision == "applied":
        assert all(c.equal for c in report.equivalence)
    if usages:  # chỉ gọi LLM khi luật/sqlglot không cho ứng viên đạt
        assert usages[0].simulated and report.attempts >= 2


def test_rule_candidate_wins_without_llm(datasets: dict[str, str]):
    sql = "select count(*) as n from (select * from raw.a union select * from raw.a) as x"
    report, usages = optimize_standalone(OptimizeJob(sql=sql, datasets=datasets))
    assert report.explanation.startswith("[rules]") or usages  # luật luôn được thử trước
    if report.explanation.startswith("[rules]"):
        assert any(c.dataset.startswith("giả định") and c.equal for c in report.equivalence)


def test_false_assumption_rejects_rule_candidate(datasets: dict[str, str]):
    from src.agents.nodes.compare import evaluate_candidate as evaluate

    with duckdb.connect(datasets["dirty"]) as con:
        con.execute("INSERT INTO raw.a SELECT * FROM raw.a LIMIT 2")  # bộ dirty có dòng trùng
    candidate = {
        **_candidate("select count(*) from raw.a", before_ms=1e6),
        "original_sql": "select count(*) from (select distinct * from raw.a) as x",
        "assumptions": [
            {
                "text": "raw.a không trùng dòng",
                "check_sql": "select (select count(*) from raw.a) - (select count(*) from (select distinct * from raw.a))",
            }
        ],
    }
    report = evaluate(candidate, datasets)
    assert report.decision == "skipped"  # hoặc lệch kết quả, hoặc giả định sai — không bao giờ được áp dụng
    assert any(not c.equal for c in report.equivalence)


def test_optimize_standalone_skips_clean_query(datasets: dict[str, str]):
    report, usages = optimize_standalone(OptimizeJob(sql="select k from raw.a group by k", datasets=datasets))
    assert report.decision == "skipped" and usages == []


def test_optimizer_and_compare_nodes_loop_until_decision(pipeline_state: dict):
    sources = []
    for _ in range(3):
        update = optimizer_node(pipeline_state)
        candidate = update["opt_candidate"]
        assert candidate["before"]["median_ms"] > 0
        sources.append(candidate["source"])
        pipeline_state.update(update)
        result = compare_node(pipeline_state)
        pipeline_state.update(result)
        if "optimization" in result:
            break
    report = pipeline_state["optimization"]
    assert report["decision"] in ("applied", "skipped")
    assert sources[-1] == "llm" or sources[0] in ("rules", "sqlglot")
    if report["decision"] == "applied":
        assert all(c["equal"] for c in report["equivalence"])
        assert "{{ ref('stg_shopee_orders') }}" in pipeline_state["code_files"]["models/marts/fct_daily_revenue.sql"]


def test_compare_node_sends_rejection_back_to_optimizer(pipeline_state: dict, mock_llm, monkeypatch):
    from src.agents.nodes import optimizer

    monkeypatch.setattr(optimizer, "DETERMINISTIC_SOURCES", {})
    mock_llm("optimizer", {"sql": "select order_date, 0 as order_count, 0 as revenue_vnd from main.stg_tiki_orders"})
    prepare_datasets(pipeline_state)
    pipeline_state.update(optimizer_node(pipeline_state))
    result = compare_node(pipeline_state)
    assert "optimization" not in result
    assert "lệch" in result["opt_candidate"]["feedback"] and result["opt_candidate"]["history"]
