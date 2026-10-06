"""Test V0 Soát spec: chặn khi còn điểm chưa rõ, thiếu trường, nguồn không có thật, mode không khớp."""

import pytest

from src.agents.nodes.spec_check import check_spec, spec_check_node

CATALOG = [{"name": "orders", "kind": "csv"}]


def valid_spec(**overrides: object) -> dict:
    spec = {
        "request_text": "doanh thu ngày",
        "mode": "ELT",
        "sources": [{"name": "orders", "kind": "csv", "path": "x.csv"}],
        "target": "fct_daily_revenue",
        "grain": ["order_date"],
        "output_columns": [{"name": "order_date", "type": "DATE"}, {"name": "revenue", "type": "BIGINT"}],
        "metrics": [{"name": "revenue", "description": "tổng tiền"}],
    }
    spec.update(overrides)
    return spec


def test_valid_spec_passes():
    assert check_spec(valid_spec(), CATALOG) == []


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {"unknowns": ["trạng thái nào?"], "questions": [{"id": "q", "question": "?", "options": ["a", "b"]}]},
            "chưa rõ",
        ),
        ({"unknowns": ["trạng thái nào?"]}, "không đặt câu hỏi"),
        ({"target": "Bang Dich"}, "bảng đích"),
        ({"grain": ["ngay"]}, "grain"),
        ({"sources": [{"name": "khong_co", "kind": "csv"}]}, "không có trong thư mục"),
        ({"sources": [{"name": "orders", "kind": "json"}]}, "sai loại"),
        ({"mode": "ETL"}, "không khớp"),
        ({"output_columns": []}, "cột đầu ra"),
    ],
)
def test_invalid_spec_is_blocked(overrides: dict, expected: str):
    errors = check_spec(valid_spec(**overrides), CATALOG)
    assert any(expected in e for e in errors), errors


def test_node_keeps_planner_format_error():
    update = spec_check_node({"spec": {}, "spec_errors": ["Planner trả về sai định dạng"]})
    assert update["spec_errors"] == ["Planner trả về sai định dạng"]


def test_node_empty_spec():
    assert spec_check_node({"spec": {}, "source_catalog": CATALOG})["spec_errors"]


SOURCE_COLUMNS = [
    {"name": "order_date", "type": "DATE"},
    {"name": "source", "type": "VARCHAR"},
    {"name": "revenue", "type": "DOUBLE"},
]


@pytest.mark.parametrize(
    ("overrides", "ok"),
    [
        ({"output_columns": SOURCE_COLUMNS}, False),  # LLM thật: có cột nguồn nhưng grain chỉ có ngày → trùng dòng
        ({"output_columns": SOURCE_COLUMNS, "grain": ["order_date", "source"]}, True),
        ({"output_columns": SOURCE_COLUMNS, "metrics": [], "grain": ["order_date"]}, True),  # bảng chiều: không áp dụng
        (  # ELT-Bench `positions`: grain là mã → cột mô tả phụ thuộc mã, hợp lệ
            {"output_columns": [{"name": "position_id", "type": "BIGINT"}, *SOURCE_COLUMNS], "grain": ["position_id"]},
            True,
        ),
    ],
)
def test_dimension_columns_must_be_in_grain(overrides: dict, ok: bool):
    errors = [e for e in check_spec(valid_spec(**overrides), CATALOG) if "không nằm trong grain" in e]
    assert (errors == []) is ok


def test_dimension_table_without_metrics_passes():
    """Bảng chiều (mỗi dòng một vị trí/địa điểm) không có chỉ số vẫn hợp lệ."""
    assert check_spec(valid_spec(metrics=[]), CATALOG) == []
