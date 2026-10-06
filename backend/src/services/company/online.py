"""Đọc lại 3 nguồn đơn online đã sinh (Shopee CSV, Tiki JSON, website SQLite) về dạng sạch, để các hệ thống khác
(chi tiết đơn, vận chuyển, thanh toán, đổi trả, CSKH) tham chiếu đúng mã đơn thật.
"""

import csv
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel


class OnlineOrder(BaseModel):
    """Một đơn online (đã chuẩn hóa) — chỉ dùng nội bộ khi sinh dữ liệu."""

    ref: str  # mã đơn như hệ thống khác ghi: SP00012, TK00003, WEB-12
    channel: str  # shopee | tiki | website
    created: datetime
    ok: bool  # đơn thành công (không hủy/hoàn)
    amount: int
    email: str


def _parse_shopee_day(text: str) -> datetime:
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).replace(hour=10)
        except ValueError:
            continue
    return datetime(2026, 9, 1, 10)


def _amount(text: object) -> int:
    digits = "".join(ch for ch in str(text or "") if ch.isdigit())
    return int(digits) if digits else 0


def _shopee(path: Path) -> list[OnlineOrder]:
    with path.open(encoding="utf-8") as handle:
        rows = list({r["order_id"]: r for r in csv.DictReader(handle)}.values())
    return [
        OnlineOrder(
            ref=r["order_id"],
            channel="shopee",
            created=_parse_shopee_day(r["order_date"]),
            ok=r["status"] == "COMPLETED",
            amount=_amount(r["total_amount"]),
            email=r["customer_email"],
        )
        for r in rows
    ]


def _tiki(path: Path) -> list[OnlineOrder]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [
        OnlineOrder(
            ref=r["id"],
            channel="tiki",
            created=datetime.fromisoformat(r["created_at"]),
            ok=r["state"] == "delivered",
            amount=int(r["grand_total"] or 0),
            email=r["buyer_email"],
        )
        for r in rows
    ]


def _website(path: Path) -> list[OnlineOrder]:
    with closing(sqlite3.connect(path)) as conn:
        rows = conn.execute("SELECT order_id, created_ts, status, amount_vnd, email FROM orders").fetchall()
    return [
        OnlineOrder(
            ref=f"WEB-{order_id}",
            channel="website",
            created=datetime.fromisoformat(created),
            ok=status == "paid",
            amount=amount,
            email=email,
        )
        for order_id, created, status, amount, email in rows
    ]


def read_online_orders(out_dir: Path) -> list[OnlineOrder]:
    """Mọi đơn online của 3 kênh (mỗi mã đơn một lần)."""
    return (
        _shopee(out_dir / "shopee_orders.csv")
        + _tiki(out_dir / "tiki_orders.json")
        + _website(out_dir / "website.sqlite")
    )
