"""Xử lý từng lệnh CLI. Mỗi hàm trả mã thoát (0 = thành công)."""

import argparse
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from rich.prompt import Prompt

from src.agents import runner
from src.agents.runner import PermissionDeniedError, ResumeRequest, RunOutcome, RunStateError
from src.agents.tools.duckdb_tools import discover_sources
from src.cli_views import (
    STATUS_TEXT,
    ask_clarification,
    ask_plan,
    ask_rescue,
    console,
    print_doctor,
    print_errors,
    print_event,
    print_optimization,
    print_review_package,
    print_run,
    print_runs,
    show_plan,
    simulated_banner,
)
from src.config import get_settings
from src.models.evidence import ReviewDecision
from src.services.doctor import run_checks
from src.services.error_memory import get_error_memory
from src.services.llm import LLMCallError, LLMConfigError
from src.services.seed import SeedConfig, generate_sources
from src.services.store import get_store

AUTO_REVIEWER = "auto-reviewer"


def cmd_doctor(args: argparse.Namespace) -> int:
    """Kiểm tra môi trường."""
    results = run_checks()
    print_doctor(results)
    return 1 if any(r.level == "fail" for r in results) else 0


def cmd_seed(args: argparse.Namespace) -> int:
    """Sinh dữ liệu giả lập."""
    settings = get_settings()
    cfg = SeedConfig(
        out_dir=settings.sources_dir,
        seed=settings.seed,
        dirty=args.dirty,
        rows_per_source=args.rows,
        profile=args.profile,
        scale=args.scale,
    )
    for name, count in generate_sources(cfg).items():
        console.print(f" [green]✓[/] {settings.sources_dir / name}" + (f": {count} dòng" if count >= 0 else ""))
    tables = len(discover_sources(settings.sources_dir))
    console.print(
        f"Tổng cộng {tables} bảng nguồn. Xem cấu trúc: màn 'Dữ liệu nguồn' trên web hoặc docs/data-catalog.md"
    )
    return 0


def _auto_review(outcome: RunOutcome) -> RunOutcome:
    console.print("[yellow]--auto-approve: tự duyệt (chỉ dùng cho test/eval).[/]")
    decision = ReviewDecision(run_id=outcome.run_id, reviewer=AUTO_REVIEWER, decision="approve", note="auto")
    return runner.submit_review(decision, "reviewer", print_event)


def _step(outcome: RunOutcome, args: argparse.Namespace) -> RunOutcome | None:
    """Xử lý một điểm dừng; trả None khi cần dừng vòng lặp."""
    kind = (outcome.pending or {}).get("kind")
    auto = getattr(args, "auto_answer", False) or getattr(args, "auto_approve", False)
    if kind == "clarify":
        answers = (
            {q["id"]: q["options"][0] for q in outcome.pending["questions"]}
            if auto
            else ask_clarification(outcome.pending)
        )
        return runner.resume_run(
            ResumeRequest(run_id=outcome.run_id, kind="clarify", value={"answers": answers}), print_event
        )
    if kind == "plan":
        if auto:
            show_plan(outcome.pending)
        value = {"decision": "approve"} if auto else ask_plan(outcome.pending)
        return runner.resume_run(ResumeRequest(run_id=outcome.run_id, kind="plan", value=value), print_event)
    if kind == "rescue":
        value = {"action": "abort"} if auto else ask_rescue(outcome.pending)
        return runner.resume_run(ResumeRequest(run_id=outcome.run_id, kind="rescue", value=value), print_event)
    if kind == "review" and getattr(args, "auto_approve", False):
        return _auto_review(outcome)
    return None


def _drive(outcome: RunOutcome, args: argparse.Namespace) -> int:
    while outcome.pending:
        next_outcome = _step(outcome, args)
        if next_outcome is None:
            break
        outcome = next_outcome
    console.print(
        f"\n[bold]Trạng thái:[/] {STATUS_TEXT.get(outcome.status, outcome.status)} (run_id: {outcome.run_id})"
    )
    if outcome.error:
        console.print(f"[red]{outcome.error}[/]")
    if outcome.status == "waiting_review":
        who = " --as reviewer --user <tên>" if get_settings().require_separate_reviewer else ""
        console.print(f"Xem bằng chứng và duyệt: [bold]python -m src.cli review {outcome.run_id}{who}[/]")
    return 1 if outcome.status == "failed" else 0


def cmd_run(args: argparse.Namespace) -> int:
    """Chạy luồng từ đầu, hỏi J1 ngay trong terminal."""
    if get_settings().require_separate_reviewer and args.role == "reviewer":
        console.print("[red]Vai trò Reviewer không tạo yêu cầu (--as engineer).[/]")
        return 2
    if get_settings().is_mock:
        simulated_banner()
    try:
        return _drive(runner.start_run(args.request, args.user, print_event), args)
    except (LLMConfigError, LLMCallError, RunStateError, PermissionDeniedError) as exc:
        console.print(f"[red]{exc}[/]")
        return 1


def cmd_answer(args: argparse.Namespace) -> int:
    """Trả lời câu hỏi làm rõ cho lần chạy đang chờ J1."""
    pending = runner.pending_interrupt(args.run_id)
    if not pending or pending.get("kind") != "clarify":
        console.print("[red]Lần chạy này không chờ câu trả lời làm rõ.[/]")
        return 1
    outcome = runner.resume_run(
        ResumeRequest(run_id=args.run_id, kind="clarify", value={"answers": ask_clarification(pending)}), print_event
    )
    return _drive(outcome, args)


def _review_choice(args: argparse.Namespace) -> tuple[str, str]:
    if args.approve or args.reject:
        return ("approve" if args.approve else "reject"), args.note
    choice = Prompt.ask("Quyết định", choices=["approve", "reject", "skip"], default="skip")
    note = Prompt.ask("Ghi chú cho Coder (bắt buộc khi từ chối)") if choice == "reject" else ""
    return choice, note


def _check_reviewer(args: argparse.Namespace) -> str:
    record = get_store().get_run(args.run_id)
    if record is None:
        return f"Không tìm thấy lần chạy {args.run_id}."
    return runner.review_permission_error(args.role, args.user, record.requester)


def _resolve_run_id(run_id: str) -> str:
    """`latest` = lần chạy mới nhất đang chờ duyệt."""
    if run_id != "latest":
        return run_id
    waiting = [r for r in get_store().list_runs(50) if r.status == "waiting_review"]
    return waiting[0].id if waiting else run_id


def cmd_review(args: argparse.Namespace) -> int:
    """Hiện gói duyệt rồi approve/reject (`run_id` có thể là `latest`)."""
    args.run_id = _resolve_run_id(args.run_id)
    problem = _check_reviewer(args)
    if problem:
        console.print(f"[red]{problem}[/]")
        return 2
    print_review_package(runner.get_values(args.run_id), full=args.full)
    if (runner.pending_interrupt(args.run_id) or {}).get("kind") != "review":
        console.print("[yellow]Lần chạy này không ở bước chờ duyệt.[/]")
        return 1
    decision, note = _review_choice(args)
    if decision == "skip":
        return 0
    try:
        review = ReviewDecision(run_id=args.run_id, reviewer=args.user, decision=decision, note=note)
        return _drive(runner.submit_review(review, args.role, print_event), args)
    except (PermissionDeniedError, RunStateError, LLMConfigError, LLMCallError) as exc:
        console.print(f"[red]{exc}[/]")
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Danh sách lần chạy hoặc chi tiết một lần."""
    store = get_store()
    if not args.run_id:
        print_runs(store.list_runs())
        return 0
    record = store.get_run(args.run_id)
    if record is None:
        console.print(f"[red]Không tìm thấy lần chạy {args.run_id}.[/]")
        return 1
    print_run(record)
    return 0


def cmd_errors(args: argparse.Namespace) -> int:
    """Sổ lỗi: liệt kê, duyệt, bỏ (bật REQUIRE_SEPARATE_REVIEWER thì chỉ Reviewer được duyệt/bỏ)."""
    memory = get_error_memory()
    separate = get_settings().require_separate_reviewer
    if (args.approve or args.discard) and separate and args.role != "reviewer":
        console.print("[red]Chỉ Reviewer được duyệt hoặc bỏ mục sổ lỗi (đang bật REQUIRE_SEPARATE_REVIEWER).[/]")
        return 2
    if args.approve:
        ok = memory.approve(args.approve, args.fix)
        console.print(f"[green]Đã duyệt mục {args.approve}.[/]" if ok else "[red]Không có mục này.[/]")
    elif args.discard:
        ok = memory.discard(args.discard)
        console.print(f"[green]Đã bỏ mục {args.discard}.[/]" if ok else "[red]Không có mục này.[/]")
    print_errors(memory.pending())
    return 0


def _datasets_for(run_id: str | None) -> dict[str, str]:
    runs = [get_store().get_run(run_id)] if run_id else get_store().list_runs(50)
    for record in runs:
        folder = Path(record.summary.get("workspace") or "") / "datasets" if record else None
        if folder and folder.exists():
            return {p.stem: str(p) for p in folder.glob("*.duckdb")}
    return {}


def cmd_optimize(args: argparse.Namespace) -> int:
    """Chạy riêng E4 + V3 trên bộ dữ liệu thử của một lần chạy."""
    from src.agents.nodes.optimizer import OptimizeJob, optimize_standalone
    from src.agents.tools.sql_tools import SqlCheckError

    datasets = _datasets_for(args.run_id)
    if args.dataset not in datasets:
        console.print("[red]Chưa có bộ dữ liệu thử. Chạy `run` một lần trước (hoặc chỉ định --run).[/]")
        return 1
    if get_settings().is_mock:
        simulated_banner()
    try:
        job = OptimizeJob(
            sql=args.sql.read_text(encoding="utf-8").strip().rstrip(";"), datasets=datasets, bench=args.dataset
        )
        report, _ = optimize_standalone(job)
    except (OSError, SqlCheckError, LLMConfigError, LLMCallError) as exc:
        console.print(f"[red]{exc}[/]")
        return 1
    print_optimization(report.model_dump())
    for check in report.equivalence:
        console.print(f" {'[green]✓[/]' if check.equal else '[red]✗[/]'} {check.dataset}: {check.detail}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Chạy eval/run_eval.py (tiến trình con, cùng provider đã chọn)."""
    script = Path(__file__).resolve().parents[1] / "eval" / "run_eval.py"
    command = [sys.executable, str(script), *(["--with-llm"] if args.with_llm else [])]
    if args.with_llm and get_settings().is_mock:
        simulated_banner()
    return subprocess.run(command, cwd=script.parents[1], check=False).returncode


COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "doctor": cmd_doctor,
    "seed": cmd_seed,
    "run": cmd_run,
    "answer": cmd_answer,
    "review": cmd_review,
    "status": cmd_status,
    "errors": cmd_errors,
    "optimize": cmd_optimize,
    "eval": cmd_eval,
}
