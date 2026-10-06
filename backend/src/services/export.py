"""Đóng gói code của một lần chạy thành file zip để DE đưa vào repo của mình (mở PR → CI/CD).

Chỉ lấy file nguồn của dự án dbt + DAG; bỏ dữ liệu sandbox (`*.duckdb`, `datasets/`), kết quả build (`target/`,
`logs/`) và `profiles.yml` (trỏ tới đường dẫn sandbox trên máy chạy agent).
"""

import io
import zipfile
from pathlib import Path

EXCLUDED_DIRS = {"datasets", "target", "logs", "dbt_packages"}
EXCLUDED_FILES = {"profiles.yml", ".user.yml"}
EXCLUDED_SUFFIXES = {".duckdb", ".wal"}


def is_exported(relative: Path) -> bool:
    """File có nằm trong gói tải về không."""
    if relative.parts and relative.parts[0] in EXCLUDED_DIRS:
        return False
    return relative.name not in EXCLUDED_FILES and relative.suffix not in EXCLUDED_SUFFIXES


def export_zip(workspace: Path, folder: str) -> bytes:
    """Nén các file nguồn của workspace; mọi file nằm trong thư mục gốc `folder` của zip."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in workspace.rglob("*") if p.is_file()):
            relative = path.relative_to(workspace)
            if is_exported(relative):
                archive.write(path, f"{folder}/{relative.as_posix()}")
    return buffer.getvalue()
