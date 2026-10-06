"""Test vòng sửa E3/E3b ↔ V1: lỗi gốc rõ ràng, Coder sửa trên code cũ, Testgen giữ "đáp án" ổn định.

Các ca này lấy từ lần chạy bằng LLM thật (gpt-4o-mini): trước khi sửa, vòng sửa không hội tụ.
"""

from src.agents.nodes.codegen import code_error, codegen_node, codegen_variables, only_test_errors
from src.agents.nodes.safety import drop_cascading
from src.agents.nodes.testgen import testgen_node as run_testgen

STG = "models/staging/stg_tiki_orders.sql"
MART = "models/marts/fct_daily_revenue.sql"
EXTRA_TEST = "tests/assert_revenue_matches.sql"


def test_drop_cascading_keeps_only_root_error():
    issues = [
        f"{STG}: Column 'state' could not be resolved.",
        f"{MART}: Bảng 'main.stg_tiki_orders' không có trong danh mục dữ liệu thật.",
        "tests/assert_x.sql: Bảng 'main.fct_daily_revenue' không có trong danh mục dữ liệu thật.",
    ]
    outputs = {STG: [], MART: []}
    assert drop_cascading(issues, outputs) == issues[:1]


def test_drop_cascading_never_hides_every_error():
    issues = ["models/a.sql: Bảng 'main.b' không có trong danh mục dữ liệu thật."]
    assert drop_cascading(issues, {"models/a.sql": [], "models/b.sql": []}) == issues


def test_codegen_gets_previous_code_and_only_its_own_errors(pipeline_state: dict):
    state = {
        **pipeline_state,
        "safety": {"passed": False, "issues": [f"{STG}: lỗi cột", "tests/assert_x.sql: lỗi test"]},
    }
    variables = codegen_variables(state)
    assert code_error(state) == f"{STG}: lỗi cột"
    assert "tests/assert_x.sql" not in variables["last_error"]
    assert MART in variables["previous_code"]


def test_codegen_first_round_has_no_previous_code(pipeline_state: dict):
    state = {**pipeline_state, "safety": {}, "sandbox": {}}
    assert codegen_variables(state)["previous_code"] == "(chưa có)"


def test_codegen_keeps_code_without_llm_when_only_tests_fail(pipeline_state: dict):
    state = {**pipeline_state, "safety": {"passed": False, "issues": ["tests/assert_x.sql: lỗi test"]}}
    assert only_test_errors(state)
    update = codegen_node(state)
    assert update["code_files"] == pipeline_state["code_files"]
    assert "llm_usage" not in update


def _with_llm_test(state: dict, issues: list[str]) -> dict:
    files = {**state["test_files"], EXTRA_TEST: "select 1 where false"}
    return {**state, "test_files": files, "safety": {"passed": not issues, "issues": issues}}


def test_testgen_reuses_passing_tests_without_llm(pipeline_state: dict):
    state = _with_llm_test(pipeline_state, [f"{STG}: lỗi cột"])
    update = run_testgen(state)
    assert update["test_files"][EXTRA_TEST] == "select 1 where false"
    assert "llm_usage" not in update


def test_testgen_regenerates_when_its_own_test_fails(pipeline_state: dict):
    state = _with_llm_test(pipeline_state, [f"{EXTRA_TEST}: Column 'created_at' could not be resolved."])
    update = run_testgen(state)
    assert update["llm_usage"]
    assert "code_files" not in update


def test_column_error_points_to_offending_line():
    from src.agents.nodes.safety import check_sql

    sql = "WITH c AS (\n    SELECT id, state AS status FROM {{ source('raw', 't') }}\n)\nSELECT id FROM c\nWHERE state = 'x'\n"
    issues, columns = check_sql(sql, {"raw": {"t": {"id": "INT", "state": "VARCHAR"}}})
    assert columns == [] and "dòng lỗi: `WHERE state = 'x'`" in issues[0] and "đổi tên" in issues[0]
    assert "chỉ đọc được các cột: id, status" in issues[0]


def test_reconcile_test_is_built_by_code_from_expected_sql(pipeline_state: dict):
    from src.agents.nodes.common import spec_of
    from src.agents.nodes.testgen import _parse_expected

    spec = spec_of(pipeline_state)
    files, _ = _parse_expected('{"expected_sql": "select 1 as order_date", "notes": []}', spec)
    sql = files["tests/assert_fct_daily_revenue_reconciles.sql"]
    assert "full outer join" in sql and "e._found is null or a._found is null" in sql
    assert "abs(coalesce(e.revenue_vnd, 0) - coalesce(a.revenue_vnd, 0))" in sql


def test_expected_sql_must_not_read_target_table(pipeline_state: dict):
    from src.agents.nodes.common import spec_of
    from src.agents.nodes.testgen import _parse_expected

    text = '{"expected_sql": "select * from {{ ref(\'fct_daily_revenue\') }}"}'
    files, notes = _parse_expected(text, spec_of(pipeline_state))
    assert files == {} and "không trả `expected_sql` hợp lệ" in notes[-1]


def test_trailing_semicolon_removed_from_sql_only():
    from src.agents.nodes.codegen import normalize_file

    assert normalize_file("models/staging/s.sql", "select 1\nGROUP BY d;\n\n") == "select 1\nGROUP BY d\n"
    assert normalize_file("dags/d.py", "x = 1;\n") == "x = 1;\n"


def test_compile_check_blames_the_staging_file(pipeline_state: dict):
    """LLM thật viết `date(x, 'dd/mm/yyyy')` trong staging; dbt báo lỗi ở mart. V1 phải chỉ đúng file staging."""
    from src.agents.nodes.safety import safety_node

    stg = "models/staging/stg_shopee_orders.sql"
    pipeline_state["code_files"][stg] = pipeline_state["code_files"][stg].replace(
        "try_strptime(cast(order_date as varchar), '%Y-%m-%d')", "date(order_date, 'yyyy-mm-dd')"
    )
    issues = safety_node(pipeline_state)["safety"]["issues"]
    assert len(issues) == 1 and issues[0].startswith(f"{stg}: DuckDB không biên dịch được")


def test_compile_check_blames_test_file_not_code(pipeline_state: dict):
    """LLM thật dùng `duckdb_parse(...)` như một hàm trong test; V1 phải gắn lỗi cho file test (Testgen sửa)."""
    from src.agents.nodes.safety import safety_node

    pipeline_state["test_files"][EXTRA_TEST] = (
        "select order_date from {{ ref('fct_daily_revenue') }} where duckdb_parse(order_date) is null"
    )
    issues = safety_node(pipeline_state)["safety"]["issues"]
    assert len(issues) == 1 and issues[0].startswith(f"{EXTRA_TEST}: DuckDB không biên dịch được")


def test_unknown_qualified_column_lists_columns_of_that_table():
    """ELT-Bench + LLM thật: `e.salary` khi staging `e` đã gộp nhóm (không còn cột salary)."""
    from src.agents.nodes.safety import check_sql

    catalog = {"main": {"stg_e": {"position_id": "INT", "avg_salary": "DOUBLE"}, "stg_p": {"position_id": "INT"}}}
    sql = (
        "select p.position_id, count(case when e.salary > 20000 then 1 end) as n\n"
        "from {{ ref('stg_p') }} p left join {{ ref('stg_e') }} e on p.position_id = e.position_id\n"
        "group by p.position_id"
    )
    issues, _ = check_sql(sql, catalog)
    assert "chỉ đọc được các cột: e.position_id, e.avg_salary" in issues[0]


def test_mart_columns_compare_ignores_case(pipeline_state: dict):
    """ELT-Bench có cột `num_Account_Representatives_...`; DuckDB không phân biệt hoa/thường nên không được báo lỗi."""
    from src.agents.nodes.safety import safety_node

    for column in pipeline_state["spec"]["output_columns"]:
        if column["name"] == "revenue_vnd":
            column["name"] = "Revenue_VND"
    pipeline_state["spec"]["grain"] = ["order_date"]
    assert safety_node(pipeline_state)["safety"]["issues"] == []


def test_planner_drops_questions_already_answered():
    """ELT-Bench `courses`: gpt-4o-mini hỏi lại y hệt 3 câu đã trả lời, 3 vòng liền → code tự bỏ."""
    from src.agents.nodes.planner import drop_answered

    answered = [{"id": "q1", "question": "Cách xác định giáo sư là giảng viên?", "answer": "Dựa vào cột hasPosition"}]
    data = {
        "unknowns": ["Cách xác định giáo sư là giảng viên?", "Điểm mới?"],
        "questions": [
            {"id": "q1", "question": "cách xác định giáo sư là giảng viên", "options": ["a", "b"]},
            {"id": "q2", "question": "Điểm mới?", "options": ["a", "b"]},
        ],
        "assumptions": [],
    }
    result = drop_answered(data, answered)
    assert result["unknowns"] == ["Điểm mới?"] and [q["id"] for q in result["questions"]] == ["q2"]
    assert result["assumptions"] == ["Cách xác định giáo sư là giảng viên? → Dựa vào cột hasPosition"]


def test_readable_columns_ignore_ctes_not_in_from():
    """ELT-Bench `professors`: CTE thứ 2 đọc stg_student (không có prof_id); CTE thứ 1 có prof_id nhưng không nằm
    trong FROM của câu lỗi → không được tính là "đọc được"."""
    from src.agents.nodes.safety import check_sql

    catalog = {"main": {"stg_ra": {"prof_id": "INT"}, "stg_student": {"student_id": "INT"}}}
    sql = (
        "with ra as (select prof_id from {{ ref('stg_ra') }}),\n"
        "s as (select prof_id, count(*) as n from {{ ref('stg_student') }} group by prof_id)\n"
        "select * from s"
    )
    issues, _ = check_sql(sql, catalog)
    assert "chỉ đọc được các cột: student_id." in issues[0]


def test_codegen_drops_system_owned_config_files():
    """gpt-5.6-luna hay tự viết dbt_project.yml / models/sources.yml (trùng source) → code bỏ và ghi chú cho Reviewer."""
    from src.agents.nodes.codegen import drop_system_files

    files = {
        "dbt_project.yml": "name: x",
        "models/sources.yml": "sources: []",
        "models/staging/schema.yaml": "x",
        "models/marts/fct.sql": "select 1",
        "dags/fct_dag.py": "x = 1",
        "../etc/passwd": "x",  # đường dẫn lạ: KHÔNG bỏ ở đây, để V1 chặn và ghi bằng chứng
    }
    kept, note = drop_system_files(files)
    assert set(kept) == {"models/marts/fct.sql", "dags/fct_dag.py", "../etc/passwd"}
    assert "dbt_project.yml" in note[0] and "models/sources.yml" in note[0]
