"""Sổ lỗi (SQLite): ghi lỗi V-node, tìm mục giống đã được Reviewer duyệt để gợi ý cho Codegen.

Mục mới mặc định `approved=False`; chỉ mục đã duyệt mới được đưa vào prompt (tối đa 3), và chỉ là gợi ý.
"""

import hashlib
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from src.config import get_settings
from src.models.evidence import ErrorEntry

MAX_HINTS = 3
_SCHEMA = """
CREATE TABLE IF NOT EXISTS error_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    signature TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    cause TEXT NOT NULL DEFAULT '',
    fix TEXT NOT NULL DEFAULT '',
    sql_before TEXT NOT NULL DEFAULT '',
    sql_after TEXT NOT NULL DEFAULT '',
    occurrences INTEGER NOT NULL DEFAULT 1,
    approved INTEGER NOT NULL DEFAULT 0
);
"""
_CODES = (
    ("SAFETY_BLOCKED", re.compile(r"bị chặn|không có trong danh mục|không hợp lệ", re.I)),
    ("BINDER_ERROR", re.compile(r"binder error|could not be resolved|not found", re.I)),
    ("PARSER_ERROR", re.compile(r"parser error|syntax|cú pháp", re.I)),
    ("CONVERSION_ERROR", re.compile(r"conversion error|could not convert", re.I)),
    ("TEST_FAILURE", re.compile(r"\bfail\b|got \d+ results", re.I)),
    ("TIMEOUT", re.compile(r"timeout|thời gian", re.I)),
)


def classify_error(message: str) -> str:
    """Mã lỗi ngắn theo nội dung thông báo."""
    return next((code for code, pattern in _CODES if pattern.search(message)), "UNKNOWN")


def error_signature(message: str) -> str:
    """Chữ ký lỗi: bỏ số, đường dẫn, chuỗi trong nháy rồi băm — cùng loại lỗi cho cùng chữ ký."""
    text = message.lower()
    text = re.sub(r"[a-z]:[\\/][^\s'\"]+|/[^\s'\"]+", "<path>", text)
    text = re.sub(r"'[^']*'|\"[^\"]*\"", "<str>", text)
    text = re.sub(r"\d+", "<n>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


class ErrorMemory:
    """Truy cập bảng `error_entries`."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def record(self, entry: ErrorEntry) -> ErrorEntry:
        """Thêm lỗi mới hoặc tăng số lần gặp nếu chữ ký đã có."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO error_entries (code, signature, description, sql_before) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(signature) DO UPDATE SET occurrences = occurrences + 1",
                (entry.code, entry.signature, entry.description[:2000], entry.sql_before[:4000]),
            )
            row = conn.execute("SELECT * FROM error_entries WHERE signature=?", (entry.signature,)).fetchone()
        return _to_entry(row)

    def approved_hints(self, signature: str, code: str) -> list[ErrorEntry]:
        """Tối đa 3 mục ĐÃ DUYỆT: cùng chữ ký trước, rồi cùng mã lỗi."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM error_entries WHERE approved=1 AND (signature=? OR code=?) "
                "ORDER BY signature=? DESC, occurrences DESC LIMIT ?",
                (signature, code, signature, MAX_HINTS),
            ).fetchall()
        return [_to_entry(r) for r in rows]

    def pending(self) -> list[ErrorEntry]:
        """Các mục chờ Reviewer duyệt."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM error_entries WHERE approved=0 ORDER BY occurrences DESC").fetchall()
        return [_to_entry(r) for r in rows]

    def approve(self, entry_id: int, fix: str) -> bool:
        """Reviewer duyệt một mục (kèm cách sửa). Trả False nếu không có mục đó."""
        with self._connect() as conn:
            cur = conn.execute("UPDATE error_entries SET approved=1, fix=? WHERE id=?", (fix, entry_id))
        return cur.rowcount > 0

    def discard(self, entry_id: int) -> bool:
        """Bỏ một mục không hữu ích."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM error_entries WHERE id=?", (entry_id,))
        return cur.rowcount > 0


def _to_entry(row: sqlite3.Row) -> ErrorEntry:
    data = dict(row)
    data["approved"] = bool(data["approved"])
    return ErrorEntry(**data)


def get_error_memory() -> ErrorMemory:
    """Sổ lỗi dùng chung file SQLite với store."""
    return ErrorMemory(get_settings().store_path)
