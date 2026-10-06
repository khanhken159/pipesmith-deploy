"""Công cụ dbt: dựng workspace từ mẫu, ghi file sinh ra, chạy `dbt build` trong tiến trình con có timeout."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from src.config import get_settings

GENERATED_DIRS = ("models/staging", "models/marts", "tests", "dags")
ALLOWED_PREFIXES = ("models/staging/", "models/marts/", "tests/", "dags/")
PROFILE_NAME = "p113_sandbox"


class DbtNodeResult(BaseModel):
    """Kết quả một model/test trong `run_results.json`."""

    unique_id: str
    status: str
    message: str = ""


class DbtResult(BaseModel):
    """Kết quả một lần chạy dbt."""

    ok: bool
    results: list[DbtNodeResult] = Field(default_factory=list)
    log_tail: str = ""
    timed_out: bool = False


def workspace_path(run_id: str) -> Path:
    """Thư mục làm việc của một lần chạy (git-ignored)."""
    return get_settings().workspaces_dir.resolve() / run_id


def prepare_workspace(run_id: str) -> Path:
    """Chép dự án dbt mẫu vào workspace và tạo profiles.yml trỏ tới sandbox DuckDB."""
    settings = get_settings()
    workspace = workspace_path(run_id)
    shutil.copytree(settings.template_dir, workspace, dirs_exist_ok=True)
    profile = {
        PROFILE_NAME: {
            "target": "sandbox",
            "outputs": {
                "sandbox": {
                    "type": "duckdb",
                    "path": str((workspace / "sandbox.duckdb").as_posix()),
                    "threads": settings.sandbox_threads,
                    "settings": {"memory_limit": settings.sandbox_memory_limit, "enable_external_access": False},
                }
            },
        }
    }
    (workspace / "profiles.yml").write_text(yaml.safe_dump(profile, sort_keys=False), encoding="utf-8")
    return workspace


def write_sources_yml(workspace: Path, tables: list[str]) -> None:
    """Khai báo nguồn raw cho dbt từ danh mục thật (code sinh, không phải LLM)."""
    doc = {"version": 2, "sources": [{"name": "raw", "schema": "raw", "tables": [{"name": t} for t in tables]}]}
    sources_path = workspace / "models" / "sources.yml"
    sources_path.parent.mkdir(parents=True, exist_ok=True)
    sources_path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def is_allowed_path(relative: str) -> bool:
    """File sinh ra chỉ được nằm trong các thư mục cho phép, không có `..` hay đường dẫn tuyệt đối."""
    normalized = relative.replace("\\", "/")
    return normalized.startswith(ALLOWED_PREFIXES) and ".." not in normalized.split("/") and ":" not in normalized


def write_generated_files(workspace: Path, files: dict[str, str]) -> None:
    """Xóa file sinh lần trước rồi ghi bộ file mới (đường dẫn đã được V1 kiểm tra)."""
    for folder in GENERATED_DIRS:
        shutil.rmtree(workspace / folder, ignore_errors=True)
        (workspace / folder).mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        if not is_allowed_path(relative):
            continue
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _dbt_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.endswith(("_API_KEY", "_TOKEN", "_SECRET"))}
    env.update({"DBT_SEND_ANONYMOUS_USAGE_STATS": "false", "DBT_USE_COLORS": "false", "PYTHONIOENCODING": "utf-8"})
    return env


def _read_run_results(workspace: Path) -> list[DbtNodeResult]:
    path = workspace / "target" / "run_results.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        DbtNodeResult(unique_id=r["unique_id"], status=r["status"], message=str(r.get("message") or ""))
        for r in data.get("results", [])
    ]


def run_dbt_build(workspace: Path) -> DbtResult:
    """V2: chạy `dbt build` trong tiến trình con (timeout, không có khóa API trong môi trường)."""
    (workspace / "target" / "run_results.json").unlink(missing_ok=True)
    command = [
        sys.executable,
        "-m",
        "dbt.cli.main",
        "build",
        "--project-dir",
        str(workspace),
        "--profiles-dir",
        str(workspace),
        "--no-use-colors",
    ]
    try:
        proc = subprocess.run(  # noqa: S603 — lệnh cố định, không ghép chuỗi từ LLM
            command,
            cwd=workspace,
            env=_dbt_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=get_settings().sandbox_timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return DbtResult(ok=False, timed_out=True, log_tail="dbt build vượt quá thời gian cho phép.")
    results = _read_run_results(workspace)
    ok = proc.returncode == 0 and all(r.status in ("success", "pass") for r in results)
    return DbtResult(ok=ok, results=results, log_tail="\n".join(proc.stdout.splitlines()[-25:]))
