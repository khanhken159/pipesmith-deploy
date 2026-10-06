"""Giao dịch bán hàng: POS cửa hàng (CSV xuất từ phần mềm bán hàng), chi tiết đơn website (JSON từng dòng),
thanh toán (Parquet của cổng thanh toán), đổi trả (CSV).

Bẩn có chủ đích: xuất trùng cả một ngày của một cửa hàng, cửa hàng TEST, mã hàng viết lệch (chữ thường, thiếu
gạch, có khoảng trắng), mã hàng không có trong ERP, số lượng âm (trả hàng ghi ngược), giá gõ nhầm ×1000,
phương thức thanh toán nhiều cách viết, khóa JSON đổi tên giữa chừng (`order_id` → `orderId`), thanh toán nhiều
lần cho một đơn (thất bại rồi thành công), giờ UTC lẫn giờ Việt Nam.
"""

from datetime import timedelta

from src.services.company.common import (
    START,
    Ctx,
    messy_case,
    messy_datetime,
    messy_money,
    messy_variant,
    with_duplicates,
)
from src.services.company.master import Master, active_store_codes
from src.services.company.online import OnlineOrder
from src.services.company.vocab import PAYMENT_METHODS, RETURN_REASONS


def messy_sku(ctx: Ctx, sku: str) -> str:
    """Mã hàng gõ tay ở quầy: chữ thường, bỏ gạch, có khoảng trắng."""
    if not ctx.chance(2):
        return sku
    return ctx.pick((sku.lower(), sku.replace("-", ""), f" {sku}", f"{sku} ", sku.replace("SKU-", "")))


def _pos_receipt(ctx: Ctx, receipt: dict, products: list[dict]) -> list[dict]:
    lines = []
    for line_no in range(1, ctx.rng.randrange(1, 5) + 1):
        product = ctx.pick(products)
        qty = ctx.rng.randrange(1, 4)
        price = product["list_price"] or product["unit_cost"]
        lines.append(
            {
                **receipt,
                "line_no": line_no,
                "sku": "SKU-999999" if ctx.chance(0.2) else messy_sku(ctx, product["sku"]),
                "qty": -qty if ctx.chance(0.6) else qty,
                "unit_price": messy_money(ctx, price * 1000 if ctx.chance(0.1) else price),
                "discount_pct": ctx.pick((0, 0, 0, 5, 10, 15)),
            }
        )
    return lines


def _pos_day(ctx: Ctx, store: str, day_index: int, master: Master) -> list[dict]:
    day = START + timedelta(days=day_index)
    cashiers = [e["employee_id"] for e in master.employees if e["store_code"] == store] or ["E00000"]
    rows = []
    for seq in range(1, ctx.rng.randrange(8, 22) + 1):
        sold = day.replace(hour=ctx.rng.randrange(8, 22), minute=ctx.rng.randrange(60))
        member = ctx.pick(master.customers) if ctx.rng.random() < 0.35 else None
        receipt = {
            "receipt_no": f"{store}-{day:%Y%m%d}-{seq:04d}",
            "store_code": messy_case(ctx, store),
            "cashier_id": ctx.pick(cashiers),
            "sold_at": messy_datetime(ctx, sold, "%d/%m/%Y %H:%M:%S"),
            "payment_method": messy_variant(ctx, ctx.pick(list(PAYMENT_METHODS)), PAYMENT_METHODS),
            "member_phone": member["phone"] if member else "",
        }
        rows += _pos_receipt(ctx, receipt, master.products)
    return rows


def build_pos_sales(ctx: Ctx, master: Master) -> list[dict]:
    """Dòng hàng bán tại quầy của mọi cửa hàng trong 30 ngày (khóa: line_id)."""
    stores = active_store_codes(master)
    days = range(max(1, int(30 * min(ctx.scale, 1.0))))
    rows = [line for store in stores for day in days for line in _pos_day(ctx, store, day, master)]
    rows += _pos_day(ctx, "TEST", 0, master) if ctx.dirty else []
    if ctx.dirty:  # một cửa hàng xuất trùng nguyên một ngày (lỗi đồng bộ cuối ngày)
        prefix = f"{ctx.pick(stores)}-{START + timedelta(days=ctx.rng.randrange(len(days))):%Y%m%d}"
        rows += [dict(r) for r in rows if r["receipt_no"].startswith(prefix)]
    return [{"line_id": index, **row} for index, row in enumerate(rows, start=1)]


def _item(ctx: Ctx, order: OnlineOrder, line_no: int, product: dict) -> dict:
    key = "orderId" if ctx.chance(0.4) else "order_id"
    order_id = int(order.ref.removeprefix("WEB-"))
    return {key: order_id, "line_no": line_no, "sku": product["sku"], "qty": ctx.rng.randrange(1, 3)}


def build_web_order_items(ctx: Ctx, orders: list[OnlineOrder], master: Master) -> list[dict]:
    """Chi tiết đơn website: giá các dòng cộng lại bằng tiền của đơn (trừ vài đơn lệch do phí/khuyến mãi)."""
    rows = []
    for order in (o for o in orders if o.channel == "website"):
        items = [_item(ctx, order, n, ctx.pick(master.products)) for n in range(1, ctx.rng.randrange(1, 4) + 1)]
        remaining = order.amount
        for item in items[:-1]:
            share = remaining // (len(items) + 1) // 1000 * 1000
            item["price"], remaining = {"amount": share, "currency": "VND"}, remaining - share * item["qty"]
        last = items[-1]
        amount = max(remaining // last["qty"], 1000) + (ctx.pick((15000, -20000)) if ctx.chance() else 0)
        last["price"] = {"amount": amount, "currency": "VND"}
        rows += items
    orphan = {"order_id": 99999, "line_no": 1, "sku": "SKU-000001", "qty": 1, "price": {"amount": 1, "currency": "VND"}}
    return with_duplicates(ctx, rows, 0.5) + ([orphan] if ctx.dirty else [])


def _payment(ctx: Ctx, order: OnlineOrder, attempt: int, status: str) -> dict:
    paid = order.created + timedelta(minutes=ctx.rng.randrange(1, 90) + attempt * 3)
    provider = ctx.pick(("MOMO", "VNPAY", "ZALOPAY", "COD"))
    return {
        "txn_id": f"PAY-{order.ref}-{attempt}",
        "order_ref": order.ref,
        "provider": messy_case(ctx, provider),
        "amount": float(order.amount + (ctx.pick((1000, -5000)) if ctx.chance(0.5) else 0)),
        "currency": "VND",
        "status": status,
        "paid_at_utc": (paid - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S"),
        "fee_vnd": round(order.amount * 0.011),
    }


def build_payments(ctx: Ctx, orders: list[OnlineOrder]) -> list[dict]:
    """Giao dịch cổng thanh toán cho đơn website + Tiki; giờ lưu theo UTC (lệch 7 tiếng so với giờ đơn)."""
    rows = []
    for order in (o for o in orders if o.channel in ("website", "tiki") and o.amount):
        if ctx.chance(3):
            rows.append(_payment(ctx, order, 0, "FAILED"))
        rows.append(_payment(ctx, order, 1, "SUCCESS" if order.ok else ctx.pick(("REFUNDED", "CANCELLED"))))
    return rows


def _rma(ctx: Ctx, index: int, ref: str, product: dict) -> dict:
    requested = START + timedelta(days=ctx.rng.randrange(30), hours=ctx.rng.randrange(8, 20))
    return {
        "rma_id": f"RMA{index:05d}",
        "source_ref": ref,
        "sku": messy_sku(ctx, product["sku"]),
        "qty": 1,
        "reason": ctx.pick(RETURN_REASONS),
        "refund_amount": messy_money(ctx, product["list_price"] or product["unit_cost"]),
        "requested_at": messy_datetime(ctx, requested, "%Y-%m-%d %H:%M:%S"),
        "status": messy_case(ctx, ctx.pick(("approved", "approved", "rejected", "pending"))),
    }


def build_returns(ctx: Ctx, orders: list[OnlineOrder], pos: list[dict], master: Master) -> list[dict]:
    """Yêu cầu đổi trả: tham chiếu mã đơn online hoặc số hóa đơn POS (cùng một cột, hai kiểu mã)."""
    refs = [o.ref for o in orders if not o.ok] + [r["receipt_no"] for r in pos if str(r["qty"]).startswith("-")]
    refs += ["SP99999"] if ctx.dirty else []
    rows = [_rma(ctx, index, ref, ctx.pick(master.products)) for index, ref in enumerate(refs, start=1)]
    return with_duplicates(ctx, rows, 0.5)
