"""Test phân tích SQL (sqlglot): chặn lệnh nguy hiểm, bắt tên bảng/cột bịa, phát hiện dấu hiệu chậm."""

import pytest

from src.agents.tools.slow_patterns import detect_slow_patterns
from src.agents.tools.sql_tools import (
    SqlCheckError,
    find_unknown_tables,
    find_unsafe_constructs,
    output_columns,
    parse_single_select,
    render_dbt_sql,
    to_dbt_refs,
)

CATALOG = {
    "raw": {"orders": {"order_id": "VARCHAR", "amount": "BIGINT", "status": "VARCHAR"}},
    "main": {"stg_orders": {"order_id": "VARCHAR", "amount": "BIGINT"}},
}


def test_render_dbt_sql_replaces_source_ref_config():
    sql = (
        "{{ config(materialized='table') }} select * from {{ source('raw', 'orders') }} join {{ ref(\"stg_orders\") }}"
    )
    assert render_dbt_sql(sql) == "select * from raw.orders join main.stg_orders"


@pytest.mark.parametrize(
    "config",
    [
        "pre_hook=\"ATTACH 'x.db' AS y; COPY (SELECT 1) TO 'out.csv'\"",
        "post_hook='INSTALL httpfs'",
        "materialized=run_query('select 1')",
        "'table'",
        "alias='{{ x }}'",
    ],
)
def test_render_dbt_sql_blocks_unsafe_config(config: str):
    with pytest.raises(SqlCheckError, match="config"):
        render_dbt_sql(f"{{{{ config({config}) }}}} select 1")


def test_render_dbt_sql_allows_literal_config():
    sql = "{{ config(materialized='incremental', unique_key=['id'], tags=['daily']) }} select 1 as id"
    assert render_dbt_sql(sql) == "select 1 as id"


def test_render_dbt_sql_blocks_other_jinja():
    with pytest.raises(SqlCheckError, match="Jinja"):
        render_dbt_sql("{{ run_query('ATTACH x') }} select 1")


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE raw.orders",
        "ATTACH 'prod.duckdb' AS prod",
        "INSTALL httpfs",
        "COPY raw.orders TO 'C:/out.csv'",
        "PRAGMA database_list",
        "SET enable_external_access = true",
        "CREATE TABLE x AS SELECT 1",
        "select 1; select 2",
        "select from where",
    ],
)
def test_parse_single_select_rejects_non_select(sql: str):
    with pytest.raises(SqlCheckError):
        parse_single_select(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "select * from read_csv('C:/secret.csv')",
        "select * from read_parquet('data.parquet')",
        "select getenv('OPENAI_API_KEY')",
        "select * from raw.orders where status = '/etc/passwd'",
        "select 'https://evil.example/x' as u",
        "select * from raw.orders where status = '~/.ssh/id_rsa'",
        "select * from raw.orders where status = '//server/share'",
    ],
)
def test_find_unsafe_constructs(sql: str):
    assert find_unsafe_constructs(parse_single_select(sql))


@pytest.mark.parametrize(
    "sql",
    [
        "select replace(order_date, '/', '-') as d from raw.orders",  # LLM thật sinh câu này; trước đây bị chặn nhầm
        "select strptime(order_date, '%d/%m/%Y') as d from raw.orders",
        "select 'a / b' as label",
    ],
)
def test_slash_in_ordinary_strings_is_not_a_path(sql: str):
    assert find_unsafe_constructs(parse_single_select(sql)) == []


def test_safe_select_has_no_issues():
    tree = parse_single_select("with a as (select order_id from raw.orders) select order_id from a")
    assert find_unsafe_constructs(tree) == []
    assert find_unknown_tables(tree, CATALOG) == []


def test_unknown_table_is_reported():
    issues = find_unknown_tables(parse_single_select("select * from raw.khong_co"), CATALOG)
    assert issues and "raw.khong_co" in issues[0]


def test_invented_column_is_rejected():
    with pytest.raises(SqlCheckError, match="cột"):
        output_columns(parse_single_select("select revenue_bia from raw.orders"), CATALOG)


def test_output_columns_resolves_star_and_aliases():
    tree = parse_single_select("select o.*, amount * 2 as double_amount from raw.orders o")
    assert output_columns(tree, CATALOG) == ["order_id", "amount", "status", "double_amount"]


@pytest.mark.parametrize(
    ("sql", "rule"),
    [
        ("select * from raw.orders", "select_star"),
        ("select order_id from raw.orders union select order_id from main.stg_orders", "union_distinct"),
        ("select order_id from raw.orders where lower(status) = 'x'", "function_in_where"),
        ("select a.order_id from raw.orders a, main.stg_orders b", "implicit_cross_join"),
        (
            "select order_id from raw.orders o where amount > "
            "(select avg(s.amount) from main.stg_orders s where s.order_id = o.order_id)",
            "correlated_subquery",
        ),
        ("select distinct status, count(*) from raw.orders group by status", "redundant_distinct"),
    ],
)
def test_detect_slow_patterns(sql: str, rule: str):
    assert rule in [f.rule for f in detect_slow_patterns(sql)]


def test_clean_query_has_no_findings():
    assert detect_slow_patterns("select status, sum(amount) as total from raw.orders group by status") == []


def test_to_dbt_refs_round_trip():
    sql = "select x from main.stg_orders join main.stg_orders_extra using (x)"
    result = to_dbt_refs(sql, ["stg_orders", "stg_orders_extra"])
    assert result == "select x from {{ ref('stg_orders') }} join {{ ref('stg_orders_extra') }} using (x)"
