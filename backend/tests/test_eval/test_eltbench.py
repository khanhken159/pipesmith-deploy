"""Test bộ chấm ELT-Bench: so với bảng kết quả đúng, dựng yêu cầu, đọc cấu hình nguồn, chạy model chuẩn."""

import sys
from pathlib import Path

import pytest

ELTBENCH = Path(__file__).resolve().parents[2] / "eval" / "benchmarks" / "eltbench"
sys.path.insert(0, str(ELTBENCH))

import run_eltbench  # noqa: E402
from gt_compare import compare_to_ground_truth, normalize  # noqa: E402
from import_eltbench import source_tables  # noqa: E402
from run_eltbench import request_text  # noqa: E402

GT = "COURSE_ID,NAME,PER_UG,PASSED\n1.0,Machine Learning,14.285714,true\n2.0,Database,,false\n"


@pytest.fixture
def gt_csv(tmp_path: Path) -> Path:
    path = tmp_path / "courses.csv"
    path.write_text(GT, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("1.0", 1.0),
        (3, 3.0),
        ("TRUE", 1.0),
        ("abc ", "abc"),
        ("2016-01-01 00:00:00.000", "2016-01-01 00:00:00"),
    ],
)
def test_normalize(value: object, expected: object):
    assert normalize(value) == expected


def test_matches_ignoring_column_case_order_row_order_and_rounding(gt_csv: Path):
    columns = ["passed", "per_ug", "name", "course_id"]
    rows = [(False, None, "Database", 2), (True, 14.2857142857, "Machine Learning", 1)]
    assert compare_to_ground_truth(columns, rows, gt_csv) == (True, "Khớp 2 dòng")


@pytest.mark.parametrize(
    ("columns", "rows", "message"),
    [
        (["course_id", "name", "per_ug"], [(1, "Machine Learning", 14.29), (2, "Database", None)], "thiếu"),
        (["course_id", "name", "per_ug", "passed"], [(1, "Machine Learning", 14.285714, True)], "số dòng"),
        (
            ["course_id", "name", "per_ug", "passed"],
            [(1, "Machine Learning", 15.0, True), (2, "Database", None, False)],
            "1/2 dòng khác",
        ),
    ],
)
def test_detects_differences(gt_csv: Path, columns: list[str], rows: list[tuple], message: str):
    ok, detail = compare_to_ground_truth(columns, rows, gt_csv)
    assert not ok and message in detail


def test_request_text_keeps_exact_model_and_column_names():
    text = request_text(
        {
            "name": "trucks",
            "description": "Each record is a truck.",
            "columns": [{"name": "truck_id", "description": "Id"}, {"name": "per_Weight", "description": "%"}],
        }
    )
    assert "`trucks`" in text and "- truck_id: Id" in text and "- per_Weight: %" in text


def test_source_tables_follow_benchmark_file_layout():
    cfg = {
        "postgres": {"config": {"tables": ["registration"]}},
        "mongodb": {"config": {"tables": ["prof"]}},
        "aws_s3": {"data": [{"path": "s3://bucket/RA.csv", "table": "RA"}]},
        "custom_api": {"config": {"tables": ["course"]}},
        "flat_files": [{"table": "student", "format": "jsonl", "path": "https://drive"}],
    }
    tables = {t.name: t for t in source_tables(cfg, "cs_semester")}
    assert tables["registration"].member == "db/cs_semester/registration.csv"
    assert tables["RA"].kind == "aws_s3" and tables["RA"].fmt == "csv"
    assert tables["course"].archive == "data_api.zip"
    assert tables["student"].member == "db/cs_semester/student.jsonl"


def test_dataset_in_repo_has_every_selected_task():
    for task in run_eltbench.task_names():
        folder = run_eltbench.DATA_DIR / task
        assert (folder / "data_model.yaml").exists() and any((folder / "ground_truth").glob("*.csv")), task


def test_reference_models_match_ground_truth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Model dbt chuẩn của cs_semester qua E0 + V1 phải khớp bảng kết quả đúng (kiểm chứng bộ chấm)."""
    monkeypatch.setattr(run_eltbench, "WORK_DIR", tmp_path)
    db = run_eltbench.load_task_db("cs_semester")
    results = [
        run_eltbench.check_reference("cs_semester", path, db)
        for path in sorted((run_eltbench.REFERENCE_DIR / "cs_semester").glob("*.sql"))
    ]
    assert len(results) == 3
    assert all(r["ok"] for r in results), results
