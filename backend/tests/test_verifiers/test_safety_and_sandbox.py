"""Test V1 An toàn (lệnh nguy hiểm, tên bịa, DAG) và V2 Sandbox (dbt build thật trên DuckDB)."""

import pytest

from src.agents.nodes.safety import check_dag, check_models, safety_node
from src.agents.nodes.sandbox_run import sandbox_run_node

MART = "models/marts/fct_daily_revenue.sql"
GOOD_DAG = "from airflow import DAG\nwith DAG(dag_id='x') as dag:\n    a = 1\n    b = 2\n    a >> b\n"


def test_generated_code_passes_safety(pipeline_state: dict):
    update = safety_node(pipeline_state)
    assert update["safety"] == {"passed": True, "issues": []}
    assert "fix_attempts" not in update


@pytest.mark.parametrize(
    ("bad_sql", "expected"),
    [
        ("select revenue_bia from {{ ref('stg_tiki_orders') }}", "cột"),
        ("select * from {{ source('raw', 'bang_bia') }}", "không có trong danh mục"),
        ("drop table raw.tiki_orders", "bị chặn"),
        ("select * from read_csv('C:/Windows/win.ini')", "bị chặn"),
    ],
)
def test_safety_blocks_dangerous_or_invented_sql(pipeline_state: dict, bad_sql: str, expected: str):
    pipeline_state["code_files"][MART] = bad_sql
    update = safety_node(pipeline_state)
    assert update["safety"]["passed"] is False
    assert any(expected in issue for issue in update["safety"]["issues"]), update["safety"]["issues"]
    assert update["fix_attempts"] == 1 and len(update["error_signatures"]) == 1


def test_safety_requires_mart_dag_and_allowed_paths(pipeline_state: dict):
    files = pipeline_state["code_files"]
    files.pop(MART)
    files["../../etc/evil.sql"] = "select 1"
    for path in [p for p in files if p.startswith("dags/")]:
        files.pop(path)
    issues = safety_node(pipeline_state)["safety"]["issues"]
    assert any("Thiếu model đích" in i for i in issues)
    assert any("Thiếu DAG" in i for i in issues)
    assert any("không được phép" in i for i in issues)


def test_safety_rejects_mart_columns_different_from_spec(pipeline_state: dict):
    pipeline_state["code_files"][MART] = "select order_date from {{ ref('stg_tiki_orders') }}"
    issues = safety_node(pipeline_state)["safety"]["issues"]
    assert any("khác đặc tả" in i for i in issues)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (GOOD_DAG, []),
        ("def f(:\n", ["cú pháp"]),
        ("x = 1\n", ["DAG(...)"]),
        ("with DAG('x') as dag:\n    t = BashOperator(task_id='build')\n", []),  # 1 task: không cần >>
        ("with DAG('x') as dag:\n    a = Op(task_id='a')\n    b = Op(task_id='b')\n", ["thứ tự"]),
        (GOOD_DAG + "conn = 'postgres://u:pw@host/db'\n", ["ghi cứng"]),
    ],
)
def test_check_dag(source: str, expected: list[str]):
    issues = check_dag(source)
    assert len(issues) == len(expected)
    assert all(any(e in i for i in issues) for e in expected)


def test_check_models_resolves_dependency_order():
    catalog = {"raw": {"t": {"a": "INT"}}}
    files = {"models/marts/m.sql": "select a from {{ ref('s') }}", "models/staging/s.sql": "select a from raw.t"}
    issues, outputs = check_models(files, catalog)
    assert issues == [] and outputs["models/marts/m.sql"] == ["a"]


@pytest.mark.slow
def test_sandbox_runs_dbt_build_and_tests(pipeline_state: dict):
    update = sandbox_run_node(pipeline_state)
    box = update["sandbox"]
    assert box["passed"], box.get("error")
    assert box["models_ok"] == box["models_total"] == 1
    assert box["tests_ok"] == box["tests_total"] >= 3  # grain không rỗng + grain không trùng + đối soát
    assert box["target_rows"] == 30 and len(box["sample"]) == 10


@pytest.mark.slow
def test_sandbox_catches_wrong_aggregation(pipeline_state: dict):
    """Lỗi giả: SUM → AVG. Test đối soát của Testgen (viết độc lập) phải bắt được."""
    pipeline_state["code_files"][MART] = pipeline_state["code_files"][MART].replace(
        "sum(amount_vnd)", "avg(amount_vnd)"
    )
    update = sandbox_run_node(pipeline_state)
    assert update["sandbox"]["passed"] is False
    assert "assert_fct_daily_revenue_reconciles" in update["sandbox"]["error"]
    assert update["fix_attempts"] == 1
