"""Vận hành: đơn mua hàng + tồn kho (ERP), vận chuyển (API đối tác), điểm thưởng (CRM), quảng cáo + tỉ giá
(marketing), phiếu hỗ trợ (CSKH).

Bẩn có chủ đích: nhận hàng trước ngày đặt, nhận thiếu/thừa, tồn kho âm, thiếu một tuần chụp tồn của một cửa hàng,
thời điểm dạng epoch mili-giây, giao xong trước khi tạo vận đơn, một đơn hai vận đơn, click > lượt hiển thị, kéo số
liệu quảng cáo hai lần, chi phí lẫn USD/VND, tỉ giá chỉ có ngày làm việc (cuối tuần phải lấy ngày gần nhất), số
điện thoại khách nằm trong nội dung phiếu hỗ trợ (PII trong văn bản tự do).
"""

from datetime import datetime, timedelta, timezone

from src.services.company.common import (
    LOCAL_TZ,
    START,
    Ctx,
    messy_case,
    messy_datetime,
    messy_variant,
    moment,
    phone_number,
    with_duplicates,
)
from src.services.company.master import Master, active_store_codes
from src.services.company.online import OnlineOrder
from src.services.company.vocab import AD_CHANNELS, CARRIERS, TICKET_CATEGORIES

VN_TZ = timezone(timedelta(hours=7))


def _purchase(ctx: Ctx, index: int, master: Master) -> dict:
    product = ctx.pick(master.products)
    ordered = moment(ctx, 45, START - timedelta(days=15))
    qty = ctx.rng.randrange(10, 300)
    received = None if ctx.rng.random() < 0.2 else ordered + timedelta(days=ctx.rng.randrange(2, 14))
    if received and ctx.chance():
        received = ordered - timedelta(days=2)
    return {
        "po_id": f"PO{index:06d}",
        "supplier_id": product["supplier_id"],
        "warehouse_code": ctx.pick(active_store_codes(master, "warehouse")),
        "sku": product["sku"],
        "qty_ordered": qty,
        "qty_received": None if received is None else qty + (ctx.pick((-5, -20, 10)) if ctx.chance(3) else 0),
        "unit_cost": product["unit_cost"],
        "ordered_at": ordered.strftime("%Y-%m-%d %H:%M:%S"),
        "received_at": received.strftime("%Y-%m-%d %H:%M:%S") if received else None,
        "status": messy_case(ctx, "open" if received is None else "received"),
    }


def build_purchase_orders(ctx: Ctx, master: Master) -> list[dict]:
    """Đơn mua hàng nhập kho tổng (khóa: po_id)."""
    return [_purchase(ctx, index, master) for index in range(1, ctx.n(1500) + 1)]


def build_inventory(ctx: Ctx, master: Master) -> list[dict]:
    """Tồn kho chụp mỗi thứ Hai tại mọi điểm cho một nhóm mã hàng; bẩn: tồn âm, thiếu một tuần của một cửa hàng."""
    skus = [p["sku"] for p in ctx.rng.sample(master.products, min(len(master.products), ctx.n(150)))]
    locations = [s["store_code"] for s in master.stores]
    skipped = (ctx.pick(locations), 2) if ctx.dirty else ("", -1)
    rows = []
    for week in range(4):
        snapshot = (START + timedelta(days=6 + 7 * week)).date()
        for location in locations:
            if (location, week) == skipped:
                continue
            for sku in skus:
                on_hand = ctx.rng.randrange(0, 200) if not ctx.chance(0.3) else -ctx.rng.randrange(1, 20)
                rows.append({"snapshot_date": str(snapshot), "location_code": location, "sku": sku, "on_hand": on_hand,
                             "reserved": ctx.rng.randrange(0, 10)})  # fmt: skip
    return rows


def _events(ctx: Ctx, created: datetime, delivered: bool) -> list[dict]:
    steps = ["created", "picked_up", "in_transit"] + (["delivered"] if delivered else ["returned_to_sender"])
    at = created
    events = []
    for step in steps[: ctx.rng.randrange(2, len(steps) + 1)] if ctx.chance(2) else steps:
        at = at + timedelta(hours=ctx.rng.randrange(2, 30))
        events.append({"status": step, "at": at.strftime("%Y-%m-%dT%H:%M:%S") + LOCAL_TZ})
    return events


def _shipment(ctx: Ctx, index: int, order: OnlineOrder) -> dict:
    created = order.created + timedelta(hours=ctx.rng.randrange(1, 20))
    events = _events(ctx, created, order.ok)
    carrier = ctx.pick(list(CARRIERS))
    return {
        "shipment_id": f"{carrier}{index:07d}",
        "order_ref": str(int(order.ref[4:])) if order.channel == "website" and ctx.chance(3) else order.ref,
        "carrier": messy_variant(ctx, carrier, CARRIERS),
        "created_at_ms": int(created.replace(tzinfo=VN_TZ).timestamp() * 1000),
        "events": events,
        "final_status": events[-1]["status"],
        "shipping_fee": ctx.pick((15000, 22000, 30000, 45000)),
        "cod_amount": order.amount if ctx.rng.random() < 0.4 else 0,
        "weight_gram": ctx.rng.randrange(100, 8000),
    }


def build_shipments(ctx: Ctx, orders: list[OnlineOrder]) -> list[dict]:
    """Vận đơn của đối tác giao hàng cho mọi đơn online chưa hủy; một số đơn có 2 vận đơn (giao lại)."""
    shipped = [o for o in orders if o.ok or ctx.rng.random() < 0.5]
    rows = [_shipment(ctx, index, order) for index, order in enumerate(shipped, start=1)]
    reshipped = ctx.rng.sample(shipped, int(len(shipped) * ctx.dirty))
    rows += [_shipment(ctx, len(rows) + n + 1, order) for n, order in enumerate(reshipped)]
    return rows


def build_loyalty(ctx: Ctx, master: Master) -> list[dict]:
    """Sổ điểm thưởng (cộng khi mua, trừ khi đổi quà/hết hạn); bẩn: mã khách không tồn tại, giao dịch ghi trùng."""
    rows = []
    for index in range(1, ctx.n(8000) + 1):
        reason = ctx.pick(("purchase", "purchase", "purchase", "redeem", "expire", "adjust"))
        points = ctx.rng.randrange(10, 500) * (1 if reason in ("purchase", "adjust") else -1)
        customer = "C999999" if ctx.chance(0.3) else ctx.pick(master.customers)["customer_id"]
        when = moment(ctx)
        rows.append({"ledger_id": index, "customer_id": customer, "points": points, "reason": reason,
                     "txn_time": messy_datetime(ctx, when, "%Y-%m-%d %H:%M:%S")})  # fmt: skip
    return with_duplicates(ctx, rows, 0.5)


def _ad_row(ctx: Ctx, day: datetime, campaign: tuple[str, str, str]) -> dict:
    campaign_id, channel, currency = campaign
    impressions = ctx.rng.randrange(2_000, 120_000)
    clicks = int(impressions * ctx.rng.uniform(0.005, 0.04))
    spend = round(ctx.rng.uniform(20, 400), 2) if currency == "USD" else ctx.rng.randrange(500, 9000) * 1000
    return {
        "date": messy_datetime(ctx, day, "%Y-%m-%d"),
        "channel": messy_variant(ctx, channel, AD_CHANNELS),
        "campaign_id": campaign_id,
        "campaign_name": f"{channel.upper()}_{campaign_id}_Sale9",
        "currency": currency,
        "spend": spend,
        "impressions": impressions,
        "clicks": impressions + 50 if ctx.chance(0.3) else clicks,
        "conversions": ctx.rng.randrange(0, max(clicks // 20, 1) + 1),
    }


def build_ad_spend(ctx: Ctx) -> list[dict]:
    """Chi phí quảng cáo theo ngày × chiến dịch; Google tính USD, kênh khác VND; bẩn: thiếu ngày, kéo trùng."""
    campaigns = [(f"CMP{n:03d}", ctx.pick(list(AD_CHANNELS)), "") for n in range(1, ctx.n(30) + 1)]
    campaigns = [(cid, ch, "USD" if ch == "google" else "VND") for cid, ch, _ in campaigns]
    missing_day = ctx.rng.randrange(30) if ctx.dirty else -1
    rows = [
        _ad_row(ctx, START + timedelta(days=day), campaign)
        for day in range(30)
        if day != missing_day
        for campaign in campaigns
    ]
    return with_duplicates(ctx, rows)


def build_fx_rates(ctx: Ctx) -> list[dict]:
    """Tỉ giá USD→VND chỉ có ngày làm việc (thứ Bảy, Chủ nhật không có dòng)."""
    rows, rate = [], 25_350.0
    for day in range(30):
        current = START + timedelta(days=day)
        rate += ctx.rng.uniform(-40, 40)
        if current.weekday() < 5:
            rows.append({"rate_date": current.strftime("%Y-%m-%d"), "currency": "USD", "rate_to_vnd": round(rate, 1)})
    return rows


def _ticket(ctx: Ctx, index: int, orders: list[OnlineOrder]) -> dict:
    order = ctx.pick(orders) if ctx.rng.random() < 0.7 else None
    created = moment(ctx)
    category = ctx.pick(TICKET_CATEGORIES)
    contact = f" Gọi lại giúp em số {phone_number(ctx)} nhé." if ctx.chance(3) else ""
    ticket = {
        "ticket_id": f"TCK{index:06d}",
        "created_at": messy_datetime(ctx, created, "%Y-%m-%dT%H:%M:%S" + LOCAL_TZ),
        "channel": ctx.pick(("zalo", "hotline", "email", "fanpage")),
        "customer_email": messy_case(ctx, order.email) if order else None,
        "order_ref": order.ref if order else None,
        "category": category,
        "body": f"Khách phản ánh {category} với đơn {order.ref if order else '(không rõ)'}.{contact}",
        "csat": ctx.pick((1, 2, 3, 4, 5, None)),
    }
    if ctx.rng.random() < 0.8:
        ticket["resolved_at"] = (created + timedelta(hours=ctx.rng.randrange(1, 96))).strftime("%Y-%m-%dT%H:%M:%S")
    if ctx.chance(2):
        ticket["tags"] = ["vip"] if ctx.rng.random() < 0.5 else ["khiếu nại", "ưu tiên"]
    return ticket


def build_tickets(ctx: Ctx, orders: list[OnlineOrder]) -> list[dict]:
    """Phiếu hỗ trợ khách hàng (JSON từng dòng; có trường chỉ xuất hiện ở một số dòng)."""
    return [_ticket(ctx, index, orders) for index in range(1, ctx.n(1500) + 1)]
