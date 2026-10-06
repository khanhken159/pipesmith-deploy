"""Cấu trúc dữ liệu cho DE (code thuần, 0 token): bảng, schema cột, lineage và khóa nối giữa các bảng.

- Bảng nguồn trước khi chạy pipeline: xem `src/services/source_catalog.py`.
- `run_catalog`: một lần chạy — bảng raw (kiểu, % rỗng, khóa, trùng khóa) + model staging/mart sinh ra (cột, kiểu
  bằng DuckDB DESCRIBE) + lineage (bảng nào đọc bảng nào) + điều kiện JOIN thật trong SQL (sqlglot).
"""

from pathlib import Path

from pydantic import BaseModel

from src.agents.tools.duckdb_tools import RAW_SCHEMA, describe_query, read_catalog
from src.agents.tools.sql_tools import (
    SqlCheckError,
    expand_models,
    inline_refs,
    join_keys,
    parse_single_select,
    referenced_tables,
    render_dbt_sql,
)


class ColumnInfo(BaseModel):
    """Một cột: tên, kiểu, % rỗng (nếu đã soi), có phải khóa không."""

    name: str
    type: str = ""
    null_pct: float | None = None
    is_key: bool = False


class TableInfo(BaseModel):
    """Một bảng trong sơ đồ."""

    id: str  # raw.<bảng> hoặc main.<model>
    name: str
    layer: str  # source | staging | mart
    columns: list[ColumnInfo]
    rows: int | None = None
    duplicate_keys: int | None = None
    file: str = ""  # đường dẫn model dbt (nếu là model sinh ra)
    group: str = ""  # hệ thống nguồn (CRM, ERP, POS...) theo systems.yml
    description: str = ""  # mô tả bảng (systems.yml)


class JoinInfo(BaseModel):
    """Quan hệ giữa hai cột của hai bảng."""

    left: str
    right: str
    how: str  # inner/left/... (JOIN thật) hoặc "gợi ý" (đoán theo tên cột)
    model: str = ""  # model chứa JOIN này
    match_pct: float | None = None  # % giá trị bên trái tìm thấy bên phải (đo bằng DuckDB; phần còn lại là mồ côi)


class LineageEdge(BaseModel):
    """`source` được đọc bởi `target`."""

    source: str
    target: str


class CatalogView(BaseModel):
    """Toàn cảnh cấu trúc dữ liệu cho màn hình DE."""

    tables: list[TableInfo]
    lineage: list[LineageEdge] = []
    joins: list[JoinInfo] = []


def _raw_table(name: str, columns: dict[str, str], profile: dict) -> TableInfo:
    stats = profile.get(name, {})
    col_stats, key = stats.get("columns", {}), stats.get("key_column", "")
    return TableInfo(
        id=f"{RAW_SCHEMA}.{name}",
        name=name,
        layer="source",
        columns=[
            ColumnInfo(name=c, type=t, null_pct=col_stats.get(c, {}).get("null_pct"), is_key=c == key)
            for c, t in columns.items()
        ],
        rows=stats.get("rows"),
        duplicate_keys=stats.get("duplicate_keys"),
    )


class ModelSql(BaseModel):
    """Một model dbt đã render (Jinja → tên bảng thật)."""

    path: str
    name: str
    sql: str


def _models(code_files: dict[str, str]) -> list[ModelSql]:
    models = []
    for path, sql in code_files.items():
        if path.startswith("models/") and path.endswith(".sql"):
            try:
                models.append(ModelSql(path=path, name=Path(path).stem, sql=render_dbt_sql(sql)))
            except SqlCheckError:
                continue  # Jinja lạ đã bị V1 chặn; không vẽ
    return models


def _model_table(model: ModelSql, db: Path, expanded: dict[str, str], grain: list[str]) -> TableInfo:
    columns = describe_query(db, inline_refs(model.sql, expanded))
    layer = "staging" if "/staging/" in model.path else "mart"
    return TableInfo(
        id=f"main.{model.name}",
        name=model.name,
        layer=layer,
        columns=[ColumnInfo(name=c, type=t, is_key=layer == "mart" and c in grain) for c, t in columns.items()],
        file=model.path,
    )


def _relations(model: ModelSql) -> tuple[list[LineageEdge], list[JoinInfo]]:
    try:
        tree = parse_single_select(model.sql)
    except SqlCheckError:
        return [], []
    target = f"main.{model.name}"
    edges = [LineageEdge(source=s, target=target) for s in referenced_tables(tree)]
    joins = [JoinInfo(left=a, right=b, how=how, model=target) for a, b, how in join_keys(tree)]
    return edges, joins


def run_catalog(values: dict) -> CatalogView:
    """Toàn cảnh một lần chạy: raw + staging + mart, lineage, JOIN thật."""
    db = Path(values["workspace"]) / "sandbox.duckdb"
    raw = read_catalog(db).get(RAW_SCHEMA, {}) if db.exists() else {}
    tables = [_raw_table(name, cols, values.get("profile", {})) for name, cols in raw.items()]
    models = _models(values.get("code_files", {}))
    expanded = expand_models({m.name: m.sql for m in models})
    grain = values.get("spec", {}).get("grain", [])
    tables += [_model_table(m, db, expanded, grain) for m in models] if db.exists() else []
    target, rows = values.get("spec", {}).get("target"), values.get("sandbox", {}).get("target_rows")
    tables = [t.model_copy(update={"rows": rows}) if t.id == f"main.{target}" else t for t in tables]
    lineage, joins = [], []
    for model in models:
        edges, pairs = _relations(model)
        lineage += edges
        joins += pairs
    return CatalogView(tables=tables, lineage=lineage, joins=joins)
