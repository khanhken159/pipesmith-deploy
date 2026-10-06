"""Nhập 10 pipeline ELT-Bench-Verified nhẹ nhất vào eval/datasets/eltbench/<task>/ (đã có sẵn trong repo, ~700 KB).

Chỉ lấy: bảng nguồn thô, yêu cầu (data_model.yaml), bảng kết quả đúng (gt_verified), câu kiểm tra (evaluation/).
Bỏ: Airbyte, Terraform, cấu hình Snowflake. Thư mục tải về chỉ được ĐỌC, không sửa.

Kiểu dữ liệu giữ đúng như khi Airbyte nạp vào kho (bảng kết quả đúng được tính trên dữ liệu đó):
- CSV từ postgres / mongodb / API / flat file → Parquet có kiểu (DuckDB tự nhận kiểu trên toàn bộ file).
- CSV từ S3 → giữ CSV (hệ thống đọc dạng chuỗi, giống Airbyte nạp file S3).
- jsonl / parquet → chép nguyên.

Cách chạy:
    python eval/benchmarks/eltbench/import_eltbench.py --src "F:/.../data/external"
"""

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import duckdb
import yaml
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[3]
TASKS_FILE = Path(__file__).resolve().parent / "tasks.yaml"
OUT_DIR = ROOT / "eval" / "datasets" / "eltbench"


class SourceTable(BaseModel):
    """Một bảng nguồn: tên, loại nguồn gốc, file trong zip, định dạng."""

    name: str
    kind: str
    archive: str
    member: str
    fmt: str


def _tables_of(kind: str, cfg: dict) -> list[str]:
    return (cfg.get(kind) or {}).get("config", {}).get("tables", [])


def _file_tables(cfg: dict, task: str) -> list[SourceTable]:
    """Bảng từ file: S3 (tên file có thể khác tên bảng) và flat file."""
    tables = []
    for item in (cfg.get("aws_s3") or {}).get("data", []):
        filename = item["path"].rsplit("/", 1)[-1]
        tables.append(
            SourceTable(
                name=item["table"],
                kind="aws_s3",
                archive="data_db.zip",
                member=f"db/{task}/{filename}",
                fmt=filename.rsplit(".", 1)[-1],
            )
        )
    for item in cfg.get("flat_files") or []:
        tables.append(
            SourceTable(
                name=item["table"],
                kind="flat_files",
                archive="data_db.zip",
                member=f"db/{task}/{item['table']}.{item['format']}",
                fmt=item["format"],
            )
        )
    return tables


def source_tables(cfg: dict, task: str) -> list[SourceTable]:
    """Danh sách bảng nguồn theo đúng quy ước file của ELT-Bench-Verified."""
    tables = [
        SourceTable(name=t, kind=k, archive="data_db.zip", member=f"db/{task}/{t}.csv", fmt="csv")
        for k in ("postgres", "mongodb")
        for t in _tables_of(k, cfg)
    ]
    tables += [
        SourceTable(name=t, kind="custom_api", archive="data_api.zip", member=f"api/{task}/{t}.csv", fmt="csv")
        for t in _tables_of("custom_api", cfg)
    ]
    return tables + _file_tables(cfg, task)


def _csv_to_parquet(csv_bytes: bytes, target: Path) -> None:
    with tempfile.TemporaryDirectory(dir=OUT_DIR) as tmp:
        csv_path = Path(tmp) / "src.csv"
        csv_path.write_bytes(csv_bytes)
        with duckdb.connect() as con:
            con.execute(
                f"COPY (SELECT * FROM read_csv('{csv_path.as_posix()}', header = true, sample_size = -1)) "
                f"TO '{target.as_posix()}' (FORMAT parquet)"
            )


def export_table(raw: Path, table: SourceTable, out: Path) -> str:
    """Ghi một bảng nguồn vào thư mục sources/ theo quy tắc kiểu ở đầu file; trả về tên file."""
    with zipfile.ZipFile(raw / table.archive) as archive:
        data = archive.read(table.member)
    if table.fmt == "csv" and table.kind != "aws_s3":
        target = out / f"{table.name}.parquet"
        _csv_to_parquet(data, target)
    else:
        target = out / f"{table.name}.{'json' if table.fmt in ('jsonl', 'json') else table.fmt}"
        target.write_bytes(data)
    return target.name


def export_ground_truth(raw: Path, task: str, out: Path) -> list[str]:
    """Chép bảng kết quả đúng gt_verified/<task>/<model>.csv."""
    out.mkdir(parents=True, exist_ok=True)
    copied = []
    with zipfile.ZipFile(raw / "ground_truth.zip") as archive:
        for member in archive.namelist():
            if member.startswith(f"gt_verified/{task}/") and member.endswith(".csv"):
                (out / Path(member).name).write_bytes(archive.read(member))
                copied.append(Path(member).stem)
    return copied


def import_task(src: Path, task: str) -> dict:
    """Nhập một task; trả về manifest."""
    repo, raw, out = src / "ELT-Bench-Verified", src / "eltbench_raw", OUT_DIR / task
    shutil.rmtree(out, ignore_errors=True)
    (out / "sources").mkdir(parents=True)
    cfg = yaml.safe_load((repo / "tasks" / task / "config.yaml").read_text(encoding="utf-8"))
    tables = source_tables(cfg, task)
    files = {t.name: {"kind": t.kind, "file": export_table(raw, t, out / "sources")} for t in tables}
    shutil.copy(repo / "tasks" / task / "data_model.yaml", out / "data_model.yaml")
    shutil.copytree(repo / "evaluation" / task, out / "evaluation", dirs_exist_ok=True)
    models = export_ground_truth(raw, task, out / "ground_truth")
    manifest = {
        "task": task,
        "tables": files,
        "models_with_ground_truth": sorted(models),
        "origin": "ELT-Bench-Verified (CC BY-SA 4.0), github.com/czanoli/ELT-Bench nhánh elt-bench-pr",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def main() -> None:
    """Nhập mọi task trong tasks.yaml."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", required=True, type=Path, help="Thư mục chứa ELT-Bench-Verified/ và eltbench_raw/")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for item in yaml.safe_load(TASKS_FILE.read_text(encoding="utf-8"))["tasks"]:
        manifest = import_task(args.src, item["name"])
        print(
            f"✓ {item['name']}: {len(manifest['tables'])} bảng nguồn, "
            f"{len(manifest['models_with_ground_truth'])} bảng kết quả đúng"
        )
    print(f"Đã nhập vào {OUT_DIR}")


if __name__ == "__main__":
    main()
