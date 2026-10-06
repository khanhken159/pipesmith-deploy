"""Test E0 nhận nguồn, P soi dữ liệu, E2 dữ liệu thử (code thuần, chạy trên dữ liệu giả lập)."""

from datetime import date
from pathlib import Path

import duckdb

from src.agents.tools.duckdb_tools import discover_sources, read_catalog


def _count(db: str, table: str) -> int:
    with duckdb.connect(db, read_only=True) as con:
        return con.execute(f'SELECT count(*) FROM raw."{table}"').fetchone()[0]


def test_discover_sources_reads_schema_and_masks_pii(seeded_sources: Path):
    infos = {i.name: i for i in discover_sources(seeded_sources)}
    assert set(infos) == {"shopee_orders", "tiki_orders", "website_orders"}
    assert infos["website_orders"].kind == "sqlite" and infos["website_orders"].table == "orders"
    assert infos["shopee_orders"].columns["total_amount"] == "VARCHAR"  # tầng raw giữ nguyên chuỗi
    assert "***@" in infos["shopee_orders"].sample[0]["customer_email"]


def test_ingest_loads_every_source(pipeline_state: dict):
    assert pipeline_state["row_counts"] == {"shopee_orders": 126, "tiki_orders": 120, "website_orders": 120}
    raw = read_catalog(Path(pipeline_state["workspace"]) / "sandbox.duckdb")["raw"]
    assert set(raw) == {"shopee_orders", "tiki_orders", "website_orders"}
    assert (Path(pipeline_state["workspace"]) / "models" / "sources.yml").exists()


def test_profile_detects_keys_duplicates_and_formats(pipeline_state: dict):
    shopee = pipeline_state["profile"]["shopee_orders"]
    assert shopee["key_column"] == "order_id"
    assert shopee["duplicate_keys"] == 6
    assert "vnd_dot (1.075.000)" in shopee["columns"]["total_amount"]["money_formats"]
    assert set(shopee["columns"]["order_date"]["date_formats"]) == {"dd/mm/yyyy", "yyyy-mm-dd"}
    assert all("***@" in v for v in shopee["columns"]["customer_email"]["examples"])
    assert pipeline_state["profile"]["website_orders"]["columns"]["order_id"]["type"] == "BIGINT"


def test_mock_datasets_have_expected_shapes(pipeline_state: dict):
    datasets = pipeline_state["datasets"]
    assert set(datasets) == {"small", "large", "dirty", "empty", "few", "dupkeys"}
    assert _count(datasets["empty"], "tiki_orders") == 0
    assert _count(datasets["few"], "tiki_orders") == 3
    assert _count(datasets["large"], "tiki_orders") >= 20000
    assert _count(datasets["dirty"], "tiki_orders") == _count(datasets["small"], "tiki_orders") + 5
    with duckdb.connect(datasets["dupkeys"], read_only=True) as con:
        dup = con.execute("SELECT count(*) - count(DISTINCT id) FROM raw.tiki_orders").fetchone()[0]
    assert dup == 5


def test_large_dataset_keeps_numeric_key_type(pipeline_state: dict):
    with duckdb.connect(pipeline_state["datasets"]["large"], read_only=True) as con:
        dtype = con.execute("SELECT typeof(order_id) FROM raw.website_orders LIMIT 1").fetchone()[0]
        unique = con.execute("SELECT count(*) = count(DISTINCT order_id) FROM raw.website_orders").fetchone()[0]
    assert dtype == "BIGINT" and unique


def test_ingest_reads_parquet_and_jsonl(tmp_path: Path):
    """Nguồn dạng Parquet (giữ kiểu) và JSON từng dòng (jsonl) — định dạng của ELT-Bench."""
    from src.agents.tools.duckdb_tools import ingest_sources

    src = tmp_path / "sources"
    src.mkdir()
    with duckdb.connect() as con:
        con.execute(
            f"COPY (SELECT 1::BIGINT AS id, 2.5 AS score) TO '{(src / 'scores.parquet').as_posix()}' (FORMAT parquet)"
        )
    (src / "people.jsonl").write_text('{"id": "1", "name": "An"}\n{"id": "2", "name": "Binh"}\n', encoding="utf-8")
    infos = {i.name: i for i in discover_sources(src)}
    assert infos["scores"].kind == "parquet" and infos["scores"].columns["id"] == "BIGINT"
    assert infos["people"].kind == "json"
    counts = ingest_sources(tmp_path / "db.duckdb", list(infos.values()))
    assert counts == {"people": 2, "scores": 1}


def test_profile_parse_expressions_run_on_raw_data(pipeline_state: dict):
    """Biểu thức `duckdb_parse` gợi ý cho LLM phải chạy được và đọc được mọi giá trị khác rỗng."""
    shopee = pipeline_state["profile"]["shopee_orders"]["columns"]
    assert shopee["order_date"]["duckdb_parse"].startswith("coalesce(try_strptime(")
    assert shopee["total_amount"]["duckdb_parse"] == "try_cast(replace(\"total_amount\", '.', '') as bigint)"
    db = str(Path(pipeline_state["workspace"]) / "sandbox.duckdb")
    with duckdb.connect(db, read_only=True) as con:
        for column in ("order_date", "total_amount"):
            expression = shopee[column]["duckdb_parse"]
            unparsed = con.execute(
                f'SELECT count(*) FROM raw.shopee_orders WHERE "{column}" IS NOT NULL AND {expression} IS NULL'
            ).fetchone()[0]
            assert unparsed == 0, column


def _raw_table(tmp_path: Path, rows: list[tuple[str, str, str]]) -> Path:
    db = tmp_path / "formats.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute("CREATE SCHEMA raw; CREATE TABLE raw.t (sold_at VARCHAR, unit_price VARCHAR, store_code VARCHAR)")
        con.executemany("INSERT INTO raw.t VALUES (?, ?, ?)", rows)
    return db


def test_profiler_reads_every_messy_date_and_money_format(tmp_path: Path):
    """Ngày/tiền nhiều kiểu viết (dữ liệu POS thật thường gặp) phải đọc ra đúng giá trị, không chỉ 'khác NULL'."""
    from src.agents.nodes.profiler import profile_table

    rows = [
        ("05/09/2026 15:30:00", "1.075.000", "ST001"),
        ("09/05/2026 03:30 PM", "1,075,000", "st001"),
        ("2026-09-05T15:30:00+07:00", "1075000.0", " ST001"),
        ("2026-09-05 15:30:00", "1075k", "ST001"),
        ("20260905", "1.075.000đ", "ST001"),
    ]
    db = _raw_table(tmp_path, rows)
    columns = profile_table(db, "t", {"sold_at": "VARCHAR", "unit_price": "VARCHAR", "store_code": "VARCHAR"})[
        "columns"
    ]
    assert columns["sold_at"]["parse_failures"] == 0 and columns["unit_price"]["parse_failures"] == 0
    with duckdb.connect(str(db), read_only=True) as con:
        dates = con.execute(f"SELECT DISTINCT CAST({columns['sold_at']['duckdb_parse']} AS DATE) FROM raw.t").fetchall()
        money = con.execute(f"SELECT DISTINCT {columns['unit_price']['duckdb_parse']} FROM raw.t").fetchall()
    assert dates == [(date(2026, 9, 5),)] and money == [(1_075_000,)]
    assert (
        columns["store_code"]["case_variants"] == 2
        and columns["store_code"]["normalize"] == 'upper(trim("store_code"))'
    )


def test_vnd_dot_amounts_are_not_mistaken_for_decimals():
    from src.agents.nodes.profiler import MONEY_PATTERNS, money_expression

    assert not MONEY_PATTERNS["plain number"].match("125.000")
    assert money_expression("x", ["vnd_dot (1.075.000)"]) == "try_cast(replace(\"x\", '.', '') as bigint)"


def test_large_dataset_keeps_joins_one_to_one(tmp_path: Path):
    """Bảng danh mục nhỏ bị nhân bản nhiều lần: nối qua khóa ngoại (sku) không được bùng nổ số dòng."""
    from src.agents.nodes.mock_data import DatasetJob, TableRecipe, build_dataset

    source = tmp_path / "sandbox.duckdb"
    with duckdb.connect(str(source)) as con:
        con.execute("CREATE SCHEMA raw")
        con.execute("CREATE TABLE raw.products AS SELECT i AS product_id, 'SKU-' || i AS sku FROM range(10) t(i)")
        con.execute("CREATE TABLE raw.sales AS SELECT i AS line_id, 'SKU-' || (i % 10) AS sku FROM range(100) t(i)")
    recipes = [
        TableRecipe(table="products", rows=10, key="product_id", key_numeric=True, link_columns={"sku": False}),
        TableRecipe(table="sales", rows=100, key="line_id", key_numeric=True, link_columns={"sku": False}),
    ]
    target = tmp_path / "large.duckdb"
    build_dataset(DatasetJob(name="large", source_db=source, target=target), recipes)
    with duckdb.connect(str(target), read_only=True) as con:
        sales = con.execute("SELECT count(*) FROM raw.sales").fetchone()[0]
        joined = con.execute("SELECT count(*) FROM raw.sales s JOIN raw.products p USING (sku)").fetchone()[0]
    assert sales > 100 and joined == sales
