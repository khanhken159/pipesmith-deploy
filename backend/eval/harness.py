"""Phần dùng chung khi đánh giá: lái một lần chạy qua các điểm dừng của con người (CHỈ dùng cho eval).

- J1 hỏi làm rõ: chọn lựa chọn chứa từ khóa ưu tiên (nếu có), không thì lựa chọn đầu; đếm lại số câu đã tự trả lời.
- Cứu hộ: dừng (eval không có người gợi ý).
- J2 duyệt: tự duyệt bằng tài khoản reviewer riêng của eval (khác người tạo yêu cầu).
"""

import os
import sys
import time
from pathlib import Path

import duckdb
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agents import runner  # noqa: E402
from src.agents.runner import ResumeRequest, RunOutcome  # noqa: E402
from src.config import get_settings  # noqa: E402
from src.models.evidence import ReviewDecision  # noqa: E402

EVAL_USER, EVAL_REVIEWER = "eval-engineer", "eval-auto-reviewer"


class AutoRun(BaseModel):
    """Kết quả một lần chạy tự động."""

    run_id: str
    status: str
    error: str
    questions_asked: int
    seconds: float


def _choose(question: dict, prefer: list[str]) -> str:
    for option in question["options"]:
        if any(word.lower() in option.lower() for word in prefer):
            return option
    return question["options"][0]


def _resume_value(pending: dict, prefer: list[str]) -> dict:
    if pending["kind"] == "clarify":
        return {"answers": {q["id"]: _choose(q, prefer) for q in pending["questions"]}}
    if pending["kind"] == "plan":
        return {"decision": "approve"}  # J1b: eval tự đồng ý kế hoạch
    return {"action": "abort"}  # cứu hộ: eval không có người gợi ý


def drive(outcome: RunOutcome, prefer: list[str]) -> tuple[RunOutcome, int]:
    """Đi qua các điểm dừng tới khi xong; trả về (kết quả cuối, số câu J1 đã tự trả lời)."""
    asked = 0
    while outcome.pending:
        if outcome.pending["kind"] == "review":
            decision = ReviewDecision(run_id=outcome.run_id, reviewer=EVAL_REVIEWER, decision="approve", note="eval")
            return runner.submit_review(decision, "reviewer"), asked
        if outcome.pending["kind"] == "clarify":
            asked += len(outcome.pending["questions"])
        value = _resume_value(outcome.pending, prefer)
        outcome = runner.resume_run(ResumeRequest(run_id=outcome.run_id, kind=outcome.pending["kind"], value=value))
    return outcome, asked


def run_request(request: str, sources_dir: Path, prefer: list[str] | None = None) -> AutoRun:
    """Một lần chạy trọn luồng trên thư mục nguồn cho trước."""
    os.environ["SOURCES_DIR"] = str(sources_dir)
    get_settings.cache_clear()
    start = time.perf_counter()
    outcome, asked = drive(runner.start_run(request, EVAL_USER), prefer or [])
    return AutoRun(
        run_id=outcome.run_id,
        status=str(outcome.status),
        error=outcome.error or "",
        questions_asked=asked,
        seconds=round(time.perf_counter() - start, 1),
    )


def usage_totals(values: dict) -> tuple[int, float]:
    """(tổng token, tổng chi phí USD) của một lần chạy."""
    usage = values.get("llm_usage", [])
    tokens = sum(u.get("input_tokens", 0) + u.get("output_tokens", 0) for u in usage)
    return tokens, round(sum(u.get("cost_usd", 0.0) for u in usage), 6)


def target_result(values: dict) -> tuple[list[str], list[tuple]]:
    """Cột và dòng của bảng đích trong sandbox của lần chạy."""
    target = values.get("spec", {}).get("target", "")
    with duckdb.connect(str(Path(values["workspace"]) / "sandbox.duckdb"), read_only=True) as con:
        rel = con.sql(f'SELECT * FROM main."{target}"')
        return rel.columns, rel.fetchall()
