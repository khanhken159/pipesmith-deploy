"""Chạy graph theo từng lần chạy (run_id = thread_id): bắt đầu, tạm dừng ở J1/J2/cứu hộ, chạy tiếp.

Dùng chung cho CLI và API. Trạng thái graph lưu bằng checkpointer SQLite; tóm tắt lưu trong store.
"""

import logging
import sqlite3
import time
from collections.abc import Callable
from functools import lru_cache

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from pydantic import BaseModel

from src.agents.graph import build_graph
from src.agents.progress import StepEvent, describe
from src.config import get_settings
from src.models.evidence import ReviewDecision
from src.models.schemas import RunStatus
from src.services.llm import LLMCallError, LLMConfigError
from src.services.store import get_store

logger = logging.getLogger(__name__)
EventCallback = Callable[[StepEvent], None]
INTERRUPT_STATUS = {
    "clarify": RunStatus.WAITING_CLARIFICATION,
    "plan": RunStatus.WAITING_PLAN,
    "rescue": RunStatus.WAITING_RESCUE,
    "review": RunStatus.WAITING_REVIEW,
}


class RunStateError(RuntimeError):
    """Lần chạy không ở đúng bước để thực hiện thao tác."""


class PermissionDeniedError(PermissionError):
    """Vai trò/người dùng không được phép thao tác."""


class RunOutcome(BaseModel):
    """Kết quả sau mỗi lần chạy/tiếp tục."""

    run_id: str
    status: RunStatus
    pending: dict | None = None
    error: str = ""


class ResumeRequest(BaseModel):
    """Tiếp tục một lần chạy đang chờ bước `kind` với dữ liệu `value`."""

    run_id: str
    kind: str
    value: dict


@lru_cache
def _graph(checkpoint_path: str) -> CompiledStateGraph:
    conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
    return build_graph(SqliteSaver(conn))


def get_graph() -> CompiledStateGraph:
    """Graph đã gắn checkpointer SQLite (mỗi tiến trình một kết nối)."""
    path = get_settings().checkpoint_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return _graph(str(path.resolve()))


def _config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}, "recursion_limit": 200}


def _stream(run_id: str, payload: object, on_event: EventCallback | None) -> str:
    """Chạy graph tới điểm dừng kế tiếp; trả về thông báo lỗi (rỗng nếu không lỗi)."""
    last = time.perf_counter()
    try:
        for chunk in get_graph().stream(payload, _config(run_id), stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    continue
                now = time.perf_counter()
                if on_event:
                    on_event(describe(node, update or {}, now - last))
                last = now
    except (LLMConfigError, LLMCallError) as exc:
        return str(exc)
    except Exception:  # ranh giới cuối: ghi log đầy đủ, chỉ trả thông báo thân thiện
        logger.exception("graph run failed", extra={"run_id": run_id})
        return "Có lỗi nội bộ khi chạy pipeline. Xem log để biết chi tiết."
    return ""


def get_values(run_id: str) -> dict:
    """State hiện tại của lần chạy (rỗng nếu chưa có)."""
    return dict(get_graph().get_state(_config(run_id)).values or {})


def pending_interrupt(run_id: str) -> dict | None:
    """Câu hỏi/bước đang chờ con người (None nếu không chờ)."""
    snapshot = get_graph().get_state(_config(run_id))
    return next((i.value for task in snapshot.tasks for i in task.interrupts), None)


def summarize(values: dict, error: str) -> dict:
    """Tóm tắt lưu vào store (hiển thị danh sách, API)."""
    usage = values.get("llm_usage", [])
    report = values.get("optimization") or {}
    return {
        "target": values.get("spec", {}).get("target"),
        "mode": values.get("spec", {}).get("mode"),
        "fix_attempts": values.get("fix_attempts", 0),
        "rescue_count": values.get("rescue_count", 0),
        "review_rounds": values.get("review_rounds", 0),
        "optimization": report.get("decision"),
        "improvement_pct": report.get("improvement_pct"),
        "llm_calls": len(usage),
        "tokens": sum(u.get("input_tokens", 0) + u.get("output_tokens", 0) for u in usage),
        "cost_usd": round(sum(u.get("cost_usd", 0.0) for u in usage), 6),
        "simulated": any(u.get("simulated") for u in usage),
        "workspace": values.get("workspace"),
        "error": error or values.get("error", ""),
    }


def _finish(run_id: str, error: str) -> RunOutcome:
    values, pending = get_values(run_id), pending_interrupt(run_id)
    if error:
        status = RunStatus.FAILED
    elif pending:
        status = INTERRUPT_STATUS.get(pending.get("kind"), RunStatus.RUNNING)
    else:
        status = RunStatus(values.get("status") or RunStatus.RUNNING)
    get_store().update_run(run_id, status, summarize(values, error))
    return RunOutcome(run_id=run_id, status=status, pending=pending, error=error or values.get("error", ""))


def create_run(request_text: str, requester: str) -> str:
    """Tạo bản ghi lần chạy (chưa chạy graph); API dùng để trả run_id ngay rồi chạy nền."""
    return get_store().create_run(request_text, requester).id


def run_created(run_id: str, on_event: EventCallback | None = None) -> RunOutcome:
    """Chạy một lần chạy vừa tạo tới điểm dừng đầu tiên."""
    record = get_store().get_run(run_id)
    if record is None:
        raise RunStateError(f"Không tìm thấy lần chạy {run_id}.")
    payload = {"run_id": run_id, "request_text": record.request_text, "requester": record.requester, "llm_usage": []}
    return _finish(run_id, _stream(run_id, payload, on_event))


def start_run(request_text: str, requester: str, on_event: EventCallback | None = None) -> RunOutcome:
    """Tạo lần chạy mới và chạy tới điểm dừng đầu tiên."""
    return run_created(create_run(request_text, requester), on_event)


def check_resumable(run_id: str, kind: str) -> dict:
    """Lần chạy phải đang chờ đúng bước `kind`; trả về nội dung đang chờ."""
    pending = pending_interrupt(run_id)
    if not pending or pending.get("kind") != kind:
        raise RunStateError(f"Lần chạy {run_id} không ở bước chờ '{kind}'.")
    return pending


def resume_run(request: ResumeRequest, on_event: EventCallback | None = None) -> RunOutcome:
    """Tiếp tục khi đúng bước đang chờ."""
    check_resumable(request.run_id, request.kind)
    get_store().update_run(request.run_id, RunStatus.RUNNING)
    return _finish(request.run_id, _stream(request.run_id, Command(resume=request.value), on_event))


def review_permission_error(role: str, reviewer: str, requester: str) -> str:
    """Luật duyệt J2 (dùng chung cho CLI và API); chuỗi rỗng = được phép.

    Mặc định một vai trò DE: người tạo yêu cầu tự xem bằng chứng và duyệt. REQUIRE_SEPARATE_REVIEWER=true:
    chỉ vai trò reviewer được duyệt và phải khác người tạo yêu cầu.
    """
    if not get_settings().require_separate_reviewer:
        return ""
    if role != "reviewer":
        return "Chỉ vai trò Reviewer mới được duyệt hoặc từ chối (đang bật REQUIRE_SEPARATE_REVIEWER)."
    if reviewer.strip().lower() == requester.strip().lower():
        return "Người tạo yêu cầu không được tự duyệt (đang bật REQUIRE_SEPARATE_REVIEWER)."
    return ""


def check_review(decision: ReviewDecision, role: str) -> None:
    """Kiểm tra trước khi duyệt: lần chạy tồn tại, đúng quyền, đang chờ duyệt (lỗi → ngoại lệ)."""
    record = get_store().get_run(decision.run_id)
    if record is None:
        raise RunStateError(f"Không tìm thấy lần chạy {decision.run_id}.")
    problem = review_permission_error(role, decision.reviewer, record.requester)
    if problem:
        raise PermissionDeniedError(problem)
    check_resumable(decision.run_id, "review")


def submit_review(decision: ReviewDecision, role: str, on_event: EventCallback | None = None) -> RunOutcome:
    """J2: duyệt hoặc từ chối theo luật ở `review_permission_error`."""
    check_review(decision, role)
    value = decision.model_dump(exclude={"run_id"})
    outcome = resume_run(ResumeRequest(run_id=decision.run_id, kind="review", value=value), on_event)
    get_store().add_review(decision)
    return outcome
