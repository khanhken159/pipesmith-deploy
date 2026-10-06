"""Toàn cảnh kho nguồn (chưa chạy pipeline) cho màn "Dữ liệu nguồn": bảng nhóm theo hệ thống, schema, số dòng,
% rỗng, trùng khóa (dùng lại bộ soi P) và gợi ý khóa nối — code thuần, 0 token.

Gợi ý khóa nối: cột dạng khóa (`*_id`, `*_code`, `*_ref`, `sku`) xuất hiện ở nhiều bảng → nối về bảng mà cột đó là
khóa duy nhất (ví dụ `pos_sales.sku` → `erp_products.sku`); thêm luật `orders.customer_id` ↔ `customers.id`. Mỗi gợi ý
được đo tỉ lệ khớp thật trên dữ liệu; khớp dưới MIN_MATCH_PCT thì bỏ.
Kết quả được nhớ theo dấu thời gian các file nguồn (đổi dữ liệu thì tính lại).
"""

import re
import tempfile
from functools import lru_cache
from pathlib import Path

import duckdb

from src.agents.nodes.profiler import profile_table
from src.agents.tools.duckdb_tools import (
    RAW_SCHEMA,
    SourceInfo,
    connect_read,
    discover_sources,
    ingest_sources,
    read_catalog,
)
from src.services.catalog import CatalogView, ColumnInfo, JoinInfo, TableInfo
from src.services.company import read_manifest

KEY_LIKE = re.compile(r"^(sku|.*_(id|code|ref))$", re.I)
MIN_KEY_RATIO = 0.8  # số giá trị khác nhau / số dòng tối thiểu để coi một cột là khóa của bảng
MIN_MATCH_PCT = 20.0  # dưới mức này coi như trùng tên nhưng khác nghĩa (ví dụ mã đơn Shopee vs website)


def _singular(name: str) -> str:
    return name[:-1] if name.endswith("s") else name


def key_ratios(profile: dict) -> dict[str, float]:
    """Cột → mức "giống khóa" = số giá trị khác nhau / số dòng (1.0 = duy nhất, không rỗng)."""
    rows = profile.get("rows", 0)
    return {c: (s.get("distinct", 0) / rows if rows else 0.0) for c, s in profile.get("columns", {}).items()}


def _key_joins(tables: dict[str, list[str]], ratios: dict[str, dict[str, float]]) -> list[JoinInfo]:
    users_of: dict[str, list[str]] = {}
    for table, columns in tables.items():
        for column in (c for c in columns if KEY_LIKE.match(c)):
            users_of.setdefault(column, []).append(table)
    joins = []
    for column, users in users_of.items():
        if len(users) < 2:
            continue
        owner = max(users, key=lambda t: ratios.get(t, {}).get(column, 0.0))  # bảng mà cột gần như là khóa chính
        for table in (t for t in users if t != owner):
            joins.append(JoinInfo(left=f"raw.{table}.{column}", right=f"raw.{owner}.{column}", how="gợi ý"))
    return joins


def _named_joins(tables: dict[str, list[str]]) -> list[JoinInfo]:
    joins = []
    for left, columns in tables.items():
        for right, other in tables.items():
            fk = f"{_singular(right)}_id"
            if left != right and fk in columns and "id" in other and fk not in other:
                joins.append(JoinInfo(left=f"raw.{left}.{fk}", right=f"raw.{right}.id", how="gợi ý"))
    return joins


def suggested_joins(tables: dict[str, list[str]], ratios: dict[str, dict[str, float]]) -> list[JoinInfo]:
    """Gợi ý quan hệ giữa các bảng nguồn theo tên cột + mức duy nhất đo được."""
    return _key_joins(tables, ratios) + _named_joins(tables)


def _owner_column(label: str) -> tuple[str, str]:
    table, column = label.removeprefix(f"{RAW_SCHEMA}.").rsplit(".", 1)
    return f'{RAW_SCHEMA}."{table}"', f'"{column}"'


def match_pct(con: duckdb.DuckDBPyConnection, join: JoinInfo) -> float:
    """% dòng (cột trái khác rỗng) tìm thấy giá trị ở cột phải; so dạng chuỗi nguyên văn (không tự làm sạch)."""
    (lt, lc), (rt, rc) = _owner_column(join.left), _owner_column(join.right)
    sql = (
        f"SELECT count(*), count(r.v) FROM (SELECT CAST({lc} AS VARCHAR) v FROM {lt} WHERE {lc} IS NOT NULL) l "
        f"LEFT JOIN (SELECT DISTINCT CAST({rc} AS VARCHAR) v FROM {rt}) r ON l.v = r.v"
    )
    total, found = con.execute(sql).fetchone()
    return round(100 * found / total, 1) if total else 0.0


def _analyze(sources: list[SourceInfo]) -> tuple[dict[str, dict[str, str]], dict[str, dict], list[JoinInfo]]:
    """Nạp nguồn vào DuckDB tạm: kiểu cột tầng raw, hồ sơ từng bảng, gợi ý nối đã đo tỉ lệ khớp."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "catalog.duckdb"
        ingest_sources(db, sources)
        raw = read_catalog(db).get(RAW_SCHEMA, {})
        profiles = {table: profile_table(db, table, columns) for table, columns in raw.items()}
        ratios = {name: key_ratios(profile) for name, profile in profiles.items()}
        candidates = suggested_joins({n: list(c) for n, c in raw.items()}, ratios)
        with connect_read(db) as con:
            measured = [j.model_copy(update={"match_pct": match_pct(con, j)}) for j in candidates]
    return raw, profiles, [j for j in measured if j.match_pct >= MIN_MATCH_PCT]


def _table(name: str, columns: dict[str, str], profile: dict) -> TableInfo:
    """Chỉ coi là khóa (và báo trùng khóa) khi cột gần như duy nhất — `order_id` của bảng chi tiết đơn thì không."""
    stats = profile.get("columns", {})
    key = profile.get("key_column", "")
    if key and key_ratios(profile).get(key, 0.0) < MIN_KEY_RATIO:
        key = ""
    return TableInfo(
        id=f"{RAW_SCHEMA}.{name}",
        name=name,
        layer="source",
        columns=[
            ColumnInfo(name=c, type=t, null_pct=stats.get(c, {}).get("null_pct"), is_key=c == key)
            for c, t in columns.items()
        ],
        rows=profile.get("rows"),
        duplicate_keys=profile.get("duplicate_keys") if key else None,
    )


@lru_cache(maxsize=4)
def _cached_catalog(sources_dir: str, signature: tuple) -> CatalogView:
    directory = Path(sources_dir)
    sources = [s for s in discover_sources(directory) if s.kind in ("csv", "json", "parquet", "sqlite")]
    raw, profiles, joins = _analyze(sources)
    manifest = read_manifest(directory)
    tables = []
    for name, columns in raw.items():
        meta = manifest.get(name, {})
        table = _table(name, columns, profiles[name])
        tables.append(
            table.model_copy(update={"group": meta.get("label", ""), "description": meta.get("description", "")})
        )
    return CatalogView(tables=tables, joins=joins)


def source_catalog(sources_dir: Path) -> CatalogView:
    """Bảng nguồn + hồ sơ dữ liệu + gợi ý quan hệ (nhớ kết quả tới khi file nguồn thay đổi)."""
    files = sorted(sources_dir.glob("*")) if sources_dir.exists() else []
    signature = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in files if p.is_file())
    return _cached_catalog(str(sources_dir.resolve()), signature)
