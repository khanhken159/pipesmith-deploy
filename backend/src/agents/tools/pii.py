"""Che thông tin cá nhân (email, số điện thoại) trước khi đưa mẫu dữ liệu cho LLM hoặc hiển thị."""

import re

EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_RE = re.compile(r"(?<!\d)(\+?84|0)(\d{2})\d{4,6}(\d{2})(?!\d)")


def mask_text(value: str) -> str:
    """Che email thành `a***@domain` và số điện thoại thành `09******12`."""
    masked = EMAIL_RE.sub(r"\1***@\2", value)
    return PHONE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}******{m.group(3)}", masked)


def mask_value(value: object) -> object:
    """Che giá trị nếu là chuỗi; kiểu khác giữ nguyên."""
    return mask_text(value) if isinstance(value, str) else value


def mask_rows(rows: list[dict]) -> list[dict]:
    """Che mọi ô chuỗi trong danh sách dòng."""
    return [{key: mask_value(val) for key, val in row.items()} for row in rows]
