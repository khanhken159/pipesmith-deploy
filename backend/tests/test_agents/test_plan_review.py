"""J1b: nội dung kế hoạch hiển thị cho DE và cách đọc quyết định (code thuần)."""

import pytest

from src.agents.nodes.plan_review import default_plan, parse_plan_reply, plan_payload

SPEC = {
    "target": "fct_daily_revenue",
    "sources": [{"name": "shopee_orders"}, {"name": "tiki_orders"}],
    "grain": ["order_date"],
    "metrics": [{"name": "revenue_vnd", "description": "tổng tiền"}],
    "filters": ["chỉ đơn hoàn tất"],
}


def test_code_builds_a_plan_when_planner_leaves_it_empty():
    payload = plan_payload(SPEC)
    assert payload["kind"] == "plan" and "fct_daily_revenue" in payload["summary"]
    assert payload["steps"] == default_plan(SPEC)
    assert "shopee_orders, tiki_orders" in payload["steps"][0]["detail"]
    assert all(step["reason"] for step in payload["steps"])


def test_planner_plan_is_shown_as_is():
    steps = [{"title": "Làm sạch", "detail": "stg_x", "reason": "ngày lẫn định dạng"}]
    payload = plan_payload({**SPEC, "plan_summary": "Tóm tắt", "plan": steps})
    assert payload["summary"] == "Tóm tắt" and payload["steps"] == steps


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ({"decision": "approve"}, {"decision": "approve", "note": ""}),
        ({"decision": "revise", "note": "  thêm cột kênh "}, {"decision": "revise", "note": "thêm cột kênh"}),
        ({"decision": "revise", "note": "  "}, None),
        ({"decision": "maybe"}, None),
        ("approve", None),
    ],
)
def test_parse_plan_reply(reply: object, expected: dict | None):
    assert parse_plan_reply(reply) == expected
