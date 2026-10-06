"""Test luật viết lại tất định (chuyển từ nhánh feature/optimizer-agent) + phát hiện dấu hiệu chậm mới."""

import duckdb
import pytest

from src.agents.tools.rewrite_rules import rules_candidate, sqlglot_candidate
from src.agents.tools.slow_patterns import detect_slow_patterns

SCHEMA = {"t": {"id": "BIGINT", "k": "INTEGER", "v": "VARCHAR"}, "u": {"id": "BIGINT", "w": "DOUBLE"}}


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    c.execute("CREATE TABLE t AS SELECT range AS id, (range % 7)::INTEGER AS k, 'v' || range AS v FROM range(200)")
    c.execute("CREATE TABLE u AS SELECT range AS id, range * 1.5 AS w FROM range(0, 200, 2)")
    return c


def same_result(con: duckdb.DuckDBPyConnection, a: str, b: str) -> bool:
    return sorted(con.execute(a).fetchall()) == sorted(con.execute(b).fetchall())


def test_no_rule_applies_returns_none():
    assert rules_candidate("SELECT id FROM t WHERE k = 1", SCHEMA) is None


def test_drop_order_by_in_subquery(con):
    sql = "SELECT k, count(*) FROM (SELECT * FROM t ORDER BY v) GROUP BY k"
    cand = rules_candidate(sql, SCHEMA)
    assert cand.applied == ["drop_subquery_order_by"] and not cand.assumptions
    assert "ORDER BY" not in cand.sql.upper() and same_result(con, sql, cand.sql)


def test_order_by_kept_with_limit_top_level_or_order_sensitive_agg():
    assert rules_candidate("SELECT * FROM (SELECT * FROM t ORDER BY v LIMIT 5)", SCHEMA) is None
    assert rules_candidate("SELECT * FROM t ORDER BY v", SCHEMA) is None
    assert rules_candidate("SELECT string_agg(v, ',') FROM (SELECT * FROM t ORDER BY v)", SCHEMA) is None


def test_drop_distinct_records_checkable_assumption(con):
    sql = "SELECT k, count(*) FROM (SELECT DISTINCT * FROM t) GROUP BY k"
    cand = rules_candidate(sql, SCHEMA)
    assert cand.applied == ["drop_distinct_star_table"]
    assert con.execute(cand.assumptions[0].check_sql).fetchone()[0] == 0
    assert same_result(con, sql, cand.sql)
    con.execute("INSERT INTO t SELECT * FROM t LIMIT 3")
    assert con.execute(cand.assumptions[0].check_sql).fetchone()[0] == 3  # dữ liệu trùng → giả định sai


def test_self_union_then_distinct_removed(con):
    sql = "SELECT count(*) FROM (SELECT * FROM t UNION SELECT * FROM t)"
    cand = rules_candidate(sql, SCHEMA)
    assert cand.applied == ["self_union_to_distinct", "drop_distinct_star_table"]
    assert "UNION" not in cand.sql.upper() and same_result(con, sql, cand.sql)


def test_union_to_union_all_with_two_assumptions(con):
    sql = "SELECT count(*) FROM (SELECT * FROM t WHERE k = 1 UNION SELECT * FROM t WHERE k <> 1)"
    cand = rules_candidate(sql, SCHEMA)
    assert cand.applied == ["union_to_union_all"] and "UNION ALL" in cand.sql.upper()
    assert [con.execute(a.check_sql).fetchone()[0] for a in cand.assumptions] == [0, 0]
    assert same_result(con, sql, cand.sql)


def test_union_overlap_assumption_detects_overlap(con):
    cand = rules_candidate("SELECT * FROM t WHERE k >= 1 UNION SELECT * FROM t WHERE k <= 3", SCHEMA)
    overlap = next(a for a in cand.assumptions if "giao" in a.text)
    assert con.execute(overlap.check_sql).fetchone()[0] > 0


def test_rownumber_dedupe_to_constant(con):
    sql = (
        "SELECT count(*) FROM (SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY id ORDER BY v) AS rn "
        "FROM t) WHERE rn = 1)"
    )
    cand = rules_candidate(sql, SCHEMA)
    assert cand.applied == ["rownumber_to_constant"] and "ROW_NUMBER" not in cand.sql.upper()
    assert con.execute(cand.assumptions[0].check_sql).fetchone()[0] == 0
    assert same_result(con, sql, cand.sql)


def test_rules_do_not_treat_cte_names_as_tables():
    """Bổ sung so với nhánh gốc: CTE không phải bảng thật nên không sinh giả định kiểm chứng sai chỗ."""
    sql = (
        "WITH a AS (SELECT * FROM t UNION SELECT * FROM t) "
        "SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY id) AS rn FROM a) WHERE rn = 1"
    )
    cand = rules_candidate(sql, SCHEMA)
    assert cand is None or "rownumber_to_constant" not in cand.applied


def test_range_pair_becomes_equality(con):
    sql = "SELECT t.id, w FROM t, u WHERE t.id >= u.id AND t.id <= u.id AND k > 2"
    cand = rules_candidate(sql, SCHEMA)
    assert cand.applied == ["range_to_equality"] and "t.id = u.id" in cand.sql
    assert same_result(con, sql, cand.sql)
    reversed_sql = "SELECT t.id FROM t, u WHERE u.id <= t.id AND u.id >= t.id"
    assert same_result(con, reversed_sql, rules_candidate(reversed_sql, SCHEMA).sql)


def test_range_pair_with_volatile_expression_is_kept():
    sql = "SELECT t.id FROM t WHERE random() >= 0.5 AND random() <= 0.5"
    cand = rules_candidate(sql, SCHEMA)
    assert cand is None or "range_to_equality" not in cand.applied


def test_cast_equality_only_for_integers(con):
    sql = "SELECT t.id FROM t, u WHERE CAST(t.id AS VARCHAR) = CAST(u.id AS VARCHAR)"
    cand = rules_candidate(sql, SCHEMA)
    assert cand.applied == ["cast_equality"] and same_result(con, sql, cand.sql)
    assert rules_candidate("SELECT 1 FROM t, u WHERE CAST(t.v AS VARCHAR) = CAST(u.w AS VARCHAR)", SCHEMA) is None


def test_sqlglot_candidate_preserves_result(con):
    sql = "SELECT k, count(*) AS n FROM (SELECT * FROM t WHERE id > 10) AS x WHERE k > 2 GROUP BY k"
    cand = sqlglot_candidate(sql, SCHEMA)
    assert cand is not None and cand.source == "sqlglot" and same_result(con, sql, cand.sql)


def test_distinct_kept_over_aggregating_subquery():
    assert rules_candidate("SELECT count(*) FROM (SELECT DISTINCT * FROM (SELECT k FROM t GROUP BY k))", SCHEMA) is None


@pytest.mark.parametrize(
    ("sql", "rule"),
    [
        ("SELECT * FROM (SELECT DISTINCT * FROM t)", "distinct_in_subquery"),
        ("SELECT k FROM (SELECT * FROM t ORDER BY v) GROUP BY k", "order_in_subquery"),
        ("SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY id) AS rn FROM t) WHERE rn = 1", "window_dedupe"),
        ("SELECT t.id FROM t, u WHERE t.id >= u.id AND t.id <= u.id", "range_equality_join"),
        ("SELECT t.id FROM t JOIN u ON CAST(t.id AS VARCHAR) = CAST(u.id AS VARCHAR)", "cast_in_join"),
        ("SELECT (SELECT max(k) FROM t) a, (SELECT max(k) FROM t) b", "repeated_subquery"),
        ("WITH x AS MATERIALIZED (SELECT * FROM t) SELECT id FROM x", "materialized_cte"),
    ],
)
def test_new_slow_patterns(sql: str, rule: str):
    assert rule in [f.rule for f in detect_slow_patterns(sql)]
