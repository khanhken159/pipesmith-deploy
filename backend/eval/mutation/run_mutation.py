"""Đo khả năng bắt lỗi của bộ kiểm chứng (V1 An toàn + V2 Sandbox với test đối soát) bằng lỗi giả (đột biến).

Không cần LLM, không cần mạng: pipeline gốc sinh tất định bằng `mock`; mỗi đột biến (eval/mutation/mutants.yaml)
được cấy vào pipeline đúng rồi chạy lại đúng V1 + V2 của hệ thống. Kho lưu trữ/sổ lỗi dùng thư mục tạm riêng
(data/eval_work/mutation, git-ignored) để không lẫn với dữ liệu thật.

    python eval/mutation/run_mutation.py
Kết quả: eval/results/mutation.md (+ mutation.json cho eval/run_eval.py).
"""

import copy
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = ROOT / "data" / "eval_work" / "mutation"
os.environ.update(
    {
        "LLM_PROVIDER": "mock",
        "LLM_FALLBACK": "none",
        "LANGCHAIN_TRACING_V2": "false",
        "STORE_PATH": str(WORK / "app.db"),
        "CHECKPOINT_PATH": str(WORK / "checkpoints.db"),
        "SOURCES_DIR": str(WORK / "sources"),
        "WORKSPACES_DIR": str(WORK / "workspaces"),
        "MOCK_LARGE_ROWS": "20000",
    }
)
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src.agents.nodes.codegen import codegen_node  # noqa: E402
from src.agents.nodes.ingest import ingest_node  # noqa: E402
from src.agents.nodes.mock_data import mock_data_node  # noqa: E402
from src.agents.nodes.planner import planner_node  # noqa: E402
from src.agents.nodes.profiler import profiler_node  # noqa: E402
from src.agents.nodes.safety import safety_node  # noqa: E402
from src.agents.nodes.sandbox_run import sandbox_run_node  # noqa: E402
from src.agents.nodes.testgen import testgen_node  # noqa: E402
from src.services.llm_mock import DUPLICATE_OPTIONS, Q_DUPLICATES, Q_STATUS, STATUS_OPTIONS  # noqa: E402
from src.services.seed import SeedConfig, generate_sources  # noqa: E402

RESULTS = ROOT / "eval" / "results"
FAILED_RE = re.compile(r"(?:test|model)\.\w+\.(\S+) \[(?:fail|error)\]")


class Replacement(BaseModel):
    """Một lần thay chuỗi."""

    old: str
    new: str


class Mutant(BaseModel):
    """Một lỗi giả: thay `old` bằng `new` trong `file` (và các thay thế phụ trong `also`)."""

    id: str
    description: str
    file: str
    old: str
    new: str
    also: list[Replacement] = []
    equivalent: bool = False


class Outcome(BaseModel):
    """Kết quả chạy V1 + V2 trên một phiên bản pipeline."""

    caught: bool
    by: str
    detail: str


def build_base() -> dict:
    """Pipeline đúng (mock, seed cố định): E1 → E0 → P → E2 → E3 → E3b."""
    shutil.rmtree(WORK, ignore_errors=True)
    generate_sources(SeedConfig(out_dir=WORK / "sources", seed=42, dirty=0.05, rows_per_source=120))
    state: dict = {
        "run_id": "mutation-base",
        "request_text": "Gộp đơn hàng 3 nguồn, tính doanh thu ngày",
        "requester": "eval",
        "answers": {Q_STATUS: STATUS_OPTIONS[0], Q_DUPLICATES: DUPLICATE_OPTIONS[0]},
    }
    for node in (planner_node, ingest_node, profiler_node, mock_data_node, codegen_node, testgen_node):
        state.update(node(state))
    return state


def verify(state: dict) -> Outcome:
    """Chạy đúng V1 rồi V2 của hệ thống; trả về bước nào bắt được lỗi."""
    issues = safety_node(state)["safety"]["issues"]
    if issues:
        return Outcome(caught=True, by="V1 An toàn", detail=issues[0][:160])
    sandbox = sandbox_run_node(state)["sandbox"]
    if sandbox["passed"]:
        return Outcome(caught=False, by="—", detail=f"{sandbox.get('tests_ok')}/{sandbox.get('tests_total')} test đạt")
    failed = sorted(set(FAILED_RE.findall(sandbox["error"]))) or ["dbt build"]
    return Outcome(caught=True, by="V2: " + ", ".join(failed), detail=sandbox["error"].splitlines()[0][:160])


def apply_mutant(base: dict, mutant: Mutant) -> dict | None:
    """Bản sao pipeline đã cấy lỗi; None nếu đoạn code cần thay không còn trong file."""
    state = copy.deepcopy(base)
    files = state["code_files"]
    for change in [Replacement(old=mutant.old, new=mutant.new), *mutant.also]:
        if change.old not in files.get(mutant.file, ""):
            return None
        files[mutant.file] = files[mutant.file].replace(change.old, change.new)
    return state


def run_all(base: dict, mutants: list[Mutant]) -> list[dict]:
    """Chạy mọi đột biến; mỗi dòng gồm mô tả + kết quả."""
    rows = []
    for mutant in mutants:
        state = apply_mutant(base, mutant)
        outcome = verify(state) if state else Outcome(caught=False, by="không áp dụng", detail="không tìm thấy `old`")
        rows.append(
            {**mutant.model_dump(exclude={"old", "new", "also"}), **outcome.model_dump(), "applied": state is not None}
        )
        print(f"{'✓' if outcome.caught != mutant.equivalent else '✗'} {mutant.id}: {outcome.by}", flush=True)
    return rows


def summarize(rows: list[dict]) -> dict:
    """Tỉ lệ bắt lỗi (đột biến thật) và báo động nhầm (đột biến đối chứng)."""
    real = [r for r in rows if r["applied"] and not r["equivalent"]]
    controls = [r for r in rows if r["applied"] and r["equivalent"]]
    caught = sum(r["caught"] for r in real)
    return {
        "date": date.today().isoformat(),
        "provider": "mock (pipeline gốc tất định; không dùng LLM để chấm)",
        "real_total": len(real),
        "real_caught": caught,
        "kill_rate_pct": round(100 * caught / len(real), 1) if real else None,
        "controls_total": len(controls),
        "false_alarms": sum(r["caught"] for r in controls),
        "not_applied": sum(not r["applied"] for r in rows),
    }


def write_report(summary: dict, rows: list[dict]) -> None:
    """Ghi bảng kết quả (chỉ số đo thật)."""
    lines = [
        "# Mutation test — bộ kiểm chứng có bắt được lỗi giả không?",
        "",
        f"- Ngày chạy: {summary['date']} • {summary['provider']}",
        "- Pipeline gốc: gộp 3 nguồn, doanh thu ngày (dữ liệu giả lập, seed 42). Kiểm chứng: V1 An toàn + V2 dbt build/test.",
        "",
        f"**Bắt được {summary['real_caught']}/{summary['real_total']} lỗi giả ({summary['kill_rate_pct']}%)**; "
        f"báo động nhầm ở đột biến đối chứng: {summary['false_alarms']}/{summary['controls_total']}.",
        "",
        "| Đột biến | Mô tả | Đối chứng | Bị bắt | Bắt bởi | Chi tiết |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        detail = r["detail"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {r['id']} | {r['description']} | {'có' if r['equivalent'] else ''} | "
            f"{'✓' if r['caught'] else '✗'} | {r['by']} | {detail} |"
        )
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "mutation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = {"summary": summary, "rows": rows}
    (RESULTS / "mutation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    """Dựng pipeline gốc, kiểm tra nó đạt, rồi chạy từng đột biến."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    config = yaml.safe_load((HERE / "mutants.yaml").read_text(encoding="utf-8"))
    base = build_base()
    sanity = verify(copy.deepcopy(base))
    if sanity.caught:
        sys.exit(f"Pipeline gốc không đạt ({sanity.by}: {sanity.detail}) — không thể đo đột biến.")
    print(f"Pipeline gốc đạt: {sanity.detail}", flush=True)
    rows = run_all(base, [Mutant.model_validate(m) for m in config["mutants"]])
    summary = summarize(rows)
    write_report(summary, rows)
    print(f"Bắt được {summary['real_caught']}/{summary['real_total']} • Đã ghi {RESULTS / 'mutation.md'}")


if __name__ == "__main__":
    main()
