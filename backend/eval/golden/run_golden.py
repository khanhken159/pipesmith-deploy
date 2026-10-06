"""Chạy bộ golden (eval/datasets/golden/<id>/): yêu cầu bằng lời + nguồn nhỏ + kết quả đúng đã kiểm tay.

- `--mode reference`: chạy câu SQL chuẩn (reference.sql) qua E0 nạp nguồn + V1 an toàn rồi so `expected.csv`.
  Mục đích: kiểm chứng lại phép tính tay trong expected.csv và bộ chấm. Không cần LLM.
- `--mode agent`: mỗi ca một lần chạy trọn luồng (tự trả lời J1 theo từ khóa ưu tiên, tự duyệt — CHỈ cho eval),
  rồi so bảng đích với `expected.csv`. Với `mock` ghi "không áp dụng (mô phỏng)".

    python eval/golden/run_golden.py --mode reference
    python eval/golden/run_golden.py --mode agent --provider openai
"""

import argparse
import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path

import duckdb
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "eval" / "benchmarks" / "eltbench"))

from gt_compare import compare_to_ground_truth  # noqa: E402
from harness import run_request, target_result, usage_totals  # noqa: E402

from src.agents import runner  # noqa: E402
from src.agents.nodes.safety import check_sql  # noqa: E402
from src.agents.tools.duckdb_tools import discover_sources, ingest_sources, read_catalog, run_query  # noqa: E402
from src.agents.tools.sql_tools import render_dbt_sql  # noqa: E402
from src.config import get_settings  # noqa: E402

CASES_DIR = ROOT / "eval" / "datasets" / "golden"
WORK_DIR = ROOT / "data" / "eval_work" / "golden"
RESULTS = ROOT / "eval" / "results"


def cases() -> list[Path]:
    """Thư mục các ca golden, theo thứ tự tên."""
    return sorted(p for p in CASES_DIR.iterdir() if (p / "meta.yaml").exists())


def meta_of(case: Path) -> dict:
    """meta.yaml của một ca."""
    return yaml.safe_load((case / "meta.yaml").read_text(encoding="utf-8"))


def check_reference(case: Path) -> dict:
    """SQL chuẩn → E0 nạp nguồn → V1 → chạy → so expected.csv."""
    db = WORK_DIR / case.name / "sandbox.duckdb"
    shutil.rmtree(db.parent, ignore_errors=True)
    db.parent.mkdir(parents=True)
    ingest_sources(db, discover_sources(case / "sources"))
    sql = (case / "reference.sql").read_text(encoding="utf-8")
    issues = check_sql(sql, read_catalog(db))[0]
    if issues:
        return {"case": case.name, "ok": False, "detail": "V1 chặn: " + "; ".join(issues)[:200]}
    result = run_query(db, render_dbt_sql(sql))
    ok, detail = compare_to_ground_truth(result.columns, result.rows, case / "expected.csv")
    return {"case": case.name, "ok": ok, "detail": detail}


def _result_score(values: dict, case: Path) -> tuple[bool, str]:
    try:
        columns, rows = target_result(values)
    except (KeyError, duckdb.Error) as exc:
        return False, f"Không đọc được bảng đích: {str(exc).splitlines()[0][:120]}"
    return compare_to_ground_truth(columns, rows, case / "expected.csv")


def run_agent_case(case: Path) -> dict:
    """Một ca golden chạy trọn luồng, chấm bằng code."""
    meta = meta_of(case)
    request = (case / "request.txt").read_text(encoding="utf-8").strip()
    run = run_request(request, case / "sources", meta.get("clarify_prefer", []))
    values = runner.get_values(run.run_id)
    tokens, cost = usage_totals(values)
    if meta.get("score") == "questions_only":
        ok, detail = run.questions_asked > 0, f"đã hỏi {run.questions_asked} câu làm rõ"
    elif run.status != "approved":
        ok, detail = False, run.error[:160] or run.status
    else:
        ok, detail = _result_score(values, case)
    return {
        "case": case.name,
        "ok": ok,
        "mode_ok": values.get("spec", {}).get("mode") == meta.get("expected_mode"),
        "asked": run.questions_asked,
        "v_failures": len(values.get("error_signatures", [])),
        "tokens": tokens,
        "cost_usd": cost,
        "seconds": run.seconds,
        "detail": detail,
    }


def _table(rows: list[dict]) -> list[str]:
    keys = [k for k in rows[0] if k != "case"] if rows else []
    lines = ["| Ca | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for r in rows:
        cells = [str(r[k]).replace("|", "\\|") for k in keys]
        lines.append(f"| {r['case']} | " + " | ".join(cells) + " |")
    return lines


def write_report(mode: str, rows: list[dict]) -> None:
    """Ghi báo cáo + JSON (chỉ số đo thật, kèm provider/model)."""
    settings = get_settings()
    lines = [
        f"# Bộ golden — chế độ `{mode}`",
        "",
        f"- Ngày chạy: {date.today().isoformat()} • provider/model: {settings.llm_provider}/{settings.models_summary}",
        f"- {len(cases())} ca trong eval/datasets/golden (dữ liệu nhỏ, kết quả đúng tính tay + kiểm bằng SQL chuẩn).",
        "",
    ]
    if mode == "agent" and settings.is_mock:
        lines.append("Không áp dụng (mô phỏng): LLM mock chỉ có câu trả lời viết sẵn cho kịch bản doanh thu ngày.")
    else:
        lines += [f"**Đạt: {sum(r['ok'] for r in rows)}/{len(rows)} ca**", "", *_table(rows)]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"golden_{mode}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {"provider": settings.llm_provider, "model": settings.models_summary, "rows": rows}
    (RESULTS / f"golden_{mode}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    """Chạy theo chế độ đã chọn."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("reference", "agent"), default="reference")
    parser.add_argument("--provider", choices=("mock", "openai", "google"), help="Ghi đè LLM_PROVIDER")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    get_settings.cache_clear()
    if args.mode == "agent" and get_settings().is_mock:
        write_report("agent", [])
        return
    rows = []
    for case in cases():
        if args.mode == "reference" and not (case / "reference.sql").exists():
            continue
        rows.append(check_reference(case) if args.mode == "reference" else run_agent_case(case))
        print(f"{'✓' if rows[-1]['ok'] else '✗'} {case.name}: {rows[-1]['detail']}", flush=True)
    write_report(args.mode, rows)


if __name__ == "__main__":
    main()
