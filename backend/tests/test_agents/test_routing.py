"""Test các hàm rẽ nhánh của graph (thuần, không chạy node)."""

import pytest

from src.agents import routing

SPEC_WITH_QUESTIONS = {"unknowns": ["?"], "questions": [{"id": "q", "question": "?", "options": ["a", "b"]}]}


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({}, "spec_check"),
        ({"error": "chưa có nguồn"}, "fail"),
    ],
)
def test_after_planner(state: dict, expected: str):
    assert routing.after_planner(state) == expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"spec_errors": []}, "plan_review"),
        ({"spec_errors": ["x"], "spec": SPEC_WITH_QUESTIONS, "plan_rounds": 1}, "clarify"),
        ({"spec_errors": ["x"], "spec": SPEC_WITH_QUESTIONS, "plan_rounds": 6}, "fail"),
        ({"spec_errors": ["thiếu target"], "spec": {}, "plan_rounds": 1}, "planner"),
        ({"spec_errors": ["thiếu target"], "spec": {}, "plan_rounds": 5}, "fail"),
    ],
)
def test_after_spec_check(state: dict, expected: str):
    assert routing.after_spec_check(state) == expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"plan_review": {"decision": "approve"}}, "ingest"),
        ({"plan_review": {"decision": "revise", "note": "x"}, "plan_reviews": 1}, "planner"),
        ({"plan_review": {"decision": "revise", "note": "x"}, "plan_reviews": 4}, "fail"),
        ({"plan_review": {"invalid": True}}, "plan_review"),
    ],
)
def test_after_plan_review(state: dict, expected: str):
    assert routing.after_plan_review(state) == expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"fix_attempts": 1, "error_signatures": ["a"]}, "codegen"),
        ({"fix_attempts": 2, "error_signatures": ["a", "b"]}, "codegen"),
        ({"fix_attempts": 2, "error_signatures": ["a", "a"]}, "rescue"),
        ({"fix_attempts": 3, "error_signatures": ["a", "b", "c"]}, "rescue"),
    ],
)
def test_fix_route(state: dict, expected: str):
    assert routing.fix_route(state) == expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"safety": {"passed": True}}, "sandbox_run"),
        ({"safety": {"passed": False}, "fix_attempts": 1, "error_signatures": ["a"]}, "codegen"),
    ],
)
def test_after_safety(state: dict, expected: str):
    assert routing.after_safety(state) == expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"sandbox": {"passed": True}}, "optimizer"),
        ({"sandbox": {"passed": True}, "optimization": {"decision": "applied"}}, "package"),
        ({"sandbox": {"passed": False}, "fix_attempts": 3, "error_signatures": ["a", "b", "c"]}, "rescue"),
    ],
)
def test_after_sandbox(state: dict, expected: str):
    assert routing.after_sandbox(state) == expected


@pytest.mark.parametrize(
    ("fn", "state", "expected"),
    [
        (routing.after_ingest, {}, "profiler"),
        (routing.after_ingest, {"error": "x"}, "fail"),
        (routing.after_rescue, {}, "codegen"),
        (routing.after_rescue, {"error": "dừng"}, "fail"),
        (routing.after_optimizer, {"optimization": {"decision": "skipped"}}, "package"),
        (routing.after_optimizer, {"opt_candidate": {"sql": "x"}}, "compare"),
        (routing.after_compare, {}, "optimizer"),
        (routing.after_compare, {"optimization": {"decision": "applied"}}, "safety"),
        (routing.after_compare, {"optimization": {"decision": "skipped"}}, "package"),
    ],
)
def test_simple_routes(fn, state: dict, expected: str):
    assert fn(state) == expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ({"review": {"invalid": True}}, "review"),
        ({"review": {"decision": "approve"}}, "finalize"),
        ({"review": {"decision": "reject"}, "review_rounds": 1}, "codegen"),
        ({"review": {"decision": "reject"}, "review_rounds": 3}, "fail"),
    ],
)
def test_after_review(state: dict, expected: str):
    assert routing.after_review(state) == expected
