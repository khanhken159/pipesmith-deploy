"""Kho dữ liệu raw của công ty bán lẻ đa kênh giả lập "P113 Retail": 8 hệ thống nguồn, 19 bảng, nhiều định dạng
(CSV, JSON, JSON từng dòng, SQLite nhiều bảng, Parquet), khóa liên kết thật giữa các hệ thống và dữ liệu bẩn có
chủ đích (mức bẩn chỉnh bằng `dirty`). Seed cố định → lặp lại được.

Danh mục hệ thống/bảng ghi ra `systems.yml` cạnh dữ liệu (màn "Dữ liệu nguồn" đọc file này để nhóm bảng).
"""

import random
from pathlib import Path

import yaml

from src.services.company.common import (
    Ctx,
    write_csv,
    write_json,
    write_jsonl,
    write_parquet,
    write_sqlite,
)
from src.services.company.master import Master, build_master
from src.services.company.online import OnlineOrder, read_online_orders
from src.services.company.operations import (
    build_ad_spend,
    build_fx_rates,
    build_inventory,
    build_loyalty,
    build_purchase_orders,
    build_shipments,
    build_tickets,
)
from src.services.company.sales import build_payments, build_pos_sales, build_returns, build_web_order_items
from src.services.company.vocab import COMPANY

MANIFEST = "systems.yml"
SYSTEMS = [
    {
        "id": "online",
        "label": "Kênh online",
        "description": "Đơn từ sàn Shopee (CSV), Tiki (API JSON) và website/app (SQLite + API chi tiết đơn)",
        "tables": {
            "shopee_orders": "Đơn Shopee: ngày dd/mm/yyyy lẫn yyyy-mm-dd, tiền dạng '1.075.000', đơn trùng",
            "tiki_orders": "Đơn Tiki từ API: tiền số thực, có đơn thiếu tiền",
            "website_orders": "Đơn website (CSDL SQLite), mã đơn số nguyên",
            "web_order_items": "Chi tiết đơn website (JSON từng dòng): giá lồng trong price.amount, khóa đổi tên order_id/orderId",
        },
    },
    {
        "id": "crm",
        "label": "CRM",
        "description": "Khách hàng và điểm thưởng (SQLite crm.sqlite)",
        "tables": {
            "crm_customers": "Khách hàng: email trùng khác mã, tài khoản test, thành phố nhiều cách viết, ngày sinh 1900-01-01",
            "crm_loyalty_points": "Sổ điểm thưởng: cộng/trừ điểm, mã khách không tồn tại, dòng ghi trùng",
        },
    },
    {
        "id": "erp",
        "label": "ERP",
        "description": "Sản phẩm, nhà cung cấp, cửa hàng/kho, đơn mua hàng (SQLite erp.sqlite)",
        "tables": {
            "erp_products": "Sản phẩm: danh mục rỗng/viết lệch, giá bán 0 hoặc thấp hơn giá vốn, nhà cung cấp mồ côi",
            "erp_suppliers": "Nhà cung cấp: cùng mã số thuế hai mã khác nhau",
            "erp_stores": "20 cửa hàng + 5 kho; một cửa hàng đã đóng cửa",
            "erp_purchase_orders": "Đơn nhập hàng: nhận trước ngày đặt, nhận thiếu/thừa, đơn chưa nhận",
        },
    },
    {
        "id": "pos",
        "label": "Bán tại cửa hàng (POS)",
        "description": "Dòng hàng bán tại quầy, xuất CSV cuối ngày",
        "tables": {
            "pos_sales": "Mỗi dòng một mặt hàng: mã hàng gõ lệch, số lượng âm (trả hàng), giá ×1000, cửa hàng TEST, xuất trùng một ngày",
        },
    },
    {
        "id": "fulfillment",
        "label": "Kho vận & đổi trả",
        "description": "Tồn kho hằng tuần, vận đơn của đối tác giao hàng, yêu cầu đổi trả",
        "tables": {
            "inventory_snapshots": "Tồn kho mỗi thứ Hai: tồn âm, thiếu một tuần của một điểm",
            "shipments": "Vận đơn (API JSON): thời điểm epoch ms, lịch sử trạng thái lồng nhau, đơn có 2 vận đơn",
            "returns_rma": "Đổi trả: một cột tham chiếu cả mã đơn online lẫn số hóa đơn POS, tiền dạng chữ",
        },
    },
    {
        "id": "finance",
        "label": "Thanh toán",
        "description": "Giao dịch cổng thanh toán (Parquet), giờ UTC",
        "tables": {"payments": "Thanh toán: thất bại rồi thành công cho cùng đơn, số tiền lệch đơn, giờ UTC"},
    },
    {
        "id": "marketing",
        "label": "Marketing",
        "description": "Chi phí quảng cáo theo ngày và tỉ giá",
        "tables": {
            "marketing_ad_spend": "Quảng cáo: Google tính USD, kênh khác VND; click > hiển thị; thiếu một ngày; kéo trùng",
            "fx_rates": "Tỉ giá USD→VND chỉ ngày làm việc (cuối tuần phải lấy ngày gần nhất)",
        },
    },
    {
        "id": "people",
        "label": "Nhân sự & CSKH",
        "description": "Nhân viên (có PII nhạy cảm) và phiếu hỗ trợ khách hàng",
        "tables": {
            "hr_employees": "Nhân viên: số CCCD, lương (PII — nên xử lý kiểu ETL), ngày nghỉ trước ngày vào làm",
            "support_tickets": "Phiếu hỗ trợ (JSON từng dòng): số điện thoại trong nội dung, trường chỉ có ở một số dòng",
        },
    },
]


FILES = (
    "crm.sqlite", "erp.sqlite", "hr_employees.csv", "pos_sales.csv", "web_order_items.jsonl", "payments.parquet",
    "returns_rma.csv", "inventory_snapshots.csv", "shipments.json", "marketing_ad_spend.csv", "fx_rates.csv",
    "support_tickets.jsonl", MANIFEST,
)  # fmt: skip


def _write_transactions(ctx: Ctx, master: Master, orders: list[OnlineOrder]) -> None:
    pos = build_pos_sales(ctx, master)
    write_csv(ctx.out_dir / "pos_sales.csv", pos)
    write_jsonl(ctx.out_dir / "web_order_items.jsonl", build_web_order_items(ctx, orders, master))
    write_parquet(ctx.out_dir / "payments.parquet", build_payments(ctx, orders))
    write_csv(ctx.out_dir / "returns_rma.csv", build_returns(ctx, orders, pos, master))


def _write_systems(ctx: Ctx, master: Master) -> None:
    crm = {"customers": master.customers, "loyalty_points": build_loyalty(ctx, master)}
    write_sqlite(ctx.out_dir / "crm.sqlite", crm)
    erp = {"products": master.products, "suppliers": master.suppliers, "stores": master.stores}
    write_sqlite(ctx.out_dir / "erp.sqlite", {**erp, "purchase_orders": build_purchase_orders(ctx, master)})
    write_csv(ctx.out_dir / "hr_employees.csv", master.employees)
    write_csv(ctx.out_dir / "inventory_snapshots.csv", build_inventory(ctx, master))
    write_csv(ctx.out_dir / "marketing_ad_spend.csv", build_ad_spend(ctx))
    write_csv(ctx.out_dir / "fx_rates.csv", build_fx_rates(ctx))


def _write_service(ctx: Ctx, orders: list[OnlineOrder]) -> None:
    write_json(ctx.out_dir / "shipments.json", build_shipments(ctx, orders))
    write_jsonl(ctx.out_dir / "support_tickets.jsonl", build_tickets(ctx, orders))


def generate_company_sources(out_dir: Path, seed: int, options: tuple[float, float]) -> list[str]:
    """Sinh các hệ thống nguồn bổ sung vào `out_dir` (cần 3 nguồn đơn online đã có). `options` = (dirty, scale).

    Trả về danh sách file đã ghi.
    """
    dirty, scale = options
    ctx = Ctx(rng=random.Random(seed * 7919 + 1), dirty=dirty, scale=scale, out_dir=out_dir)
    master = build_master(ctx)
    orders = read_online_orders(out_dir)
    _write_transactions(ctx, master, orders)
    _write_systems(ctx, master)
    _write_service(ctx, orders)
    manifest = {"company": COMPANY, "systems": SYSTEMS}
    (out_dir / MANIFEST).write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return list(FILES)


def read_manifest(sources_dir: Path) -> dict[str, dict]:
    """Bảng → {system, label, description} từ `systems.yml` (rỗng nếu không có)."""
    path = sources_dir / MANIFEST
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        table: {"system": system["id"], "label": system["label"], "description": text}
        for system in data.get("systems", [])
        for table, text in (system.get("tables") or {}).items()
    }
