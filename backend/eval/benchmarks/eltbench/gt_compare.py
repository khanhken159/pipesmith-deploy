"""So kết quả của pipeline với bảng kết quả đúng (CSV xuất từ Snowflake) — code tất định, không dùng LLM.

Bảng đúng có tên cột viết HOA, số làm tròn 6 chữ số, số nguyên dạng "1.0". Vì vậy: so tên cột không phân biệt
hoa/thường và không phụ thuộc thứ tự cột; so số với sai số; so tập dòng hai chiều, không phụ thuộc thứ tự dòng.
"""

import math
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

REL_TOL = 1e-5
ABS_TOL = 1e-6
BOOLEANS = {"true": 1.0, "false": 0.0}


def normalize(value: object) -> object:
    """Đưa một ô về dạng so được: None, số thực, hoặc chuỗi."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float | Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    text = str(value).strip()
    if text.lower() in BOOLEANS:
        return BOOLEANS[text.lower()]
    try:
        return float(text)
    except ValueError:
        return text.removesuffix(".000")


def _sort_key(row: tuple) -> tuple:
    return tuple((0, "") if v is None else (1, f"{v:.3f}") if isinstance(v, float) else (2, v) for v in row)


def _same_cell(a: object, b: object) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL) or (math.isnan(a) and math.isnan(b))
    return a == b


def load_ground_truth(csv_path: Path) -> tuple[list[str], list[tuple]]:
    """Đọc bảng đúng (mọi cột dạng chuỗi), tên cột chữ thường."""
    with duckdb.connect() as con:
        rel = con.sql(f"SELECT * FROM read_csv('{csv_path.as_posix()}', header = true, all_varchar = true)")
        return [c.lower() for c in rel.columns], rel.fetchall()


def compare_to_ground_truth(columns: list[str], rows: list[tuple], csv_path: Path) -> tuple[bool, str]:
    """So (cột, dòng) của pipeline với bảng đúng; trả (khớp?, mô tả)."""
    gt_columns, gt_rows = load_ground_truth(csv_path)
    lowered = [c.lower() for c in columns]
    if sorted(lowered) != sorted(gt_columns):
        missing, extra = sorted(set(gt_columns) - set(lowered)), sorted(set(lowered) - set(gt_columns))
        return False, f"Khác cột — thiếu {missing}, thừa {extra}"
    if len(rows) != len(gt_rows):
        return False, f"Khác số dòng: {len(rows)} ≠ {len(gt_rows)} (đúng)"
    order = [lowered.index(c) for c in gt_columns]
    ours = sorted((tuple(normalize(r[i]) for i in order) for r in rows), key=_sort_key)
    truth = sorted((tuple(normalize(v) for v in r) for r in gt_rows), key=_sort_key)
    wrong = sum(1 for a, b in zip(ours, truth, strict=True) if not all(map(_same_cell, a, b)))
    return (wrong == 0, f"Khớp {len(rows)} dòng" if wrong == 0 else f"{wrong}/{len(rows)} dòng khác bảng đúng")
