"""Kho raw công ty giả lập (P113 Retail): lặp lại được, có đủ hệ thống, khóa liên kết thật, bẩn đúng chủ đích."""

import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from src.agents.tools.duckdb_tools import discover_sources, ingest_sources
from src.services.company import SYSTEMS, read_manifest
from src.services.seed import SeedConfig, generate_sources
from src.services.source_catalog import source_catalog

SCALE = 0.3


def _generate(out: Path, dirty: float) -> Path:
    generate_sources(SeedConfig(out_dir=out, seed=42, dirty=dirty, profile="company", scale=SCALE))
    return out


@pytest.fixture(scope="module")
def company(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _generate(tmp_path_factory.mktemp("company") / "sources", 0.05)


@pytest.fixture(scope="module")
def raw(company: Path, tmp_path_factory: pytest.TempPathFactory) -> duckdb.DuckDBPyConnection:
    db = tmp_path_factory.mktemp("sandbox") / "sandbox.duckdb"
    ingest_sources(db, discover_sources(company))
    con = duckdb.connect(str(db), read_only=True)
    yield con
    con.close()


def _count(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    return con.execute(sql).fetchone()[0]


def _digest(folder: Path) -> dict[str, str]:
    files = (p for p in folder.iterdir() if p.suffix in (".csv", ".jsonl", ".json", ".yml"))
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def test_every_table_is_discovered_and_described(company: Path):
    names = {s.name for s in discover_sources(company)}
    manifest = read_manifest(company)
    assert len(names) == 19 and names == set(manifest)
    assert {meta["label"] for meta in manifest.values()} == {s["label"] for s in SYSTEMS}
    assert {"csv", "json", "sqlite", "parquet"} <= {s.kind for s in discover_sources(company)}


def test_same_seed_gives_same_files(company: Path, tmp_path: Path):
    assert _digest(_generate(tmp_path / "again", 0.05)) == _digest(company)


@pytest.mark.parametrize(
    ("check", "sql"),
    [
        ("email khách trùng khác mã", "SELECT count(*) - count(DISTINCT lower(trim(email))) FROM raw.crm_customers"),
        ("số lượng âm ở POS", "SELECT count(*) FROM raw.pos_sales WHERE CAST(qty AS INT) < 0"),
        ("cửa hàng TEST", "SELECT count(*) FROM raw.pos_sales WHERE store_code = 'TEST'"),
        ("khóa JSON đổi tên", "SELECT count(*) FROM raw.web_order_items WHERE orderId IS NOT NULL"),
        ("nhận hàng trước ngày đặt", "SELECT count(*) FROM raw.erp_purchase_orders WHERE received_at < ordered_at"),
        ("tồn kho âm", "SELECT count(*) FROM raw.inventory_snapshots WHERE CAST(on_hand AS INT) < 0"),
        (
            "click > lượt hiển thị",
            "SELECT count(*) FROM raw.marketing_ad_spend WHERE CAST(clicks AS INT) > CAST(impressions AS INT)",
        ),
        ("thanh toán nhiều lần một đơn", "SELECT count(*) - count(DISTINCT order_ref) FROM raw.payments"),
        ("nhà cung cấp trùng mã số thuế", "SELECT count(*) - count(DISTINCT tax_code) FROM raw.erp_suppliers"),
        ("giá bán dưới giá vốn", "SELECT count(*) FROM raw.erp_products WHERE list_price < unit_cost"),
    ],
)
def test_dirt_is_present(raw: duckdb.DuckDBPyConnection, check: str, sql: str):
    assert _count(raw, sql) > 0, check


def test_systems_link_through_real_keys(raw: duckdb.DuckDBPyConnection):
    online_emails = (
        "SELECT count(*) FROM raw.shopee_orders s JOIN raw.crm_customers c ON lower(trim(c.email)) = s.customer_email"
    )
    assert _count(raw, online_emails) > 0
    matched = _count(raw, "SELECT count(*) FROM raw.pos_sales p JOIN raw.erp_products e ON p.sku = e.sku")
    assert matched > 0.8 * _count(raw, "SELECT count(*) FROM raw.pos_sales")
    sums = """SELECT count(*) FILTER (WHERE i.total = o.amount_vnd), count(*) FROM (
        SELECT coalesce(order_id, orderId) AS id, sum(qty * price.amount) AS total FROM raw.web_order_items GROUP BY 1
    ) i JOIN raw.website_orders o ON o.order_id = i.id"""
    equal, total = raw.execute(sums).fetchone()
    assert equal > 0.8 * total  # chi tiết đơn cộng lại khớp tiền đơn, trừ vài đơn lệch có chủ đích


def test_fx_rates_skip_weekends(raw: duckdb.DuckDBPyConnection):
    weekend = "SELECT count(*) FROM raw.fx_rates WHERE dayofweek(CAST(rate_date AS DATE)) IN (0, 6)"
    assert _count(raw, weekend) == 0 and _count(raw, "SELECT count(*) FROM raw.fx_rates") > 0


def test_clean_profile_has_no_planted_dirt(tmp_path: Path):
    clean = _generate(tmp_path / "clean", 0.0)
    lines = (clean / "web_order_items.jsonl").read_text(encoding="utf-8").splitlines()
    assert all("orderId" not in json.loads(line) for line in lines)
    assert "TEST-" not in (clean / "pos_sales.csv").read_text(encoding="utf-8")


def test_source_catalog_groups_tables_and_measures_joins(company: Path):
    view = source_catalog(company)
    tables = {t.name: t for t in view.tables}
    assert tables["erp_products"].group == "ERP" and tables["erp_products"].description
    assert tables["web_order_items"].duplicate_keys is None  # order_id không phải khóa của bảng chi tiết
    joins = {(j.left, j.right): j.match_pct for j in view.joins}
    assert joins[("raw.pos_sales.sku", "raw.erp_products.sku")] < 100  # có mã hàng gõ lệch / mồ côi
    assert joins[("raw.inventory_snapshots.sku", "raw.erp_products.sku")] == 100
    assert not any("shopee_orders.order_id" in left for left, _ in joins)  # trùng tên cột nhưng khác nghĩa


def test_mock_planner_picks_only_order_sources(company: Path):
    from src.services.llm_mock import mock_planner

    catalog = [s.model_dump() for s in discover_sources(company)]
    spec = mock_planner({"source_catalog": json.dumps(catalog, default=str), "answers": "(chưa có)"})
    assert {s["name"] for s in spec["sources"]} == {"shopee_orders", "tiki_orders", "website_orders"}
