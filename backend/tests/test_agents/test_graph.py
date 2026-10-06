"""Test graph end-to-end bằng mock: J1 → J1b → sinh code → V1/V2 → E4/V3 → J2 (duyệt, từ chối, cứu hộ, quyền)."""

import pytest

from src.agents import runner
from src.agents.graph import NODES, build_graph
from src.agents.runner import PermissionDeniedError, ResumeRequest, RunStateError
from src.models.evidence import ReviewDecision
from src.services.store import get_store


def _answer_only(outcome: runner.RunOutcome) -> runner.RunOutcome:
    answers = {q["id"]: q["options"][0] for q in outcome.pending["questions"]}
    return runner.resume_run(ResumeRequest(run_id=outcome.run_id, kind="clarify", value={"answers": answers}))


def _answer_first(outcome: runner.RunOutcome) -> runner.RunOutcome:
    """Trả lời J1 bằng lựa chọn đầu rồi đồng ý kế hoạch J1b."""
    outcome = _answer_only(outcome)
    assert outcome.status == "waiting_plan_review", outcome.error
    return runner.resume_run(ResumeRequest(run_id=outcome.run_id, kind="plan", value={"decision": "approve"}))


@pytest.fixture(scope="module")
def waiting_review(built_state) -> runner.RunOutcome:
    """Một lần chạy đi hết tới J2 (dùng chung trong module)."""
    outcome = runner.start_run("Gộp đơn hàng 3 nguồn, tính doanh thu ngày", "alice")
    assert outcome.status == "waiting_clarification"
    outcome = _answer_first(outcome)
    assert outcome.status == "waiting_review", outcome.error
    return outcome


def test_graph_compiles_with_all_nodes():
    graph = build_graph()
    assert set(NODES) <= set(graph.get_graph().nodes)


@pytest.mark.slow
def test_full_run_reaches_review_with_evidence(waiting_review: runner.RunOutcome):
    values = runner.get_values(waiting_review.run_id)
    assert values["sandbox"]["passed"] and values["safety"]["passed"]
    assert values["optimization"]["decision"] in ("applied", "skipped")
    assert values["evidence"]["measured"] and values["evidence"]["claimed"]
    record = get_store().get_run(waiting_review.run_id)
    assert record.summary["target"] == "fct_daily_revenue" and record.summary["simulated"] is True


@pytest.mark.slow
def test_clarify_keeps_question_text_for_planner(waiting_review: runner.RunOutcome):
    """Planner phải thấy cả câu hỏi lẫn câu trả lời; chỉ có mã `q1` thì LLM thật hỏi lặp mãi."""
    answered = runner.get_values(waiting_review.run_id)["answered"]
    assert len(answered) == 2
    assert all(item["question"].endswith("?") and item["answer"] for item in answered)


@pytest.mark.slow
def test_requester_cannot_approve_and_engineer_role_cannot_review(waiting_review: runner.RunOutcome, separate_reviewer):
    with pytest.raises(PermissionDeniedError):
        runner.submit_review(
            ReviewDecision(run_id=waiting_review.run_id, reviewer="alice", decision="approve"), "reviewer"
        )
    with pytest.raises(PermissionDeniedError):
        runner.submit_review(
            ReviewDecision(run_id=waiting_review.run_id, reviewer="bob", decision="approve"), "engineer"
        )
    with pytest.raises(RunStateError):
        runner.resume_run(ResumeRequest(run_id=waiting_review.run_id, kind="clarify", value={}))


@pytest.mark.slow
def test_reject_goes_back_to_codegen_then_approve(waiting_review: runner.RunOutcome):
    reject = ReviewDecision(run_id=waiting_review.run_id, reviewer="bob", decision="reject", note="thêm cột nguồn")
    outcome = runner.submit_review(reject, "reviewer")
    assert outcome.status == "waiting_review"
    values = runner.get_values(waiting_review.run_id)
    assert values["review_rounds"] == 1 and values["review_notes"] == ["thêm cột nguồn"]
    assert values["previous_files"]
    approve = ReviewDecision(run_id=waiting_review.run_id, reviewer="bob", decision="approve")
    assert runner.submit_review(approve, "reviewer").status == "approved"
    assert [r.decision for r in get_store().list_reviews(waiting_review.run_id)] == ["reject", "approve"]


def test_review_permission_default_single_de_role():
    """Mặc định 1 vai trò DE: người tạo yêu cầu tự duyệt được (quyết định của người dùng, xem JOURNAL)."""
    assert runner.review_permission_error("de", "alice", "alice") == ""


def test_review_permission_separate_mode(separate_reviewer):
    assert "Reviewer" in runner.review_permission_error("de", "bob", "alice")
    assert "tự duyệt" in runner.review_permission_error("reviewer", "alice", "alice")
    assert runner.review_permission_error("reviewer", "bob", "alice") == ""


def test_repeated_error_goes_to_rescue_then_abort(built_state, mock_llm):
    mock_llm("codegen", {"files": {"models/marts/fct_daily_revenue.sql": "drop table x"}, "notes": []})
    outcome = _answer_first(runner.start_run("doanh thu ngày", "carol"))
    assert outcome.status == "waiting_rescue"
    values = runner.get_values(outcome.run_id)
    assert values["fix_attempts"] == 2  # cùng một lỗi lặp 2 lần → cứu hộ sớm
    final = runner.resume_run(ResumeRequest(run_id=outcome.run_id, kind="rescue", value={"action": "abort"}))
    assert final.status == "failed" and "cứu hộ" in final.error


def test_llm_config_error_marks_run_failed(built_state, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from src.config import get_settings

    get_settings.cache_clear()
    try:
        outcome = runner.start_run("doanh thu ngày", "dave")
    finally:
        monkeypatch.setenv("LLM_PROVIDER", "mock")
        get_settings.cache_clear()
    assert outcome.status == "failed" and "OPENAI_API_KEY" in outcome.error


def test_plan_is_shown_with_explanations_and_can_be_revised(built_state):
    """J1b: kế hoạch hiện ra có giải thích; sửa (kèm ghi chú) → Planner lập lại; ghi chú rỗng → hỏi lại; đồng ý → chạy."""
    outcome = _answer_only(runner.start_run("Gộp đơn hàng 3 nguồn, tính doanh thu ngày", "erin"))
    plan = outcome.pending
    assert outcome.status == "waiting_plan_review" and plan["kind"] == "plan"
    assert plan["summary"] and plan["spec"]["target"] == "fct_daily_revenue"
    assert len(plan["steps"]) >= 3 and all(step["detail"] and step["reason"] for step in plan["steps"])
    blank = runner.resume_run(ResumeRequest(run_id=outcome.run_id, kind="plan", value={"decision": "revise"}))
    assert blank.status == "waiting_plan_review"  # sửa mà không nói sửa gì → hỏi lại, không chạy tiếp
    revise = {"decision": "revise", "note": "thêm cột nguồn bán"}
    again = runner.resume_run(ResumeRequest(run_id=outcome.run_id, kind="plan", value=revise))
    values = runner.get_values(outcome.run_id)
    assert again.status == "waiting_plan_review" and values["plan_feedback"] == ["thêm cột nguồn bán"]
    assert values["plan_reviews"] == 1 and "workspace" not in values  # chưa nạp nguồn, chưa tốn token sinh code
    done = runner.resume_run(ResumeRequest(run_id=outcome.run_id, kind="plan", value={"decision": "approve"}))
    assert done.status == "waiting_review"
