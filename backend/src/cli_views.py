"""Hiển thị trong terminal (rich): tiến trình, câu hỏi làm rõ, gói duyệt, danh sách lần chạy."""

import difflib

import sqlglot
from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.syntax import Syntax
from rich.table import Table

from src.agents.progress import StepEvent
from src.agents.tools.sql_tools import DIALECT
from src.models.evidence import ErrorEntry
from src.models.schemas import RunRecord
from src.services.doctor import CheckResult

console = Console(highlight=False)
LEVEL_STYLE = {"ok": "[green]✓[/]", "warn": "[yellow]![/]", "fail": "[red]✗[/]", "info": "[cyan]i[/]"}
STATUS_TEXT = {
    "running": "đang chạy",
    "waiting_clarification": "chờ trả lời câu hỏi làm rõ",
    "waiting_plan_review": "chờ duyệt kế hoạch",
    "waiting_rescue": "chờ cứu hộ",
    "waiting_review": "chờ Reviewer duyệt",
    "approved": "đã duyệt",
    "failed": "dừng do lỗi",
}


def simulated_banner() -> None:
    """Nhãn bắt buộc khi chạy bằng LLM giả."""
    console.print(
        Panel(
            "[bold yellow]Chế độ mô phỏng[/]: LLM_PROVIDER=mock — câu trả lời LLM là cố định, "
            "không phản ánh chất lượng mô hình thật.",
            border_style="yellow",
        )
    )


def print_event(event: StepEvent) -> None:
    """Một dòng tiến trình: ✓/✗, tên bước, thời gian, token, chi tiết."""
    mark = "[green]✓[/]" if event.ok else "[red]✗[/]"
    tokens = f"{event.tokens} tok" if event.tokens else ""
    console.print(f" {mark} {event.label:<20} [dim]{event.seconds:>6.2f}s {tokens:>9}[/]  {event.detail}")


def ask_clarification(pending: dict) -> dict[str, str]:
    """Hỏi từng câu, người dùng chọn số thứ tự đáp án."""
    console.print(
        Panel(
            "Agent cần bạn làm rõ trước khi viết code:\n- " + "\n- ".join(pending.get("unknowns", [])),
            title="J1 Hỏi làm rõ",
            border_style="cyan",
        )
    )
    answers = {}
    for question in pending.get("questions", []):
        console.print(f"\n[bold]{question['question']}[/]")
        for index, option in enumerate(question["options"], start=1):
            console.print(f"  {index}. {option}")
        choice = IntPrompt.ask("Chọn số", choices=[str(i) for i in range(1, len(question["options"]) + 1)])
        answers[question["id"]] = question["options"][choice - 1]
    return answers


def show_plan(pending: dict) -> None:
    """In kế hoạch có giải thích (J1b) để DE đọc trước khi agent sinh code."""
    spec = pending.get("spec", {})
    console.print(
        Panel(pending.get("summary", ""), title="J1b Kế hoạch của agent (LLM lập — bạn duyệt)", border_style="cyan")
    )
    table = Table(show_lines=True)
    for header in ("#", "Bước", "Làm gì", "Vì sao"):
        table.add_column(header)
    for index, step in enumerate(pending.get("steps", []), start=1):
        table.add_row(str(index), step.get("title", ""), step.get("detail", ""), step.get("reason", ""))
    console.print(table)
    console.print(
        f"Bảng đích: [bold]{spec.get('target')}[/] • mỗi dòng là: {', '.join(spec.get('grain') or [])} • "
        f"{spec.get('mode')} ({spec.get('mode_reason')})"
    )
    console.print(f"[dim]{pending.get('next_steps', '')}[/]")


def ask_plan(pending: dict) -> dict:
    """Đồng ý kế hoạch, hoặc ghi chú để agent lập lại."""
    show_plan(pending)
    choice = Prompt.ask("Kế hoạch này ổn chưa?", choices=["approve", "revise"], default="approve")
    if choice == "approve":
        return {"decision": "approve"}
    return {"decision": "revise", "note": Prompt.ask("Cần sửa gì (agent sẽ lập lại kế hoạch)")}


def ask_rescue(pending: dict) -> dict:
    """Cứu hộ: nhập gợi ý cho agent hoặc dừng."""
    console.print(
        Panel(
            pending.get("error", "")[:1500],
            title=f"Cứu hộ sau {pending.get('fix_attempts')} lần sửa",
            border_style="red",
        )
    )
    hint = Prompt.ask("Gợi ý cho agent (để trống = dừng lần chạy)", default="")
    return {"action": "retry", "hint": hint} if hint.strip() else {"action": "abort"}


def print_runs(records: list[RunRecord]) -> None:
    """Bảng các lần chạy gần đây."""
    table = Table(title="Các lần chạy gần đây")
    for column in ("ID", "Trạng thái", "Người tạo", "Bảng đích", "Tối ưu", "Provider", "Yêu cầu"):
        table.add_column(column)
    for r in records:
        table.add_row(
            r.id,
            STATUS_TEXT.get(r.status, r.status),
            r.requester,
            str(r.summary.get("target") or "—"),
            str(r.summary.get("optimization") or "—"),
            r.provider,
            r.request_text[:50],
        )
    console.print(table)


def print_run(record: RunRecord) -> None:
    """Chi tiết một lần chạy."""
    s = record.summary
    lines = [
        f"Yêu cầu: {record.request_text}",
        f"Người tạo: {record.requester}",
        f"Trạng thái: [bold]{STATUS_TEXT.get(record.status, record.status)}[/]",
        f"Bảng đích: {s.get('target') or '—'} ({s.get('mode') or '—'})",
        f"Vòng sửa: {s.get('fix_attempts', 0)} • cứu hộ: {s.get('rescue_count', 0)} • bị từ chối: {s.get('review_rounds', 0)}",
        f"Tối ưu: {s.get('optimization') or '—'} ({s.get('improvement_pct') if s.get('improvement_pct') is not None else '—'}%)",
        f"LLM: {record.provider}/{record.model} • {s.get('llm_calls', 0)} lần gọi • {s.get('tokens', 0)} token • "
        f"{s.get('cost_usd', 0)} USD" + (" [yellow](mô phỏng)[/]" if s.get("simulated") else ""),
        f"Workspace: {s.get('workspace') or '—'}",
    ]
    if s.get("error"):
        lines.append(f"[red]Lỗi: {s['error']}[/]")
    console.print(Panel("\n".join(lines), title=f"Lần chạy {record.id}"))


def print_doctor(results: list[CheckResult]) -> None:
    """Kết quả kiểm tra môi trường."""
    for r in results:
        console.print(f" {LEVEL_STYLE[r.level]} [bold]{r.name:<16}[/] {r.message}")
    fails = [r for r in results if r.level == "fail"]
    console.print(
        "\n[green]Môi trường sẵn sàng cho giai đoạn A.[/]"
        if not fails
        else f"\n[red]{len(fails)} mục cần sửa trước khi chạy.[/]"
    )


def print_errors(entries: list[ErrorEntry]) -> None:
    """Các mục sổ lỗi chờ duyệt."""
    table = Table(title="Sổ lỗi chờ Reviewer duyệt")
    for column in ("ID", "Mã", "Số lần", "Mô tả"):
        table.add_column(column)
    for e in entries:
        table.add_row(str(e.id), e.code, str(e.occurrences), e.description[:90])
    console.print(table if entries else "[green]Không có mục nào chờ duyệt.[/]")


def print_diff(before: dict[str, str], after: dict[str, str]) -> None:
    """Diff có màu giữa hai bộ file (file mới so với rỗng)."""
    for path in sorted(set(before) | set(after)):
        old, new = before.get(path, ""), after.get(path, "")
        if old == new:
            continue
        diff = difflib.unified_diff(old.splitlines(), new.splitlines(), f"a/{path}", f"b/{path}", lineterm="")
        console.print(Syntax("\n".join(diff), "diff", theme="ansi_dark", word_wrap=True))


def _spec_panel(values: dict) -> Panel:
    spec = values.get("spec", {})
    lines = [
        f"Yêu cầu: {values.get('request_text')}  [dim](người tạo: {values.get('requester')})[/]",
        f"Bảng đích: [bold]{spec.get('target')}[/] • grain: {', '.join(spec.get('grain', []))}",
        f"Chế độ: [bold]{spec.get('mode')}[/] — {spec.get('mode_reason')}",
        "Đã làm rõ: " + ("; ".join(spec.get("assumptions", [])) or "—"),
    ]
    return Panel("\n".join(lines), title="Đặc tả (kế hoạch bằng lời)")


def _evidence_table(evidence: dict) -> Table:
    table = Table(title="Bằng chứng", show_lines=True)
    table.add_column("Code đo (measured)", ratio=3)
    table.add_column("LLM nói (claimed, chưa kiểm chứng)", ratio=2)
    measured = [
        f"{'[green]✓[/] ' if m['passed'] else '[red]✗[/] ' if m['passed'] is False else ''}"
        f"[dim]{m['node']}[/] {m['check']}: {m['result']}"
        for m in evidence.get("measured", [])
    ]
    claimed = evidence.get("claimed", [])
    for index in range(max(len(measured), len(claimed))):
        table.add_row(measured[index] if index < len(measured) else "", claimed[index] if index < len(claimed) else "")
    return table


def _sample_table(sandbox: dict) -> Table:
    rows = sandbox.get("sample", [])
    table = Table(title=f"Kết quả mẫu ({sandbox.get('target_rows', 0)} dòng, hiển thị {len(rows)})")
    for column in rows[0] if rows else []:
        table.add_column(column)
    for row in rows:
        table.add_row(*row.values())
    return table


def print_optimization(report: dict) -> None:
    """Báo cáo tối ưu: phát hiện, số đo trước/sau, quyết định, diff SQL."""
    if not report:
        return
    before, after = report.get("before") or {}, report.get("after") or {}
    lines = [
        "Dấu hiệu: " + ("; ".join(f["message"] for f in report.get("findings", [])) or "—"),
        f"Trung vị trên bộ large: {before.get('median_ms', '—')} ms → {after.get('median_ms', '—')} ms",
        f"Quyết định: [bold]{report.get('decision')}[/] — {report.get('reason')}",
    ]
    lines += [f"[dim]Gợi ý cho kho khác (không thực thi): {h}[/]" for h in report.get("warehouse_hints", [])]
    console.print(Panel("\n".join(lines), title="Báo cáo tối ưu (E4 + V3)"))
    if report.get("proposed_sql") and report.get("proposed_sql") != report.get("original_sql"):
        print_diff({"query.sql": _pretty(report["original_sql"])}, {"query.sql": _pretty(report["proposed_sql"])})


def _pretty(sql: str) -> str:
    """Chuẩn hóa định dạng hai bản SQL trước khi so để diff chỉ còn khác biệt thật."""
    try:
        return sqlglot.transpile(sql, read=DIALECT, write=DIALECT, pretty=True)[0]
    except sqlglot.errors.ParseError:
        return sql


def print_review_package(values: dict, full: bool = False) -> None:
    """Toàn bộ gói duyệt cho Reviewer."""
    console.print(_spec_panel(values))
    console.print(_evidence_table(values.get("evidence", {})))
    console.print(_sample_table(values.get("sandbox", {})))
    print_optimization(values.get("optimization", {}))
    current = {**values.get("code_files", {}), **values.get("test_files", {})}
    previous = values.get("previous_files", {})
    console.rule("Thay đổi code" + (" so với vòng trước" if previous else " (file mới)"))
    if previous or full:
        print_diff(previous, current)
    else:
        for path, content in sorted(current.items()):
            console.print(f"[bold]{path}[/] [dim]({len(content.splitlines())} dòng)[/]")
        console.print("[dim]Thêm --full để xem toàn bộ nội dung file.[/]")
