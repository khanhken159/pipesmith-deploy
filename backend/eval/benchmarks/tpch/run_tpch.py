"""Benchmark tốc độ E4 + V3 trên 13 truy vấn TPC-H viết chậm cố ý (bộ query lấy từ nhánh feature/optimizer-agent).

Cần mạng lần đầu (DuckDB tải extension `tpch`), nên KHÔNG chạy trong CI. Cách chạy:
    python eval/benchmarks/tpch/run_tpch.py --sf 1
Kết quả ghi vào eval/results/tpch_benchmark.md (kèm provider/model). Đáp án đúng = truy vấn chuẩn TPC-H.
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.agents.nodes.compare import compare_results  # noqa: E402
from src.agents.nodes.optimizer import OptimizeJob, optimize_standalone  # noqa: E402
from src.agents.tools.duckdb_tools import run_query  # noqa: E402
from src.config import get_settings  # noqa: E402

SLOW_DIR = Path(__file__).resolve().parent / "slow"
HEADER_RE = re.compile(r"^--\s*(\w+)\s*:\s*(.*)$")
REPORT = ROOT / "eval" / "results" / "tpch_benchmark.md"


def parse_header(text: str) -> dict[str, str]:
    """Đọc các dòng `-- key: value` đầu file."""
    meta = {}
    for line in text.splitlines():
        match = HEADER_RE.match(line.strip())
        if not match:
            break
        meta[match.group(1).lower()] = match.group(2).strip()
    return meta


def prepare_db(sf: float) -> Path:
    """Sinh dữ liệu TPC-H vào data/tpch_sf<sf>.duckdb (bỏ qua nếu đã có)."""
    db = ROOT / "data" / f"tpch_sf{sf}.duckdb"
    db.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db)) as con:
        con.execute("INSTALL tpch")
        con.execute("LOAD tpch")
        if not con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'lineitem'").fetchone()[
            0
        ]:
            con.execute(f"CALL dbgen(sf = {sf})")
    return db


def reference_sql(db: Path, number: int) -> str:
    """Truy vấn chuẩn TPC-H số `number`."""
    with duckdb.connect(str(db), read_only=True) as con:
        con.execute("LOAD tpch")
        return (
            con.execute("SELECT query FROM tpch_queries() WHERE query_nr = ?", [number])
            .fetchone()[0]
            .strip()
            .rstrip(";")
        )


def run_one(db: Path, path: Path) -> dict:
    """Kiểm tra query chậm đúng với đáp án chuẩn, rồi chạy E4 + V3 trên nó."""
    text = path.read_text(encoding="utf-8")
    meta = parse_header(text)
    sql = "\n".join(line for line in text.splitlines() if not HEADER_RE.match(line.strip())).strip().rstrip(";")
    reference = reference_sql(db, int(meta["reference"].split(":")[1]))
    correct, _ = compare_results(run_query(db, reference), run_query(db, sql), get_settings().compare_abs_tol)
    report, usages = optimize_standalone(OptimizeJob(sql=sql, datasets={"small": str(db), "large": str(db)}))
    return {
        "name": path.stem,
        "pattern": meta.get("pattern", ""),
        "slow_correct": correct,
        "report": report,
        "llm_calls": len(usages),
    }


def _row(r: dict) -> str:
    rep = r["report"]
    before = rep.before.median_ms if rep.before else None
    after = rep.after.median_ms if rep.after else None
    source = rep.explanation.split("]")[0].lstrip("[") if rep.explanation.startswith("[") else "llm"
    gain = f"{rep.improvement_pct}%" if rep.improvement_pct is not None else "—"
    return (
        f"| {r['name']} | {'✓' if r['slow_correct'] else '✗'} | {rep.decision} | {source} | "
        f"{before if before is not None else '—'} | {after if after is not None else '—'} | {gain} | {r['llm_calls']} |"
    )


def write_report(rows: list[dict], sf: float) -> None:
    """Ghi bảng kết quả (chỉ số đo thật)."""
    settings = get_settings()
    model = settings.models_summary
    lines = [
        "# Benchmark TPC-H — Optimizer (E4) + Đối chiếu (V3)",
        "",
        f"- Ngày đo: {date.today().isoformat()} • scale factor: {sf} • provider/model: {settings.llm_provider}/{model}",
        f"- Ngưỡng áp dụng: nhanh hơn ≥ {settings.opt_min_gain_pct}% và kết quả giống hệt; trung vị của {settings.opt_bench_runs} lần đo.",
        "",
        "| Query | Query chậm đúng đáp án | Quyết định | Nguồn đề xuất | Trước (ms) | Sau (ms) | Cải thiện | Gọi LLM |",
        "|---|---|---|---|---|---|---|---|",
        *[_row(r) for r in rows],
        "",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Chạy toàn bộ bộ query chậm."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sf", type=float, default=1.0, help="Scale factor TPC-H (mặc định 1)")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    db = prepare_db(args.sf)
    rows = []
    for path in sorted(SLOW_DIR.glob("*.sql")):
        rows.append(run_one(db, path))
        print(_row(rows[-1]), flush=True)
    write_report(rows, args.sf)
    print(f"Đã ghi {REPORT}")


if __name__ == "__main__":
    main()
