"""Sinh dữ liệu nguồn giả lập.

- `basic`: 3 nguồn đơn online (CSV kiểu Shopee, JSON kiểu API Tiki, SQLite của website) — nhỏ, dùng cho test/demo.
- `company`: `basic` + kho raw của cả công ty bán lẻ "P113 Retail" (CRM, ERP, POS, kho vận, thanh toán, marketing,
  nhân sự, CSKH — xem `src/services/company/`).

Seed cố định để kết quả lặp lại được; `dirty` điều chỉnh mức "bẩn" (trùng, rỗng, ngày lẫn định dạng, đơn hoàn...).
"""

import csv
import json
import random
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from src.services.company import generate_company_sources

START_DAY = date(2026, 9, 1)
DAYS = 30


class SeedConfig(BaseModel):
    """Tham số sinh dữ liệu."""

    out_dir: Path
    seed: int = 42
    dirty: float = Field(default=0.05, ge=0.0, le=0.5)
    rows_per_source: int = Field(default=300, ge=10)
    profile: Literal["basic", "company"] = "basic"
    scale: float = Field(default=1.0, gt=0, le=10, description="Hệ số quy mô cho bộ company")


def _vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")


def _when(rng: random.Random) -> datetime:
    day = START_DAY + timedelta(days=rng.randrange(DAYS))
    return datetime(day.year, day.month, day.day, rng.randrange(8, 23), rng.randrange(60))


def _contact(rng: random.Random, n: int) -> tuple[str, str]:
    return f"khach{n}@example.com", f"09{rng.randrange(10**7, 10**8)}"


def _status(rng: random.Random, labels: tuple[str, str, str], dirty: float) -> str:
    roll = rng.random()
    return labels[2] if roll < 0.05 + dirty else labels[1] if roll < 0.2 + dirty else labels[0]


def _shopee_rows(cfg: SeedConfig, rng: random.Random) -> list[dict]:
    rows = []
    for n in range(1, cfg.rows_per_source + 1):
        when, (email, phone) = _when(rng), _contact(rng, n)
        mixed = rng.random() < cfg.dirty
        rows.append(
            {
                "order_id": f"SP{n:05d}",
                "order_date": when.strftime("%Y-%m-%d" if mixed else "%d/%m/%Y"),
                "customer_email": email,
                "customer_phone": phone,
                "status": _status(rng, ("COMPLETED", "CANCELLED", "RETURNED"), cfg.dirty),
                "total_amount": "" if rng.random() < cfg.dirty / 2 else _vnd(rng.randrange(50, 3000) * 1000),
            }
        )
    duplicates = [dict(r) for r in rng.sample(rows, int(len(rows) * cfg.dirty))]
    return rows + duplicates


def _tiki_rows(cfg: SeedConfig, rng: random.Random) -> list[dict]:
    rows = []
    for n in range(1, cfg.rows_per_source + 1):
        amount = None if rng.random() < cfg.dirty / 2 else float(rng.randrange(50, 3000) * 1000)
        rows.append(
            {
                "id": f"TK{n:05d}",
                "created_at": _when(rng).isoformat(),
                "state": _status(rng, ("delivered", "canceled", "refunded"), cfg.dirty),
                "grand_total": amount,
                "buyer_email": _contact(rng, n)[0],
            }
        )
    return rows


def _website_rows(cfg: SeedConfig, rng: random.Random) -> list[tuple]:
    rows = []
    for n in range(1, cfg.rows_per_source + 1):
        email, phone = _contact(rng, n)
        status = _status(rng, ("paid", "cancelled", "refunded"), cfg.dirty)
        rows.append((n, _when(rng).strftime("%Y-%m-%d %H:%M:%S"), status, rng.randrange(50, 3000) * 1000, email, phone))
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_sqlite(path: Path, rows: list[tuple]) -> None:
    path.unlink(missing_ok=True)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "CREATE TABLE orders (order_id INTEGER, created_ts TEXT, status TEXT, amount_vnd INTEGER, "
            "email TEXT, phone TEXT)"
        )
        conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", rows)


def generate_sources(cfg: SeedConfig) -> dict[str, int]:
    """Ghi các nguồn vào `cfg.out_dir`; trả về số dòng mỗi file (bộ company: -1 = file nhiều bảng/không đếm)."""
    rng = random.Random(cfg.seed)
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    shopee, tiki, website = _shopee_rows(cfg, rng), _tiki_rows(cfg, rng), _website_rows(cfg, rng)
    _write_csv(cfg.out_dir / "shopee_orders.csv", shopee)
    (cfg.out_dir / "tiki_orders.json").write_text(json.dumps(tiki, ensure_ascii=False, indent=1), encoding="utf-8")
    _write_sqlite(cfg.out_dir / "website.sqlite", website)
    counts = {"shopee_orders.csv": len(shopee), "tiki_orders.json": len(tiki), "website.sqlite": len(website)}
    if cfg.profile == "company":
        files = generate_company_sources(cfg.out_dir, cfg.seed, (cfg.dirty, cfg.scale))
        counts.update({name: -1 for name in files})
    return counts


def ensure_demo_sources(out_dir: Path, seed: int) -> bool:
    """Thư mục nguồn trống (máy chủ mới, Docker volume mới, Render) → sinh dữ liệu mẫu. Trả về True nếu vừa sinh."""
    if out_dir.exists() and any(out_dir.iterdir()):
        return False
    generate_sources(SeedConfig(out_dir=out_dir, seed=seed, profile="company"))
    return True
