"""J1b Duyệt kế hoạch: graph tạm dừng, DE đọc kế hoạch có giải thích rồi đồng ý (sinh code) hoặc ghi chú để sửa.

Kế hoạch do Planner viết (lời LLM, chưa kiểm chứng); nếu Planner bỏ trống thì code dựng kế hoạch tối thiểu từ đặc tả
để DE luôn có thứ để duyệt. Đặt bước này trước khi sinh code để không tốn token cho kế hoạch sai.
"""

from langgraph.types import interrupt

from src.agents.state import PipelineState

PLAN_SPEC_FIELDS = ("target", "mode", "mode_reason", "grain", "output_columns", "metrics", "filters", "assumptions")
NEXT_STEPS = (
    "Sau khi bạn đồng ý: nạp nguồn vào sandbox → soi dữ liệu → sinh model dbt + DAG → Tester độc lập viết test "
    "(không xem code) → chạy thử trong sandbox → tối ưu nếu đáng → bạn duyệt code (J2)."
)


def _names(items: list[dict], key: str = "name") -> str:
    return ", ".join(str(item.get(key, "")) for item in items) or "—"


def default_plan(spec: dict) -> list[dict]:
    """Kế hoạch tối thiểu dựng bằng code từ đặc tả (khi Planner không viết phần giải thích)."""
    metrics = "; ".join(f"{m.get('name')}: {m.get('description')}" for m in spec.get("metrics", [])) or "—"
    return [
        {
            "title": "Nạp nguồn",
            "detail": f"Đọc các bảng: {_names(spec.get('sources', []))}.",
            "reason": "Đây là các nguồn chứa dữ liệu yêu cầu cần.",
        },
        {
            "title": "Làm sạch (staging)",
            "detail": "Chuẩn hóa ngày, tiền, mã và trạng thái của từng nguồn về cùng một dạng.",
            "reason": "Dữ liệu thô mỗi nguồn ghi một kiểu; phải thống nhất trước khi gộp.",
        },
        {
            "title": f"Tính bảng đích {spec.get('target', '')}",
            "detail": f"Mỗi dòng là một {', '.join(spec.get('grain', [])) or '—'}; chỉ số: {metrics}.",
            "reason": "Đúng mức gộp và chỉ số yêu cầu nêu.",
        },
        {
            "title": "Áp dụng điều kiện lọc",
            "detail": "; ".join(spec.get("filters", [])) or "Không có điều kiện lọc riêng.",
            "reason": "Theo yêu cầu và câu trả lời làm rõ.",
        },
    ]


def plan_payload(spec: dict) -> dict:
    """Nội dung hiển thị cho DE ở J1b."""
    steps = spec.get("plan") or default_plan(spec)
    return {
        "kind": "plan",
        "summary": spec.get("plan_summary")
        or f"Tạo bảng {spec.get('target', '')} từ {_names(spec.get('sources', []))}.",
        "steps": steps,
        "spec": {key: spec.get(key) for key in PLAN_SPEC_FIELDS},
        "sources": [s.get("name") for s in spec.get("sources", [])],
        "next_steps": NEXT_STEPS,
    }


def parse_plan_reply(reply: object) -> dict | None:
    """Quyết định hợp lệ: đồng ý, hoặc yêu cầu sửa kèm ghi chú; còn lại trả về None."""
    if not isinstance(reply, dict):
        return None
    decision, note = reply.get("decision"), str(reply.get("note") or "").strip()
    if decision == "approve":
        return {"decision": "approve", "note": note}
    if decision == "revise" and note:
        return {"decision": "revise", "note": note}
    return None


def plan_review_node(state: PipelineState) -> dict:
    """Tạm dừng chờ DE; sửa → ghi chú chuyển cho Planner lập lại kế hoạch."""
    reply = parse_plan_reply(interrupt(plan_payload(state.get("spec", {}))))
    if reply is None:
        return {"plan_review": {"invalid": True}}
    if reply["decision"] == "approve":
        return {"plan_review": reply}
    return {
        "plan_review": reply,
        "plan_feedback": [*state.get("plan_feedback", []), reply["note"]],
        "plan_reviews": state.get("plan_reviews", 0) + 1,
    }
