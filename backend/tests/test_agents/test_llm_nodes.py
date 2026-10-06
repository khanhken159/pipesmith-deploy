"""Test các node dùng LLM (mock): Planner, Codegen, Testgen (mù code), J1, J2, đóng gói bằng chứng."""

from src.agents.nodes.clarify import valid_answers
from src.agents.nodes.codegen import error_hints, last_error
from src.agents.nodes.package import build_evidence
from src.agents.nodes.planner import build_spec, planner_node
from src.agents.nodes.review import validate_decision
from src.agents.nodes.testgen import blind_inputs, generic_tests
from src.models.evidence import ErrorEntry
from src.models.spec import ClarifyQuestion, PipelineMode, PipelineSpec
from src.services.error_memory import error_signature, get_error_memory


def test_planner_asks_first_then_completes(seeded_sources):
    first = planner_node({"request_text": "doanh thu ngày"})
    spec = first["spec"]
    assert spec["unknowns"] and len(spec["questions"]) == 2
    answers = {q["id"]: q["options"][0] for q in spec["questions"]}
    second = planner_node(
        {"request_text": "doanh thu ngày", "answers": answers, "source_catalog": first["source_catalog"]}
    )
    assert second["spec"]["unknowns"] == [] and second["spec"]["decisions"] == answers
    assert second["llm_usage"][0]["simulated"] is True


def test_planner_mode_is_decided_by_code_not_llm():
    data = {"mode": "ETL", "sources": [{"name": "a", "kind": "csv"}], "signals": {"restricted_pii": False}}
    spec = build_spec(data, "x", {})
    assert spec.mode == PipelineMode.ELT and "Mặc định ELT" in spec.mode_reason


def test_planner_invalid_output_goes_to_spec_errors(seeded_sources, mock_llm):
    mock_llm("planner", {"questions": [{"id": "q", "question": "?", "options": ["chỉ một"]}]})
    update = planner_node({"request_text": "x"})
    assert update["spec"] == {} and "sai định dạng" in update["spec_errors"][0]


def test_planner_without_sources_fails_clearly(monkeypatch, tmp_path):
    from src.agents.nodes import planner

    monkeypatch.setattr(planner, "discover_sources", lambda _: [])
    update = planner_node({"request_text": "x"})
    assert update["status"] == "failed" and "seed" in update["error"]


def test_clarify_keeps_only_valid_options():
    questions = [ClarifyQuestion(id="q1", question="?", options=["a", "b"])]
    assert valid_answers(questions, {"answers": {"q1": "b", "q2": "x"}}) == {"q1": "b"}
    assert valid_answers(questions, {"answers": {"q1": "khác"}}) == {}
    assert valid_answers(questions, "rác") == {}


def test_testgen_is_blind_to_coder_code(pipeline_state: dict):
    inputs = blind_inputs(pipeline_state)
    assert set(inputs) == {"spec", "catalog", "profile"}
    code_snippet = pipeline_state["code_files"]["models/marts/fct_daily_revenue.sql"][:40]
    assert all(code_snippet not in value for value in inputs.values())


def test_generic_tests_cover_not_null_and_grain():
    spec = PipelineSpec.model_validate(
        {
            "request_text": "x",
            "target": "fct_x",
            "grain": ["d", "s"],
            "output_columns": [
                {"name": "d", "type": "DATE"},
                {"name": "s", "type": "VARCHAR", "references": "dim_s.id"},
                {"name": "best_employee", "type": "VARCHAR"},  # có thể rỗng hợp lệ → không gắn not_null
            ],
        }
    )
    files = generic_tests(spec)
    assert "not_null" in files["models/marts/fct_x.yml"] and "relationships" in files["models/marts/fct_x.yml"]
    assert "best_employee" not in files["models/marts/fct_x.yml"]
    assert "group by d, s" in files["tests/assert_grain_unique.sql"]


def test_codegen_reads_last_error_and_only_approved_hints():
    state = {"safety": {"passed": False, "issues": ["Binder Error: cột x không tồn tại"]}}
    error = last_error(state)
    assert "Binder" in error
    memory = get_error_memory()
    entry = memory.record(ErrorEntry(code="BINDER_ERROR", signature=error_signature(error), description=error))
    assert error_hints(error) == []
    memory.approve(entry.id, "dùng tên cột trong danh mục")
    assert error_hints(error)[0]["fix"] == "dùng tên cột trong danh mục"
    assert last_error({"safety": {"passed": True}, "sandbox": {"passed": False, "error": "dbt lỗi"}}) == "dbt lỗi"


def test_review_decision_validation_blocks_self_approval_in_separate_mode(separate_reviewer):
    assert validate_decision({"reviewer": "alice", "decision": "approve"}, "r1", "alice") is None
    assert validate_decision({"reviewer": "bob", "decision": "maybe"}, "r1", "alice") is None


def test_review_decision_allows_self_approval_by_default():
    """Mặc định một vai trò DE: người tạo yêu cầu tự duyệt được."""
    assert validate_decision({"reviewer": "alice", "decision": "approve"}, "r1", "alice").reviewer == "alice"
    assert validate_decision({"reviewer": "bob", "decision": "maybe"}, "r1", "alice") is None
    assert validate_decision({"reviewer": "bob", "decision": "approve"}, "r1", "alice").reviewer == "bob"


def test_evidence_keeps_measured_and_claimed_separate(pipeline_state: dict):
    pipeline_state.update(
        {
            "safety": {"passed": True},
            "sandbox": {"passed": True, "models_ok": 1, "models_total": 1},
            "optimization": {
                "decision": "skipped",
                "reason": "nhỏ",
                "equivalence": [],
                "explanation": "LLM nói nhanh hơn",
            },
        }
    )
    evidence = build_evidence(pipeline_state)
    assert any(m.node.startswith("V2") for m in evidence.measured)
    assert "Optimizer: LLM nói nhanh hơn" in evidence.claimed
    assert all("LLM nói" not in m.result for m in evidence.measured)
