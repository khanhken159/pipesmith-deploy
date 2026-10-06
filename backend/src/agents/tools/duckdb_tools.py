"""Công cụ DuckDB (code tin cậy của hệ thống, không chạy code do LLM sinh trừ khi đã qua V1)."""

import json
import sqlite3
import statistics
import tempfile
import time
from contextlib import closing
from pathlib import Path

import duckdb
from pydantic import BaseModel, Field

from src.agents.tools.pii import mask_rows
from src.models.evidence import QueryMetrics
from src.models.spec import SourceRef

FILE_KINDS = {
    ".csv": "csv",
    ".json": "json",
    ".jsonl": "json",
    ".ndjson": "json",
    ".parquet": "parquet",
    ".sqlite": "sqlite",
    ".db": "sqlite",
}
NON_TABULAR_KINDS = {".png": "image", ".jpg": "image", ".jpeg": "image", ".pdf": "pdf"}
SQLITE_TYPES = {"INTEGER": "BIGINT", "INT": "BIGINT", "REAL": "DOUBLE", "NUMERIC": "DOUBLE", "TEXT": "VARCHAR"}
RAW_SCHEMA = "raw"
# DuckDB gộp các kết nối cùng tệp trong một tiến trình và báo lỗi nếu cấu hình khác nhau (API đọc catalog song song
# với luồng chạy pipeline) → MỌI kết nối chỉ-đọc dùng chung đúng một cấu hình này.
READ_CONFIG = {"enable_external_access": False}


def connect_read(db_path: Path) -> duckdb.DuckDBPyConnection:
    """Kết nối chỉ-đọc, cấu hình thống nhất toàn hệ thống."""
    return duckdb.connect(str(db_path), read_only=True, config=READ_CONFIG)


class SourceInfo(BaseModel):
    """Nguồn phát hiện trong thư mục dữ liệu: tên, loại, schema và vài dòng mẫu (đã che PII)."""

    name: str
    kind: str
    path: str
    table: str = Field(default="", description="Tên bảng trong file SQLite")
    columns: dict[str, str] = Field(default_factory=dict)
    sample: list[dict] = Field(default_factory=list)


class QueryResult(BaseModel):
    """Kết quả một truy vấn: tên cột, kiểu cột, các dòng."""

    columns: list[str]
    types: list[str]
    rows: list[tuple]


def quote_path(path: Path) -> str:
    """Đường dẫn dạng chuỗi SQL an toàn."""
    return "'" + path.resolve().as_posix().replace("'", "''") + "'"


def read_expr(source: SourceRef) -> str:
    """Biểu thức đọc file nguồn (CSV giữ nguyên chuỗi ở tầng raw — đúng tinh thần ELT)."""
    path = quote_path(Path(source.path))
    if source.kind == "csv":
        return f"read_csv({path}, all_varchar = true, header = true)"
    if source.kind == "parquet":
        return f"read_parquet({path})"
    return f"read_json_auto({path})"  # nhận cả JSON mảng lẫn JSON từng dòng (jsonl)


def _sqlite_table_names(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        return [r[0] for r in rows.fetchall()]


def _sqlite_columns(path: Path, table: str) -> dict[str, str]:
    with closing(sqlite3.connect(path)) as conn:
        info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {row[1]: SQLITE_TYPES.get(str(row[2]).upper(), "VARCHAR") for row in info}


def _sqlite_rows(path: Path, table: str, limit: int | None = None) -> list[tuple]:
    sql = f'SELECT * FROM "{table}"' + (f" LIMIT {int(limit)}" if limit else "")
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(sql).fetchall()


def _sqlite_sources(path: Path) -> list[SourceInfo]:
    infos = []
    for table in _sqlite_table_names(path):
        name = path.stem if table == path.stem else f"{path.stem}_{table}"
        columns = _sqlite_columns(path, table)
        sample = [dict(zip(columns, row, strict=False)) for row in _sqlite_rows(path, table, 3)]
        infos.append(SourceInfo(name=name, kind="sqlite", path=str(path), table=table, columns=columns, sample=sample))
    return infos


def _file_source(path: Path, kind: str) -> SourceInfo:
    ref = SourceRef(name=path.stem, kind=kind, path=str(path))
    with duckdb.connect() as con:
        rel = con.sql(f"SELECT * FROM {read_expr(ref)} LIMIT 3")
        columns = dict(zip(rel.columns, [str(t) for t in rel.types], strict=True))
        sample = [dict(zip(rel.columns, row, strict=True)) for row in rel.fetchall()]
    return SourceInfo(name=path.stem, kind=kind, path=str(path), columns=columns, sample=sample)


def discover_sources(sources_dir: Path) -> list[SourceInfo]:
    """Liệt kê nguồn trong thư mục: schema thật + 3 dòng mẫu đã che PII."""
    infos: list[SourceInfo] = []
    for path in sorted(sources_dir.glob("*")):
        suffix = path.suffix.lower()
        if suffix in (".sqlite", ".db"):
            infos.extend(_sqlite_sources(path))
        elif suffix in FILE_KINDS:
            infos.append(_file_source(path, FILE_KINDS[suffix]))
        elif suffix in NON_TABULAR_KINDS:
            infos.append(SourceInfo(name=path.stem, kind=NON_TABULAR_KINDS[suffix], path=str(path)))
    for info in infos:
        info.sample = mask_rows(info.sample)
    return infos


def _ingest_sqlite(con: duckdb.DuckDBPyConnection, info: SourceInfo) -> None:
    """Đổ bảng SQLite ra JSON tạm (giữ đúng kiểu cột) rồi DuckDB đọc một lần — nhanh hơn chèn từng dòng rất nhiều."""
    names = list(info.columns)
    types = ", ".join(f"'{n.replace(chr(39), chr(39) * 2)}': '{t}'" for n, t in info.columns.items())
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "rows.jsonl"
        rows = _sqlite_rows(Path(info.path), info.table)
        lines = (json.dumps(dict(zip(names, row, strict=True)), default=str) for row in rows)
        path.write_text("\n".join(lines), encoding="utf-8")
        reader = f"read_json({quote_path(path)}, format = 'newline_delimited', columns = {{{types}}})"
        con.execute(f'CREATE OR REPLACE TABLE {RAW_SCHEMA}."{info.name}" AS SELECT * FROM {reader}')


def ingest_sources(db_path: Path, sources: list[SourceInfo]) -> dict[str, int]:
    """E0: nạp từng nguồn dạng bảng vào schema `raw` của sandbox; trả về số dòng mỗi bảng."""
    counts: dict[str, int] = {}
    with duckdb.connect(str(db_path)) as con:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA}")
        for info in sources:
            if info.kind == "sqlite":
                _ingest_sqlite(con, info)
            elif info.kind in ("csv", "json", "parquet"):
                expr = read_expr(SourceRef(name=info.name, kind=info.kind, path=info.path))
                con.execute(f'CREATE OR REPLACE TABLE {RAW_SCHEMA}."{info.name}" AS SELECT * FROM {expr}')
            else:
                continue
            counts[info.name] = con.execute(f'SELECT count(*) FROM {RAW_SCHEMA}."{info.name}"').fetchone()[0]
    return counts


def read_catalog(db_path: Path) -> dict[str, dict[str, dict[str, str]]]:
    """Danh mục thật: {schema: {bảng: {cột: kiểu}}}."""
    sql = "SELECT table_schema, table_name, column_name, data_type FROM information_schema.columns ORDER BY ordinal_position"
    catalog: dict[str, dict[str, dict[str, str]]] = {}
    with connect_read(db_path) as con:
        for schema, table, column, dtype in con.execute(sql).fetchall():
            catalog.setdefault(schema, {}).setdefault(table, {})[column] = dtype
    return catalog


def run_query(db_path: Path, sql: str) -> QueryResult:
    """Chạy một câu SELECT (đã qua V1) ở chế độ chỉ đọc, chặn truy cập file ngoài."""
    with connect_read(db_path) as con:
        rel = con.sql(sql)
        return QueryResult(columns=rel.columns, types=[str(t) for t in rel.types], rows=rel.fetchall())


def explain_error(db_path: Path, sql: str) -> str:
    """Cho DuckDB biên dịch thử câu SELECT (EXPLAIN, không đọc dữ liệu); trả về lỗi đầu tiên, rỗng nếu được."""
    try:
        with connect_read(db_path) as con:
            con.execute(f"EXPLAIN {sql}")
    except duckdb.Error as exc:
        return str(exc).strip().splitlines()[0]
    return ""


def explain_analyze(db_path: Path, sql: str) -> str:
    """Kế hoạch thực thi có số đo thật (EXPLAIN ANALYZE)."""
    with connect_read(db_path) as con:
        rows = con.execute(f"EXPLAIN ANALYZE {sql}").fetchall()
    return "\n".join(str(row[-1]) for row in rows)


def benchmark_query(db_path: Path, sql: str, runs: int) -> QueryMetrics:
    """Đo thời gian: 1 lần khởi động + `runs` lần, lấy trung vị (mili giây)."""
    timings: list[float] = []
    with connect_read(db_path) as con:
        con.execute(sql).fetchall()
        for _ in range(runs):
            start = time.perf_counter()
            con.execute(sql).fetchall()
            timings.append((time.perf_counter() - start) * 1000)
    return QueryMetrics(median_ms=round(statistics.median(timings), 3), runs=runs)


def materialize_views(db_path: Path, models: dict[str, str]) -> None:
    """Tạo các model trung gian (đã qua V1) thành bảng `main.<tên>` trên một bộ dữ liệu."""
    with duckdb.connect(str(db_path), config={"enable_external_access": False}) as con:
        for name, sql in models.items():
            con.execute(f'CREATE OR REPLACE TABLE main."{name}" AS {sql}')


def describe_query(db_path: Path, sql: str) -> dict[str, str]:
    """Cột → kiểu của một câu SELECT (DuckDB DESCRIBE, không đọc dữ liệu); rỗng nếu không biên dịch được."""
    try:
        with connect_read(db_path) as con:
            return {row[0]: row[1] for row in con.execute(f"DESCRIBE ({sql})").fetchall()}
    except duckdb.Error:
        return {}
