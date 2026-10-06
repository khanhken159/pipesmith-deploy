"""Chạy ELT-Bench-Verified (10 pipeline nhẹ nhất) trên hệ thống P-113. Dữ liệu có sẵn ở eval/datasets/eltbench/.

Hai chế độ:
- `--mode reference`: chạy model dbt chuẩn (nếu có) qua E0 nạp nguồn + V1 an toàn, so với bảng kết quả đúng.
  Dùng để kiểm chứng bộ chấm (nạp dữ liệu, kiểu dữ liệu, cách so) trước khi chấm agent. Không cần LLM.
- `--mode agent`: mỗi model một lần chạy trọn luồng (yêu cầu = mô tả trong data_model.yaml), tự duyệt (chỉ cho eval),
  rồi so bảng đích với bảng kết quả đúng. Chỉ có ý nghĩa với LLM thật; với `mock` ghi "không áp dụng (mô phỏng)".

    python eval/benchmarks/eltbench/run_eltbench.py --mode reference
    python eval/benchmarks/eltbench/run_eltbench.py --mode agent --provider openai
"""

import argparse
import os
import shutil
import sys
import time
from datetime import date
from pathlib import Path

import duckdb
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from gt_compare import compare_to_ground_truth  # noqa: E402

from src.agents import runner  # noqa: E402
from src.agents.nodes.safety import check_sql  # noqa: E402
from src.agents.runner import ResumeRequest, RunOutcome  # noqa: E402
from src.agents.tools.duckdb_tools import discover_sources, ingest_sources, read_catalog, run_query  # noqa: E402
from src.agents.tools.sql_tools import render_dbt_sql  # noqa: E402
from src.config import get_settings  # noqa: E402
from src.models.evidence import ReviewDecision  # noqa: E402

DATA_DIR = ROOT / "eval" / "datasets" / "eltbench"
WORK_DIR = ROOT / "data" / "eltbench_work"  # sandbox tạm (git-ignored)
REFERENCE_DIR = HERE / "reference"
REPORT = ROOT / "eval" / "results" / "eltbench_report.md"
EVAL_USER, EVAL_REVIEWER = "eltbench-eval", "eltbench-auto-reviewer"


def task_names() -> list[str]:
    """Danh sách task đã chọn."""
    return [t["name"] for t in yaml.safe_load((HERE / "tasks.yaml").read_text(encoding="utf-8"))["tasks"]]


def models_of(task: str) -> list[dict]:
    """Các model (bảng đích) cần xây của một task, kèm mô tả cột."""
    return yaml.safe_load((DATA_DIR / task / "data_model.yaml").read_text(encoding="utf-8"))["models"]


def request_text(model: dict) -> str:
    """Yêu cầu bằng lời cho Planner, dựng từ data_model.yaml (giữ nguyên mô tả gốc tiếng Anh)."""
    columns = "\n".join(f"- {c['name']}: {str(c.get('description', '')).strip()}" for c in model.get("columns", []))
    return (
        f"Xây bảng đích `{model['name']}` từ các bảng nguồn có sẵn. Mô tả: {model.get('description', '')}\n"
        f"Các cột đầu ra (giữ đúng tên cột):\n{columns}"
    )


def load_task_db(task: str) -> Path:
    """Nạp nguồn của task vào một sandbox tạm (qua E0) — dùng cho chế độ reference."""
    work = WORK_DIR / task
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    db = work / "sandbox.duckdb"
    ingest_sources(db, discover_sources(DATA_DIR / task / "sources"))
    return db


def check_reference(task: str, sql_path: Path, db: Path) -> dict:
    """Model chuẩn → V1 → chạy → so bảng đúng."""
    sql = sql_path.read_text(encoding="utf-8")
    issues = check_sql(sql, read_catalog(db))[0]
    if issues:
        return {"task": task, "model": sql_path.stem, "ok": False, "detail": "V1 chặn: " + "; ".join(issues)[:200]}
    result = run_query(db, render_dbt_sql(sql))
    ok, detail = compare_to_ground_truth(
        result.columns, result.rows, DATA_DIR / task / "ground_truth" / f"{sql_path.stem}.csv"
    )
    return {"task": task, "model": sql_path.stem, "ok": ok, "detail": detail}


def run_reference() -> list[dict]:
    """Chế độ reference cho mọi task có model chuẩn."""
    rows = []
    for task in task_names():
        sql_files = sorted((REFERENCE_DIR / task).glob("*.sql"))
        db = load_task_db(task) if sql_files else None
        rows += [check_reference(task, path, db) for path in sql_files]
    return rows


def _drive(outcome: RunOutcome) -> tuple[RunOutcome, int]:
    """Đi qua các điểm dừng: J1 chọn đáp án đầu (ghi lại số lần), J1b đồng ý, cứu hộ → dừng, J2 → tự duyệt (chỉ cho eval)."""
    auto_answers = 0
    while outcome.pending:
        kind = outcome.pending["kind"]
        if kind == "clarify":
            auto_answers += len(outcome.pending["questions"])
            value = {"answers": {q["id"]: q["options"][0] for q in outcome.pending["questions"]}}
        elif kind == "plan":
            value = {"decision": "approve"}
        elif kind == "rescue":
            value = {"action": "abort"}
        else:
            decision = ReviewDecision(run_id=outcome.run_id, reviewer=EVAL_REVIEWER, decision="approve", note="eval")
            return runner.submit_review(decision, "reviewer"), auto_answers
        outcome = runner.resume_run(ResumeRequest(run_id=outcome.run_id, kind=kind, value=value))
    return outcome, auto_answers


def _target_result(values: dict) -> tuple[list[str], list[tuple]]:
    target = values.get("spec", {}).get("target", "")
    with duckdb.connect(str(Path(values["workspace"]) / "sandbox.duckdb"), read_only=True) as con:
        rel = con.sql(f'SELECT * FROM main."{target}"')
        return rel.columns, rel.fetchall()


def run_agent_model(task: str, model: dict) -> dict:
    """Một lần chạy trọn luồng cho một model, rồi chấm bằng bảng kết quả đúng."""
    os.environ["SOURCES_DIR"] = str(DATA_DIR / task / "sources")
    get_settings.cache_clear()
    start = time.perf_counter()
    outcome, auto_answers = _drive(runner.start_run(request_text(model), EVAL_USER))
    values = runner.get_values(outcome.run_id)
    row = {
        "task": task,
        "model": model["name"],
        "status": str(outcome.status),
        "auto_answers": auto_answers,
        "fix_attempts": values.get("fix_attempts", 0),
        "rescue": values.get("rescue_count", 0),
        "tokens": sum(u.get("input_tokens", 0) + u.get("output_tokens", 0) for u in values.get("llm_usage", [])),
        "cost_usd": sum(u.get("cost_usd", 0.0) for u in values.get("llm_usage", [])),
        "seconds": round(time.perf_counter() - start, 1),
        "ok": False,
        "detail": outcome.error or "",
    }
    if outcome.status == "approved":
        try:
            columns, rows = _target_result(values)
            row["ok"], row["detail"] = compare_to_ground_truth(
                columns, rows, DATA_DIR / task / "ground_truth" / f"{model['name']}.csv"
            )
        except duckdb.Error as exc:
            row["detail"] = f"Không đọc được bảng đích: {str(exc).splitlines()[0][:150]}"
    return row


def run_agent() -> list[dict]:
    """Chế độ agent cho mọi model có bảng kết quả đúng."""
    rows = []
    for task in task_names():
        for model in models_of(task):
            if (DATA_DIR / task / "ground_truth" / f"{model['name']}.csv").exists():
                rows.append(run_agent_model(task, model))
                print(f"{'✓' if rows[-1]['ok'] else '✗'} {task}.{model['name']}: {rows[-1]['detail']}", flush=True)
    return rows


def _header(mode: str) -> list[str]:
    settings = get_settings()
    model = settings.models_summary
    return [
        f"# ELT-Bench-Verified — chế độ `{mode}`",
        "",
        f"- Ngày chạy: {date.today().isoformat()} • provider/model: {settings.llm_provider}/{model}",
        "- Dữ liệu: 10 pipeline nhẹ nhất (eval/benchmarks/eltbench/tasks.yaml); ELT-Bench-Verified, CC BY-SA 4.0.",
        "",
    ]


def write_report(mode: str, rows: list[dict]) -> None:
    """Ghi báo cáo (chỉ số đo thật)."""
    lines = _header(mode)
    if mode == "agent" and get_settings().is_mock:
        lines.append("Không áp dụng (mô phỏng): LLM mock chỉ có câu trả lời viết sẵn cho kịch bản doanh thu ngày.")
    else:
        passed = sum(r["ok"] for r in rows)
        lines += [f"**Khớp bảng kết quả đúng: {passed}/{len(rows)} model**", ""]
        keys = [k for k in rows[0] if k not in ("task", "model")] if rows else []
        lines += ["| Task | Model | " + " | ".join(keys) + " |", "|---|---|" + "---|" * len(keys)]
        lines += [f"| {r['task']} | {r['model']} | " + " | ".join(str(r[k]) for k in keys) + " |" for r in rows]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report = REPORT.with_name(f"eltbench_{mode}.md")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Đã ghi {report}")


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
    if not DATA_DIR.exists():
        sys.exit(
            "Chưa có dữ liệu. Chạy trước: python eval/benchmarks/eltbench/import_eltbench.py --src <thư mục tải về>"
        )
    if args.mode == "agent" and get_settings().is_mock:
        write_report("agent", [])
        return
    write_report(args.mode, run_reference() if args.mode == "reference" else run_agent())


if __name__ == "__main__":
    main()
