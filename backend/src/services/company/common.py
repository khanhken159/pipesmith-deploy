"""Tiện ích sinh dữ liệu công ty giả lập: ngữ cảnh ngẫu nhiên (seed cố định), các kiểu "làm bẩn", ghi file.

Mọi kiểu bẩn đều có xác suất tỉ lệ với `dirty` để chỉnh được mức bẩn (0 = sạch hoàn toàn).
"""

import csv
import json
import random
import sqlite3
import unicodedata
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb

START = datetime(2026, 9, 1)
DAYS = 30
LOCAL_TZ = "+07:00"


@dataclass
class Ctx:
    """Ngữ cảnh sinh dữ liệu: bộ sinh ngẫu nhiên, mức bẩn, hệ số quy mô, thư mục ghi."""

    rng: random.Random
    dirty: float
    scale: float
    out_dir: Path

    def n(self, base: int) -> int:
        """Số bản ghi theo quy mô (tối thiểu 10)."""
        return max(10, int(base * self.scale))

    def chance(self, weight: float = 1.0) -> bool:
        """Có làm bẩn bản ghi này không (xác suất = dirty × weight)."""
        return self.rng.random() < self.dirty * weight

    def pick(self, items: list | tuple):
        """Chọn ngẫu nhiên một phần tử."""
        return items[self.rng.randrange(len(items))]


def moment(ctx: Ctx, days: int = DAYS, start: datetime = START) -> datetime:
    """Thời điểm ngẫu nhiên trong giờ làm việc (8h–22h) của khoảng `days` ngày từ `start`."""
    day = start + timedelta(days=ctx.rng.randrange(days))
    return day.replace(hour=ctx.rng.randrange(8, 22), minute=ctx.rng.randrange(60), second=ctx.rng.randrange(60))


def past_day(ctx: Ctx, years: int) -> date:
    """Một ngày trong `years` năm trước START."""
    return (START - timedelta(days=ctx.rng.randrange(1, 365 * years))).date()


def messy_datetime(ctx: Ctx, value: datetime, usual: str) -> str:
    """Thường theo `usual`; bẩn thì đổi sang định dạng khác (ISO, dd/mm, mm/dd kiểu Mỹ, có múi giờ)."""
    if not ctx.chance():
        return value.strftime(usual)
    styles = ("%Y-%m-%dT%H:%M:%S" + LOCAL_TZ, "%d/%m/%Y %H:%M", "%m/%d/%Y %I:%M %p", "%Y-%m-%d %H:%M:%S", "%Y%m%d")
    return value.strftime(ctx.pick(styles))


def messy_case(ctx: Ctx, value: str) -> str:
    """Bẩn: đổi hoa/thường hoặc thêm khoảng trắng thừa."""
    if not ctx.chance():
        return value
    return ctx.pick((value.lower(), value.upper(), f" {value}", f"{value}  ", value.title()))


def messy_variant(ctx: Ctx, value: str, variants: dict[str, list[str]]) -> str:
    """Bẩn: thay bằng một cách viết khác của cùng giá trị (ví dụ "TP. Hồ Chí Minh" → "HCM")."""
    options = variants.get(value, [])
    return ctx.pick(options) if options and ctx.chance(2) else value


def no_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt ("Nguyễn" → "Nguyen") — kiểu dữ liệu nhập từ bàn phím không dấu."""
    stripped = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D")


def vnd_text(amount: int) -> str:
    """1075000 → "1.075.000"."""
    return f"{amount:,}".replace(",", ".")


def messy_money(ctx: Ctx, amount: int) -> str:
    """Tiền dạng chuỗi: thường "1.075.000"; bẩn thì "1,075,000", "1075000.0", "1.075.000đ", "1.075k"."""
    if not ctx.chance():
        return vnd_text(amount)
    styles = (f"{amount:,}", f"{amount}.0", f"{vnd_text(amount)}đ", f"{amount // 1000}k", f"{vnd_text(amount)} VND")
    return ctx.pick(styles)


def phone_number(ctx: Ctx) -> str:
    """Số di động 10 số."""
    return f"0{ctx.pick('35789')}{ctx.rng.randrange(10**7, 10**8)}"


def messy_phone(ctx: Ctx, phone: str) -> str:
    """Bẩn: +84, có dấu cách/chấm, mất số 0 đầu."""
    if not ctx.chance(2):
        return phone
    body = phone[1:]
    return ctx.pick(
        (f"+84{body}", f"84{body}", f"{phone[:4]} {phone[4:7]} {phone[7:]}", f"{phone[:4]}.{phone[4:]}", body)
    )


def with_duplicates(ctx: Ctx, rows: list[dict], weight: float = 1.0) -> list[dict]:
    """Thêm bản sao y hệt của một phần dòng (xuất trùng, gọi API lặp)."""
    count = int(len(rows) * ctx.dirty * weight)
    return rows + [dict(r) for r in ctx.rng.sample(rows, min(count, len(rows)))]


def write_csv(path: Path, rows: list[dict]) -> None:
    """CSV UTF-8, cột theo thứ tự xuất hiện đầu tiên."""
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """JSON từng dòng (kiểu log/sự kiện API)."""
    lines = (json.dumps(row, ensure_ascii=False, default=str) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path: Path, rows: list[dict]) -> None:
    """Một mảng JSON (kiểu phản hồi API trả theo trang)."""
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def write_sqlite(path: Path, tables: dict[str, list[dict]]) -> None:
    """Một file SQLite nhiều bảng (CSDL của hệ thống nghiệp vụ); kiểu cột suy từ dòng đầu."""
    path.unlink(missing_ok=True)
    with closing(sqlite3.connect(path)) as conn, conn:
        for name, rows in tables.items():
            columns = list(rows[0])
            types = ", ".join(f'"{c}" {_sqlite_type(rows[0][c])}' for c in columns)
            conn.execute(f'CREATE TABLE "{name}" ({types})')
            marks = ", ".join("?" for _ in columns)
            conn.executemany(f'INSERT INTO "{name}" VALUES ({marks})', [tuple(r.get(c) for c in columns) for r in rows])


def _sqlite_type(value: object) -> str:
    if isinstance(value, bool | int):
        return "INTEGER"
    return "REAL" if isinstance(value, float) else "TEXT"


def write_parquet(path: Path, rows: list[dict]) -> None:
    """Parquet (kho dữ liệu của cổng thanh toán) — ghi qua DuckDB, không cần thêm thư viện."""
    staging = path.with_suffix(".tmp.jsonl")
    write_jsonl(staging, rows)
    try:
        with duckdb.connect() as con:
            source, target = staging.as_posix().replace("'", "''"), path.as_posix().replace("'", "''")
            con.execute(f"COPY (SELECT * FROM read_json_auto('{source}')) TO '{target}' (FORMAT parquet)")
    finally:
        staging.unlink(missing_ok=True)
