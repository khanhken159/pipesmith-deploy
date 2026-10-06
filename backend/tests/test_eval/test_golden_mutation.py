"""Test bộ đánh giá Phase 6: golden (kết quả đúng kiểm bằng SQL chuẩn), đột biến áp dụng được, chọn đáp án J1."""

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "eval" / "golden"))

import run_golden  # noqa: E402
from harness import _choose  # noqa: E402

MUTANTS = yaml.safe_load((ROOT / "eval" / "mutation" / "mutants.yaml").read_text(encoding="utf-8"))["mutants"]


def test_golden_has_at_least_ten_scored_cases():
    scored = [c for c in run_golden.cases() if (c / "expected.csv").exists()]
    assert len(scored) >= 10
    assert any(run_golden.meta_of(c).get("expect_questions") for c in run_golden.cases())


@pytest.mark.parametrize(
    "case", [c for c in run_golden.cases() if (c / "reference.sql").exists()], ids=lambda c: c.name
)
def test_golden_expected_matches_reference_sql(case: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Kết quả đúng tính tay (expected.csv) phải khớp câu SQL chuẩn chạy độc lập."""
    monkeypatch.setattr(run_golden, "WORK_DIR", tmp_path)
    result = run_golden.check_reference(case)
    assert result["ok"], result["detail"]


@pytest.mark.parametrize("mutant", MUTANTS, ids=lambda m: m["id"])
def test_every_mutant_applies_to_base_pipeline(mutant: dict, built_state: dict):
    """Đột biến phải tìm thấy đoạn code cần thay; nếu pipeline mẫu đổi thì test này báo để sửa mutants.yaml."""
    assert mutant["old"] in built_state["code_files"][mutant["file"]]


@pytest.mark.parametrize(
    ("prefer", "expected"),
    [(["hoàn tất"], "Chỉ đơn hoàn tất"), ([], "Mọi đơn"), (["không có"], "Mọi đơn")],
)
def test_clarify_choice_prefers_keywords(prefer: list[str], expected: str):
    question = {"id": "q", "question": "?", "options": ["Mọi đơn", "Chỉ đơn hoàn tất"]}
    assert _choose(question, prefer) == expected
