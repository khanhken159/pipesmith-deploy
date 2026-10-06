"""Dữ liệu gốc (master data): cửa hàng/kho, nhà cung cấp, sản phẩm (ERP), khách hàng (CRM), nhân viên (HR).

Bẩn có chủ đích: khách hàng trùng email khác mã, nhà cung cấp trùng mã số thuế khác tên, giá bán < giá vốn,
danh mục rỗng, khóa ngoại mồ côi, ngày sinh "giữ chỗ" 1900-01-01, ngày nghỉ việc trước ngày vào làm.
"""

from datetime import date, timedelta

from pydantic import BaseModel

from src.services.company.common import Ctx, messy_case, messy_phone, messy_variant, no_accents, past_day
from src.services.company.common import phone_number as new_phone
from src.services.company.vocab import (
    CATEGORIES,
    CITIES,
    CITY_VARIANTS,
    FIRST_NAMES,
    LAST_NAMES,
    MIDDLE_NAMES,
    POSITIONS,
    TIERS,
    UOM_VARIANTS,
)


class Master(BaseModel):
    """Dữ liệu gốc dùng chung cho các bảng giao dịch (khóa sạch, chưa làm bẩn)."""

    stores: list[dict]
    suppliers: list[dict]
    products: list[dict]
    customers: list[dict]
    employees: list[dict]


def person_name(ctx: Ctx) -> str:
    """Họ tên tiếng Việt; bẩn thì không dấu hoặc viết hoa toàn bộ."""
    name = f"{ctx.pick(LAST_NAMES)} {ctx.pick(MIDDLE_NAMES)} {ctx.pick(FIRST_NAMES)}"
    if ctx.chance():
        return ctx.pick((no_accents(name), name.upper()))
    return name


def build_stores(ctx: Ctx) -> list[dict]:
    """20 cửa hàng + 5 kho; một cửa hàng đã đóng cửa."""
    cities = list(CITIES)
    rows = []
    for index in range(1, 26):
        is_store = index <= 20
        city = cities[index % len(cities)]
        rows.append(
            {
                "store_code": f"ST{index:03d}" if is_store else f"WH{index - 20:02d}",
                "store_name": f"P113 {city} {index}" if is_store else f"Kho tổng {city}",
                "store_type": "store" if is_store else "warehouse",
                "region": messy_case(ctx, CITIES[city]),
                "city": messy_variant(ctx, city, CITY_VARIANTS),
                "opened_on": str(past_day(ctx, 8)),
                "closed_on": "2026-08-31" if index == 7 else None,
            }
        )
    return rows


def build_suppliers(ctx: Ctx) -> list[dict]:
    """Nhà cung cấp; bẩn: cùng mã số thuế xuất hiện 2 lần với tên viết khác (trùng dữ liệu gốc)."""
    rows = [
        {
            "supplier_id": f"S{index:03d}",
            "supplier_name": f"Công ty TNHH {ctx.pick(LAST_NAMES)} {ctx.pick(('Phát', 'Thịnh', 'Lộc', 'Hưng', 'An'))}",
            "tax_code": f"0{ctx.rng.randrange(10**8, 10**9)}",
            "payment_terms_days": ctx.pick((0, 15, 30, 45, 60)),
            "country": "VN" if ctx.rng.random() < 0.85 else ctx.pick(("CN", "KR", "TH")),
        }
        for index in range(1, ctx.n(40) + 1)
    ]
    for original in ctx.rng.sample(rows, max(1, int(len(rows) * ctx.dirty))):
        copy = {
            **original,
            "supplier_id": f"S{len(rows) + 1:03d}",
            "supplier_name": no_accents(original["supplier_name"]),
        }
        rows.append(copy)
    return rows


def _product(ctx: Ctx, index: int, supplier_ids: list[str]) -> dict:
    category = ctx.pick(list(CATEGORIES))
    brands, (low, high) = CATEGORIES[category]
    price = ctx.rng.randrange(low // 1000, high // 1000) * 1000
    cost = int(price * ctx.rng.uniform(0.55, 0.85)) // 100 * 100
    uom = "cái" if category in ("Điện thoại", "Laptop", "Phụ kiện", "Điện gia dụng") else ctx.pick(("hộp", "chai"))
    return {
        "product_id": index,
        "sku": f"SKU-{index:06d}",
        "product_name": f"{ctx.pick(brands)} {category} {ctx.pick(('Mini', 'Pro', 'Plus', 'Lite', 'X'))}{index % 97}",
        "category": None if ctx.chance(0.5) else messy_case(ctx, category),
        "uom": messy_variant(ctx, uom, UOM_VARIANTS),
        "unit_cost": cost,
        "list_price": ctx.pick((0, cost - 1000)) if ctx.chance(0.3) else price,
        "is_active": ctx.pick((1, 1, 1, 0)),
        "supplier_id": "S999" if ctx.chance(0.3) else ctx.pick(supplier_ids),
        "created_at": f"{past_day(ctx, 3)} 09:00:00",
    }


def build_products(ctx: Ctx, suppliers: list[dict]) -> list[dict]:
    """Danh mục sản phẩm ERP (khóa: product_id; mã hàng: sku)."""
    supplier_ids = [s["supplier_id"] for s in suppliers]
    return [_product(ctx, index, supplier_ids) for index in range(1, ctx.n(600) + 1)]


def _customer(ctx: Ctx, index: int) -> dict:
    created = past_day(ctx, 3)
    birth = date(1900, 1, 1) if ctx.chance(0.5) else created - timedelta(days=365 * ctx.rng.randrange(18, 65))
    return {
        "customer_id": f"C{index:06d}",
        "full_name": person_name(ctx),
        "email": messy_case(ctx, f"khach{index}@example.com"),
        "phone": messy_phone(ctx, new_phone(ctx)),
        "gender": ctx.pick(("M", "F", "Nam", "Nữ", None)) if ctx.chance(2) else ctx.pick(("M", "F")),
        "birth_date": str(birth),
        "city": messy_variant(ctx, ctx.pick(list(CITIES)), CITY_VARIANTS),
        "tier": messy_case(ctx, ctx.pick(TIERS)),
        "marketing_consent": ctx.pick((0, 1)),
        "created_at": f"{created} {ctx.rng.randrange(8, 22):02d}:{ctx.rng.randrange(60):02d}:00",
    }


def build_customers(ctx: Ctx) -> list[dict]:
    """Khách hàng CRM; email khachN@example.com khớp với email trong đơn online.

    Bẩn: cùng email đăng ký 2 lần (mã khác), tài khoản test nội bộ.
    """
    rows = [_customer(ctx, index) for index in range(1, ctx.n(4000) + 1)]
    for original in ctx.rng.sample(rows, int(len(rows) * ctx.dirty * 0.5)):
        rows.append({**original, "customer_id": f"C{len(rows) + 1:06d}", "phone": new_phone(ctx), "tier": "Bronze"})
    for index in range(int(10 * ctx.dirty * 10)):
        rows.append({**_customer(ctx, 900000 + index), "full_name": "Test User", "email": f"test{index}@p113retail.vn"})
    return rows


def _employee(ctx: Ctx, index: int, store_codes: list[str]) -> dict:
    hired = past_day(ctx, 6)
    left = None
    if ctx.rng.random() < 0.12:
        left = (
            str(hired - timedelta(days=30)) if ctx.chance() else str(hired + timedelta(days=ctx.rng.randrange(60, 900)))
        )
    return {
        "employee_id": f"E{index:05d}",
        "full_name": person_name(ctx),
        "national_id": f"0{ctx.rng.randrange(10**10, 10**11)}",
        "phone": new_phone(ctx),
        "work_email": f"nv{index}@p113retail.vn",
        "store_code": ctx.pick(store_codes),
        "position": ctx.pick(POSITIONS),
        "hire_date": str(hired),
        "termination_date": left,
        "salary_vnd": None if ctx.chance() else ctx.rng.randrange(60, 350) * 100_000,
    }


def build_employees(ctx: Ctx, stores: list[dict]) -> list[dict]:
    """Nhân viên (HR) — có PII nhạy cảm: số CCCD, lương."""
    codes = [s["store_code"] for s in stores]
    return [_employee(ctx, index, codes) for index in range(1, ctx.n(600) + 1)]


def build_master(ctx: Ctx) -> Master:
    """Sinh toàn bộ dữ liệu gốc theo thứ tự phụ thuộc."""
    stores = build_stores(ctx)
    suppliers = build_suppliers(ctx)
    return Master(
        stores=stores,
        suppliers=suppliers,
        products=build_products(ctx, suppliers),
        customers=build_customers(ctx),
        employees=build_employees(ctx, stores),
    )


def active_store_codes(master: Master, kind: str = "store") -> list[str]:
    """Mã cửa hàng (hoặc kho) — mã sạch để sinh giao dịch."""
    return [s["store_code"] for s in master.stores if s["store_type"] == kind]
