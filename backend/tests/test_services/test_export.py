"""Gói code tải về: chỉ file nguồn dbt + DAG, không kèm dữ liệu sandbox hay đường dẫn máy chạy."""

import io
import zipfile
from pathlib import Path

import pytest

from src.services.export import export_zip, is_exported


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("models/marts/fct.sql", True),
        ("tests/assert_x.sql", True),
        ("dags/x_dag.py", True),
        ("dbt_project.yml", True),
        ("profiles.yml", False),
        ("sandbox.duckdb", False),
        ("datasets/large.duckdb", False),
        ("target/manifest.json", False),
        ("logs/dbt.log", False),
    ],
)
def test_is_exported(path: str, expected: bool):
    assert is_exported(Path(path)) is expected


def test_export_zip_keeps_only_source_files(tmp_path: Path):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "a.sql").write_text("select 1", encoding="utf-8")
    (tmp_path / "sandbox.duckdb").write_bytes(b"x")
    archive = zipfile.ZipFile(io.BytesIO(export_zip(tmp_path, "p113-r1")))
    assert archive.namelist() == ["p113-r1/models/a.sql"]
    assert archive.read("p113-r1/models/a.sql") == b"select 1"
