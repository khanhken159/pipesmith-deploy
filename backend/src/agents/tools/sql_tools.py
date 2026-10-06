"""Phân tích SQL bằng sqlglot: dựng SQL từ model dbt, kiểm tra an toàn, kiểm tra tên bảng/cột."""

import ast
import logging
import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError, SchemaError, SqlglotError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope

logging.getLogger("sqlglot").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

DIALECT = "duckdb"
SOURCE_RE = re.compile(r"\{\{\s*source\(\s*['\"](\w+)['\"]\s*,\s*['\"](\w+)['\"]\s*\)\s*\}\}")
REF_RE = re.compile(r"\{\{\s*ref\(\s*['\"](\w+)['\"]\s*\)\s*\}\}")
CONFIG_RE = re.compile(r"\{\{\s*config\(([^}]*)\)\s*\}\}")
# dbt thực thi đối số của config() (pre_hook/post_hook chạy SQL tùy ý, bỏ qua V1) → chỉ nhận khóa vô hại, giá trị literal.
ALLOWED_CONFIG_KEYS = {"materialized", "tags", "alias", "unique_key"}
JINJA_COMMENT_RE = re.compile(r"\{#.*?#\}", re.DOTALL)
BLOCKED_FUNCTIONS = {
    "READ_CSV",
    "READ_CSV_AUTO",
    "READ_PARQUET",
    "PARQUET_SCAN",
    "READ_JSON",
    "READ_JSON_AUTO",
    "READ_NDJSON",
    "READ_TEXT",
    "READ_BLOB",
    "GLOB",
    "SQLITE_SCAN",
    "SQLITE_ATTACH",
    "POSTGRES_SCAN",
    "MYSQL_SCAN",
    "GETENV",
    "READ_XLSX",
    "ICEBERG_SCAN",
    "DELTA_SCAN",
    "QUERY_TABLE",
    "READCSV",
    "READPARQUET",
    "READJSON",
}
# "/" phải theo sau là tên thư mục (/etc, /.ssh); "/" đứng riêng hay trong "%d/%m/%Y" không phải đường dẫn
ABS_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/[\w.]|//|~[\\/]|\\\\|[a-z]+://)")


class SqlCheckError(ValueError):
    """SQL không qua được kiểm tra (thông báo tiếng Việt)."""


def check_config_args(args: str) -> None:
    """config() chỉ được có đối số tên trong ALLOWED_CONFIG_KEYS với giá trị literal (chuỗi, số, danh sách)."""
    try:
        call = ast.parse(f"config({args})", mode="eval").body
        assert isinstance(call, ast.Call) and not call.args
        keywords = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords}
    except (SyntaxError, ValueError, AssertionError) as exc:
        raise SqlCheckError(f"config() chỉ nhận đối số dạng tên=giá_trị_literal: config({args.strip()[:80]})") from exc
    blocked = sorted(str(key) for key in keywords if key not in ALLOWED_CONFIG_KEYS)
    if blocked:
        allowed = ", ".join(sorted(ALLOWED_CONFIG_KEYS))
        raise SqlCheckError(f"config() không cho phép {', '.join(blocked)} (chỉ được: {allowed}).")
    if any("{" in str(value) for value in keywords.values()):
        raise SqlCheckError("Giá trị trong config() không được chứa Jinja.")


def _strip_config(match: re.Match) -> str:
    check_config_args(match.group(1))
    return ""


def render_dbt_sql(sql: str) -> str:
    """Thay source()/ref()/config() bằng tên bảng thật; Jinja khác bị coi là không an toàn."""
    text = CONFIG_RE.sub(_strip_config, JINJA_COMMENT_RE.sub("", sql))
    text = SOURCE_RE.sub(lambda m: f"{m.group(1)}.{m.group(2)}", text)
    text = REF_RE.sub(lambda m: f"main.{m.group(1)}", text)
    if "{{" in text or "{%" in text:
        raise SqlCheckError("Chỉ cho phép Jinja source(), ref(), config(); phát hiện Jinja khác (macro/lệnh).")
    return text.strip().rstrip(";")


def to_dbt_refs(sql: str, models: list[str]) -> str:
    """Đổi `main.<model>` về `{{ ref('<model>') }}` (dùng khi ghi bản tối ưu trở lại dự án dbt)."""
    for name in sorted(models, key=len, reverse=True):
        sql = re.sub(rf'\b(?:"?main"?\.)"?{name}"?\b', f"{{{{ ref('{name}') }}}}", sql)
    return sql


def parse_single_select(sql: str) -> exp.Query:
    """Parse đúng một câu SELECT; lỗi cú pháp hoặc lệnh khác SELECT đều bị từ chối."""
    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
    except ParseError as exc:
        raise SqlCheckError(f"Lỗi cú pháp SQL: {str(exc).splitlines()[0]}") from exc
    if len(statements) != 1:
        raise SqlCheckError(f"Chỉ cho phép đúng 1 câu lệnh, nhận được {len(statements)}.")
    statement = statements[0]
    if not isinstance(statement, exp.Query):
        raise SqlCheckError(f"Lệnh '{type(statement).__name__.upper()}' bị chặn: model chỉ được là câu SELECT.")
    return statement


def same_query(a: str, b: str) -> bool:
    """Hai câu SQL giống nhau sau khi chuẩn hóa định dạng (bỏ khác biệt chữ hoa/thụt lề/comment)."""
    try:
        return parse_single_select(a).sql(dialect=DIALECT, comments=False) == parse_single_select(b).sql(
            dialect=DIALECT, comments=False
        )
    except SqlCheckError:
        return a.strip() == b.strip()


def _function_name(node: exp.Func) -> str:
    return (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).upper()


def find_unsafe_constructs(tree: exp.Expression) -> list[str]:
    """Tìm hàm đọc file/mạng, câu lệnh lồng nguy hiểm và đường dẫn tuyệt đối trong chuỗi."""
    issues = []
    for node in tree.find_all(exp.Func):
        if _function_name(node) in BLOCKED_FUNCTIONS:
            issues.append(f"Hàm '{_function_name(node)}' bị chặn (đọc file/biến môi trường ngoài sandbox).")
    for node in tree.find_all(exp.Literal):
        if node.is_string and ABS_PATH_RE.match(node.this):
            issues.append(f"Đường dẫn/URL '{node.this}' bị chặn (chỉ được đọc bảng trong workspace).")
    for kind in (exp.Drop, exp.Attach, exp.Install, exp.Copy, exp.Pragma, exp.Set, exp.Command, exp.Insert):
        if tree.find(kind):
            issues.append(f"Lệnh '{kind.__name__.upper()}' bị chặn.")
    return issues


def _cte_names(tree: exp.Expression) -> set[str]:
    return {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}


def find_unknown_tables(tree: exp.Expression, catalog: dict[str, dict[str, dict[str, str]]]) -> list[str]:
    """Bảng được tham chiếu phải có trong danh mục thật (hoặc là CTE)."""
    ctes, issues = _cte_names(tree), []
    for table in tree.find_all(exp.Table):
        if not table.name or isinstance(table.this, exp.Func):
            continue
        schema = (table.db or "main").lower()
        if table.name.lower() in ctes and not table.db:
            continue
        if table.name.lower() not in {t.lower() for t in catalog.get(schema, {})}:
            issues.append(f"Bảng '{schema}.{table.name}' không có trong danh mục dữ liệu thật.")
    return issues


LINE_RE = re.compile(r"Line: (\d+)")
COLUMN_NAME_RE = re.compile(r"Column '([^']+)' could not be resolved|Unknown column: (\w+)")
COLUMN_HINT = (
    "Gợi ý: cột này không có trong bảng/CTE mà câu SELECT đó đọc. Nếu CTE đã đổi tên (AS) thì dùng tên mới; "
    "nếu cần cột gốc thì chọn thêm nó trong CTE hoặc lọc ngay trong CTE."
)


def readable_columns(tree: exp.Expression, catalog: dict[str, dict[str, dict[str, str]]], message: str) -> list[str]:
    """Các cột mà câu SELECT chứa cột lỗi thực sự đọc được (từ CTE/subquery/bảng nó đọc)."""
    match = COLUMN_NAME_RE.search(message)
    if not match:
        return []
    name = match.group(1) or match.group(2)
    try:
        for scope in traverse_scope(tree):
            for column in (c for c in scope.columns if c.name == name):
                available = _available_for(scope, column.table, catalog)
                if name not in available:  # đúng câu SELECT (và đúng bảng) nơi cột không đọc được
                    return [f"{column.table}.{col}" if column.table else col for col in available]
    except SqlglotError:
        logger.debug("không phân tích được phạm vi cột", exc_info=True)
    return []


def _available_for(scope: Scope, table: str, catalog: dict[str, dict[str, dict[str, str]]]) -> list[str]:
    """Cột đọc được từ một nguồn cụ thể (`e.salary` → chỉ xét `e`) hoặc từ mọi nguồn của câu SELECT."""
    selected = {name: source for name, (_, source) in scope.selected_sources.items()}  # chỉ nguồn trong FROM/JOIN
    sources = [selected[table]] if table in selected else list(selected.values())
    return [col for source in sources for col in _source_columns(source, catalog)]


def _source_columns(source: object, catalog: dict[str, dict[str, dict[str, str]]]) -> list[str]:
    if isinstance(source, Scope):
        return list(source.expression.named_selects)
    if isinstance(source, exp.Table):
        return list(catalog.get((source.db or "main").lower(), {}).get(source.name, {}))
    return []


def explain_column_error(message: str, sql: str, readable: list[str]) -> str:
    """Thêm dòng SQL bị lỗi, các cột đọc được và gợi ý sửa vào thông báo của sqlglot (để Coder sửa đúng chỗ)."""
    match = LINE_RE.search(message)
    lines = sql.splitlines()
    has_line = bool(match) and 0 < int(match.group(1)) <= len(lines)
    if not has_line and not readable:
        return message
    where = f" → dòng lỗi: `{lines[int(match.group(1)) - 1].strip()}`." if has_line else ""
    available = f" Câu SELECT đó chỉ đọc được các cột: {', '.join(readable)}." if readable else ""
    return f"{message}{where}{available} {COLUMN_HINT}"


def output_columns(tree: exp.Query, catalog: dict[str, dict[str, dict[str, str]]]) -> list[str]:
    """Kiểm tra mọi cột tồn tại (sqlglot qualify) và trả về tên các cột đầu ra."""
    try:
        qualified = qualify(tree.copy(), schema=catalog, dialect=DIALECT, validate_qualify_columns=True)
    except (OptimizeError, SchemaError) as exc:
        raise SqlCheckError(f"Tham chiếu cột không hợp lệ: {str(exc).splitlines()[0]}") from exc
    return list(qualified.named_selects)


def referenced_tables(tree: exp.Expression) -> list[str]:
    """Bảng thật mà câu SQL đọc (bỏ CTE), dạng `schema.bảng` — dùng dựng lineage."""
    ctes, found = _cte_names(tree), []
    for table in tree.find_all(exp.Table):
        if not table.name or isinstance(table.this, exp.Func) or (table.name.lower() in ctes and not table.db):
            continue
        name = f"{(table.db or 'main').lower()}.{table.name}"
        if name not in found:
            found.append(name)
    return found


def _table_label(table: exp.Table) -> str:
    return f"{table.db.lower()}.{table.name}" if table.db else table.name


def _column_label(column: exp.Column, aliases: dict[str, str]) -> str:
    owner = aliases.get(column.table.lower(), column.table) if column.table else ""
    return f"{owner}.{column.name}" if owner else column.name


def _cte_origins(tree: exp.Expression) -> dict[str, str]:
    """CTE chỉ đọc đúng một bảng thật → tên bảng đó (để JOIN qua CTE vẫn hiện bảng gốc)."""
    origins = {}
    for cte in tree.find_all(exp.CTE):
        sources = referenced_tables(cte.this)
        if len(sources) == 1:
            origins[cte.alias_or_name.lower()] = sources[0]
    return origins


def join_keys(tree: exp.Expression) -> list[tuple[str, str, str]]:
    """Cặp cột nối trong `JOIN ... ON a.x = b.y` (bí danh đổi về tên bảng/CTE): (trái, phải, kiểu JOIN)."""
    origins = _cte_origins(tree)
    aliases = {t.alias_or_name.lower(): origins.get(t.name.lower(), _table_label(t)) for t in tree.find_all(exp.Table)}
    pairs = []
    for join in tree.find_all(exp.Join):
        how = (join.side or join.kind or "inner").lower()
        condition = join.args.get("on")
        for eq in condition.find_all(exp.EQ) if condition is not None else []:
            if isinstance(eq.this, exp.Column) and isinstance(eq.expression, exp.Column):
                pairs.append((_column_label(eq.this, aliases), _column_label(eq.expression, aliases), how))
    return pairs


def inline_refs(sql: str, rendered: dict[str, str]) -> str:
    """Nhúng model được ref (staging ephemeral) thành CTE bên ngoài, giống cách dbt biên dịch."""
    used = [name for name in rendered if re.search(rf"\bmain\.{name}\b", sql)]
    for name in used:
        sql = re.sub(rf"\bmain\.{name}\b", name, sql)
    if not used:
        return sql
    ctes = ",\n".join(f"{name} as (\n{rendered[name]}\n)" for name in used)
    return f"with {ctes}\nselect * from (\n{sql}\n)"


def expand_models(rendered: dict[str, str]) -> dict[str, str]:
    """Nhúng ref nhiều tầng (mart → staging, ...), tối đa 3 tầng."""
    expanded = dict(rendered)
    for _ in range(3):
        expanded = {name: inline_refs(sql, expanded) for name, sql in rendered.items()}
    return expanded
