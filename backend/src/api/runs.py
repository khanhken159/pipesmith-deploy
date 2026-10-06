"""Lần chạy: tạo (chạy nền), xem tiến trình/chi tiết/file, tải gói code, trả lời J1, duyệt kế hoạch J1b, cứu hộ.

Thao tác làm graph chạy tiếp trả về 202 ngay; web hỏi `GET /runs/{id}` định kỳ để thấy tiến trình.
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.agents import runner
from src.agents.nodes.clarify import valid_answers
from src.agents.runner import ResumeRequest, RunStateError
from src.api.deps import CurrentUser, current_user, run_or_404
from src.api.requests import Accepted, AnswerBody, CreateRunBody, PlanBody, RescueBody, RunDetail, RunFiles
from src.models.schemas import RunRecord
from src.models.spec import ClarifyQuestion
from src.services.export import export_zip
from src.services.jobs import get_jobs
from src.services.store import get_store

router = APIRouter(prefix="/runs", tags=["runs"])
SPEC_FIELDS = (
    "target", "mode", "mode_reason", "grain", "output_columns", "metrics", "filters", "assumptions", "plan_summary", "plan",
)  # fmt: skip


@router.get("", response_model=list[RunRecord])
async def list_runs(limit: int = Query(default=20, ge=1, le=100)) -> list[RunRecord]:
    """Danh sách lần chạy mới nhất."""
    return get_store().list_runs(limit)


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=Accepted)
def create_run(body: CreateRunBody, user: Annotated[CurrentUser, Depends(current_user)]) -> Accepted:
    """Tạo yêu cầu mới; agent chạy nền tới điểm dừng đầu tiên (câu hỏi làm rõ hoặc bản duyệt)."""
    run_id = runner.create_run(body.request_text.strip(), user.name)
    get_jobs().submit(run_id, lambda sink: runner.run_created(run_id, sink))
    return Accepted(run_id=run_id, status="running", message="Đã nhận yêu cầu, agent đang chạy.")


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: str) -> RunDetail:
    """Trạng thái, câu hỏi đang chờ, tiến trình từng bước, đặc tả, bằng chứng, báo cáo tối ưu."""
    record = run_or_404(run_id)
    jobs = get_jobs()
    values = runner.get_values(run_id)
    spec = values.get("spec", {})
    return RunDetail(
        record=record,
        busy=jobs.busy(run_id),
        pending=None if jobs.busy(run_id) else runner.pending_interrupt(run_id),
        events=jobs.events(run_id),
        spec={k: spec.get(k) for k in SPEC_FIELDS},
        answered=values.get("answered", []),
        evidence=values.get("evidence", {}),
        optimization=values.get("optimization", {}),
        sandbox=values.get("sandbox", {}),
        code_notes=values.get("code_notes", []),
        test_notes=values.get("test_notes", []),
    )


@router.get("/{run_id}/files", response_model=RunFiles)
def get_files(run_id: str) -> RunFiles:
    """Code + test hiện tại và bộ file vòng trước (để xem diff)."""
    run_or_404(run_id)
    values = runner.get_values(run_id)
    return RunFiles(
        code_files=values.get("code_files", {}),
        test_files=values.get("test_files", {}),
        previous_files=values.get("previous_files", {}),
    )


@router.get("/{run_id}/download", response_class=Response)
def download(run_id: str) -> Response:
    """Gói zip code dbt + test + DAG (không kèm dữ liệu sandbox) để DE đưa vào repo và mở PR."""
    run_or_404(run_id)
    workspace = runner.get_values(run_id).get("workspace")
    if not workspace or not Path(workspace).exists():
        raise HTTPException(status_code=409, detail="Lần chạy chưa sinh code nên chưa có gì để tải.")
    name = f"p113-{run_id}"
    headers = {"Content-Disposition": f'attachment; filename="{name}.zip"'}
    return Response(export_zip(Path(workspace), name), media_type="application/zip", headers=headers)


def _pending(run_id: str, kind: str) -> dict:
    """Lần chạy phải rảnh và đang chờ đúng bước; nếu không → 409."""
    if get_jobs().busy(run_id):
        raise HTTPException(status_code=409, detail="Lần chạy đang chạy, vui lòng đợi.")
    try:
        return runner.check_resumable(run_id, kind)
    except RunStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _resume(run_id: str, kind: str, value: dict) -> Accepted:
    request = ResumeRequest(run_id=run_id, kind=kind, value=value)
    get_jobs().submit(run_id, lambda sink: runner.resume_run(request, sink))
    return Accepted(run_id=run_id, status="running", message="Đã nhận, agent chạy tiếp.")


@router.post("/{run_id}/answers", status_code=status.HTTP_202_ACCEPTED, response_model=Accepted)
def answer(run_id: str, body: AnswerBody) -> Accepted:
    """Trả lời câu hỏi làm rõ (J1); lựa chọn phải đúng một trong các đáp án đã đưa ra."""
    run_or_404(run_id)
    questions = [ClarifyQuestion.model_validate(q) for q in _pending(run_id, "clarify").get("questions", [])]
    answers = valid_answers(questions, {"answers": body.answers})
    if len(answers) != len(questions):
        raise HTTPException(status_code=422, detail="Cần chọn đúng một đáp án có sẵn cho mỗi câu hỏi.")
    return _resume(run_id, "clarify", {"answers": answers})


@router.post("/{run_id}/plan", status_code=status.HTTP_202_ACCEPTED, response_model=Accepted)
def review_plan(run_id: str, body: PlanBody) -> Accepted:
    """Duyệt kế hoạch (J1b): đồng ý → agent sinh code; sửa (kèm ghi chú) → agent lập lại kế hoạch."""
    run_or_404(run_id)
    _pending(run_id, "plan")
    if body.decision == "revise" and not body.note.strip():
        raise HTTPException(status_code=422, detail="Yêu cầu sửa kế hoạch thì cần ghi chú cần sửa gì.")
    return _resume(run_id, "plan", {"decision": body.decision, "note": body.note.strip()})


@router.post("/{run_id}/rescue", status_code=status.HTTP_202_ACCEPTED, response_model=Accepted)
def rescue(run_id: str, body: RescueBody) -> Accepted:
    """Cứu hộ khi agent sửa không được: gợi ý rồi thử lại, hoặc dừng."""
    run_or_404(run_id)
    _pending(run_id, "rescue")
    if body.action == "retry" and not body.hint.strip():
        raise HTTPException(status_code=422, detail="Hãy nhập gợi ý cho agent trước khi thử lại.")
    return _resume(run_id, "rescue", body.model_dump())
