"""V1 An toàn (code thuần, 0 token): kiểm tra mọi file sinh ra trước khi chạy trong sandbox.

- SQL: chỉ một câu SELECT; chặn DROP/ATTACH/INSTALL/COPY/PRAGMA/SET, hàm đọc file, đường dẫn tuyệt đối, Jinja lạ.
- Mọi bảng/cột phải có trong danh mục thật (sqlglot qualify); DuckDB biên dịch thử (EXPLAIN, chỉ đọc) từng model.
- DAG: biên dịch được, có DAG(...), có thứ tự task, không ghi cứng thông tin kết nối.
"""

import ast
import re
from pathlib import Path

from src.agents.nodes.common import all_files, mart_path, register_failure, sandbox_db, spec_of
from src.agents.state import PipelineState
from src.agents.tools.dbt_tools import is_allowed_path
from src.agents.tools.duckdb_tools import explain_error, read_catalog
from src.agents.tools.sql_tools import (
    SqlCheckError,
    expand_models,
    explain_column_error,
    find_unknown_tables,
    find_unsafe_constructs,
    inline_refs,
    output_columns,
    parse_single_select,
    readable_columns,
    render_dbt_sql,
)

Catalog = dict[str, dict[str, dict[str, str]]]
SECRET_RE = re.compile(r"password\s*=|passwd|secret\s*=|api[_-]?key\s*=|(postgres|mysql|snowflake)://\S+:\S+@", re.I)


def check_sql(sql: str, catalog: Catalog) -> tuple[list[str], list[str]]:
    """Kiểm tra một file SQL; trả về (lỗi, cột đầu ra)."""
    rendered = render_dbt_sql(sql)
    try:
        tree = parse_single_select(rendered)
    except SqlCheckError as exc:
        return [str(exc)], []
    issues = find_unsafe_constructs(tree) + find_unknown_tables(tree, catalog)
    if issues:
        return issues, []
    try:
        return [], output_columns(tree, catalog)
    except SqlCheckError as exc:
        return [explain_column_error(str(exc), rendered, readable_columns(tree, catalog, str(exc)))], []


def check_dag(source: str) -> list[str]:
    """Kiểm tra DAG Airflow bằng AST (không cần cài Airflow)."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"DAG lỗi cú pháp Python dòng {exc.lineno}: {exc.msg}"]
    calls = {getattr(n.func, "id", getattr(n.func, "attr", "")) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    issues = [] if "DAG" in calls else ["DAG không có lời gọi DAG(...)."]
    tasks = sum(1 for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == "task_id")
    has_order = any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.RShift) for n in ast.walk(tree))
    if tasks > 1 and not has_order:
        issues.append("DAG có nhiều task nhưng chưa khai báo thứ tự (toán tử >>).")
    if SECRET_RE.search(source):
        issues.append("DAG có vẻ ghi cứng mật khẩu/chuỗi kết nối — dùng Airflow Connection/Variable.")
    return issues


def _model_name(path: str) -> str:
    return path.rsplit("/", 1)[-1].removesuffix(".sql")


def check_models(sql_files: dict[str, str], catalog: Catalog) -> tuple[list[str], dict[str, list[str]]]:
    """Kiểm tra model theo thứ tự phụ thuộc; model đã đạt được thêm vào danh mục `main`."""
    issues: list[str] = []
    outputs: dict[str, list[str]] = {}
    pending = dict(sql_files)
    while pending:
        progressed = False
        for path, sql in list(pending.items()):
            errors, columns = check_sql(sql, catalog)
            if errors and any("không có trong danh mục" in e for e in errors) and len(pending) > 1:
                continue
            pending.pop(path)
            progressed = True
            issues.extend(f"{path}: {e}" for e in errors)
            outputs[path] = columns
            if columns:
                catalog.setdefault("main", {})[_model_name(path)] = {c: "VARCHAR" for c in columns}
        if not progressed:
            path, sql = pending.popitem()
            issues.extend(f"{path}: {e}" for e in check_sql(sql, catalog)[0])
    return issues, outputs


def _structure_issues(state: PipelineState, files: dict[str, str]) -> list[str]:
    spec = spec_of(state)
    issues = [f"Đường dẫn file không được phép: {p}" for p in files if not is_allowed_path(p)]
    if mart_path(spec) not in files:
        issues.append(f"Thiếu model đích {mart_path(spec)}.")
    if not any(p.startswith("dags/") for p in files):
        issues.append("Thiếu DAG Airflow trong thư mục dags/.")
    return issues


def _mart_columns_issue(state: PipelineState, outputs: dict[str, list[str]]) -> list[str]:
    spec = spec_of(state)
    expected, actual = [c.name for c in spec.output_columns], outputs.get(mart_path(spec))
    # Tên cột DuckDB không phân biệt hoa/thường (sqlglot trả về chữ thường); model lỗi (rỗng) đã báo ở lỗi gốc
    if actual and {a.lower() for a in actual} != {e.lower() for e in expected}:
        missing = sorted({e.lower() for e in expected} - {a.lower() for a in actual})
        extra = sorted({a.lower() for a in actual} - {e.lower() for e in expected})
        return [f"Cột của model đích khác đặc tả: thiếu {missing}, thừa {extra}."]
    return []


def drop_cascading(issues: list[str], outputs: dict[str, list[str]]) -> list[str]:
    """Bỏ lỗi dây chuyền "bảng main.X không có" khi chính model X đã lỗi, để Coder thấy đúng lỗi gốc."""
    failed = {_model_name(path) for path, columns in outputs.items() if not columns}
    kept = [i for i in issues if not any(f"'main.{name}' không có" in i for name in failed)]
    return kept or issues  # không bao giờ để rỗng khi thực tế có lỗi (ví dụ tham chiếu vòng)


def compile_issues(sql_files: dict[str, str], db: Path) -> list[str]:
    """Biên dịch thử model + test bằng DuckDB EXPLAIN (chỉ đọc, 0 token) để lỗi hàm/kiểu gắn ĐÚNG file.

    Không có bước này, lỗi trong staging ephemeral bị dbt báo ở model đích nên Coder sửa nhầm chỗ.
    """
    rendered = {path: render_dbt_sql(sql) for path, sql in sql_files.items()}
    models = expand_models({_model_name(p): sql for p, sql in rendered.items() if p.startswith("models/")})
    errors: dict[str, str] = {}
    for path, sql in rendered.items():
        full = inline_refs(sql, models)
        if not re.search(r"\bmain\.", full) and (error := explain_error(db, full)):
            errors[path] = error
    failed = {_model_name(path) for path in errors if path.startswith("models/")}
    return [
        f"{path}: DuckDB không biên dịch được: {error}"
        for path, error in errors.items()
        if not any(re.search(rf"\bmain\.{name}\b", rendered[path]) for name in failed)
    ]  # bỏ lỗi dây chuyền ở file gọi tới model đã lỗi


def run_safety_checks(state: PipelineState) -> list[str]:
    """Toàn bộ kiểm tra V1 cho code + test hiện tại."""
    files = all_files(state)
    issues = _structure_issues(state, files)
    catalog = {k: v for k, v in read_catalog(sandbox_db(state)).items() if k == "raw"}
    models = {p: s for p, s in files.items() if p.startswith("models/") and p.endswith(".sql")}
    model_issues, outputs = check_models(models, catalog)
    tests = {p: s for p, s in files.items() if p.startswith("tests/") and p.endswith(".sql")}
    test_issues = [f"{p}: {e}" for p, s in tests.items() for e in check_sql(s, catalog)[0]]
    dag_issues = [f"{p}: {e}" for p, s in files.items() if p.startswith("dags/") for e in check_dag(s)]
    all_issues = issues + model_issues + test_issues + dag_issues + _mart_columns_issue(state, outputs)
    if all_issues:
        return drop_cascading(all_issues, outputs)
    return compile_issues({**models, **tests}, sandbox_db(state))


def safety_node(state: PipelineState) -> dict:
    """Chặn code không an toàn/bịa tên; lỗi được ghi sổ lỗi và đếm vào vòng sửa."""
    issues = run_safety_checks(state)
    result: dict = {"safety": {"passed": not issues, "issues": issues}}
    if issues:
        result.update(
            register_failure(
                state, "\n".join(issues), sql_before=state.get("code_files", {}).get(mart_path(spec_of(state)), "")
            )
        )
    return result
