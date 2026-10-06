"""Chạy các đích giống Makefile trên máy không có `make` (Windows): `python scripts/tasks.py ci`."""

import os
import shutil
import subprocess
import sys

PY = sys.executable
NPM = shutil.which("npm") or "npm"  # Windows: npm.cmd
DEMO_REQUEST = "Gộp dữ liệu đơn hàng 3 nguồn (Shopee CSV, Tiki JSON, website SQLite), tính doanh thu theo ngày"
TASKS: dict[str, list[list[str]]] = {
    "run": [[PY, "-m", "uvicorn", "src.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]],
    "test": [[PY, "-m", "pytest"]],
    "lint": [[PY, "-m", "ruff", "check", "src/", "tests/"]],
    "format": [[PY, "-m", "ruff", "format", "src/", "tests/"]],
    "ci": [
        [PY, "-m", "ruff", "check", "src/", "tests/"],
        [PY, "-m", "ruff", "format", "--check", "src/", "tests/"],
        [PY, "-m", "pytest"],
    ],
    "doctor": [[PY, "-m", "src.cli", "doctor"]],
    "seed": [[PY, "-m", "src.cli", "seed"]],
    "demo": [
        [PY, "-m", "src.cli", "seed"],
        [
            PY,
            "-m",
            "src.cli",
            "--provider",
            "mock",
            "run",
            "--request",
            DEMO_REQUEST,
            "--as",
            "engineer",
            "--user",
            "an",
            "--auto-answer",
        ],
        [
            PY,
            "-m",
            "src.cli",
            "--provider",
            "mock",
            "review",
            "latest",
            "--as",
            "reviewer",
            "--user",
            "binh",
            "--approve",
        ],
    ],
    "eval": [[PY, "eval/run_eval.py"]],
    "eval-llm": [[PY, "eval/run_eval.py", "--with-llm"]],
    "frontend-dev": [[NPM, "--prefix", "frontend", "run", "dev"]],
    "frontend-build": [[NPM, "--prefix", "frontend", "run", "build"]],
    "frontend-check": [
        [NPM, "--prefix", "frontend", "run", script] for script in ("lint", "format:check", "typecheck", "build")
    ],
    "docker-up": [["docker", "compose", "up", "--build", "-d"]],
    "docker-down": [["docker", "compose", "down"]],
}


def main() -> int:
    """Chạy lần lượt các lệnh của đích; dừng ở lệnh lỗi đầu tiên."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2 or sys.argv[1] not in TASKS:
        print(f"Cách dùng: python scripts/tasks.py <{'|'.join(TASKS)}>")
        return 2
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for command in TASKS[sys.argv[1]]:
        print(f"$ {' '.join(['python', *command[1:]] if command[0] == PY else command)}", flush=True)
        code = subprocess.run(command, env=env, check=False).returncode
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
