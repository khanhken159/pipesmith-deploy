"""Test store (lần chạy, duyệt) và sổ lỗi (chữ ký, chỉ gợi ý mục đã duyệt)."""

from pathlib import Path

import pytest

from src.models.evidence import ErrorEntry, ReviewDecision
from src.models.schemas import RunStatus
from src.services.error_memory import ErrorMemory, classify_error, error_signature
from src.services.store import Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "app.db")


@pytest.fixture
def memory(tmp_path: Path) -> ErrorMemory:
    return ErrorMemory(tmp_path / "app.db")


def test_store_create_update_list(store: Store):
    record = store.create_run("gộp đơn hàng", "alice")
    assert record.status == RunStatus.RUNNING and record.provider == "mock"
    store.update_run(record.id, RunStatus.WAITING_REVIEW, {"target": "fct_x"})
    loaded = store.get_run(record.id)
    assert loaded.status == RunStatus.WAITING_REVIEW
    assert loaded.summary == {"target": "fct_x"}
    assert [r.id for r in store.list_runs()] == [record.id]
    assert store.get_run("khong-co") is None
    assert store.ping()


def test_store_reviews(store: Store):
    record = store.create_run("x", "alice")
    store.add_review(ReviewDecision(run_id=record.id, reviewer="bob", decision="reject", note="sai cột"))
    reviews = store.list_reviews(record.id)
    assert len(reviews) == 1 and reviews[0].note == "sai cột"


def test_signature_ignores_numbers_paths_and_quoted_names():
    a = error_signature("Binder Error: column 'foo' not found at line 3 in C:\\x\\a.sql")
    b = error_signature("Binder Error: column 'bar' not found at line 9 in C:\\y\\b.sql")
    assert a == b
    assert a != error_signature("Parser Error: syntax error at end of input")


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("Lệnh 'DROP' bị chặn", "SAFETY_BLOCKED"),
        ("Binder Error: Referenced column x not found", "BINDER_ERROR"),
        ("Parser Error: syntax error", "PARSER_ERROR"),
        ("Conversion Error: Could not convert string", "CONVERSION_ERROR"),
        ("test.assert_x [fail]: Got 3 results", "TEST_FAILURE"),
        ("điều gì đó lạ", "UNKNOWN"),
    ],
)
def test_classify_error(message: str, code: str):
    assert classify_error(message) == code


def test_error_memory_only_hints_approved_entries(memory: ErrorMemory):
    entry = ErrorEntry(code="BINDER_ERROR", signature="sig1", description="cột không tồn tại")
    first = memory.record(entry)
    again = memory.record(entry)
    assert again.occurrences == 2 and not again.approved
    assert memory.approved_hints("sig1", "BINDER_ERROR") == []
    assert memory.approve(first.id, "dùng đúng tên cột trong danh mục")
    hints = memory.approved_hints("sig1", "BINDER_ERROR")
    assert len(hints) == 1 and hints[0].fix.startswith("dùng đúng")
    assert memory.pending() == []


def test_error_memory_discard(memory: ErrorMemory):
    entry = memory.record(ErrorEntry(code="X", signature="s2", description="d"))
    assert memory.discard(entry.id)
    assert not memory.discard(entry.id)
    assert not memory.approve(999, "")
