"""V0 Soát Spec (code thuần): chặn khi còn điểm chưa biết, thiếu trường bắt buộc, hoặc mode không khớp tín hiệu."""

import re

from src.agents.state import PipelineState
from src.models.spec import PipelineSpec, decide_mode, signals_from_sources

IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _required_fields(spec: PipelineSpec) -> list[str]:
    errors = []
    if not IDENTIFIER_RE.match(spec.target):
        errors.append("Thiếu hoặc sai tên bảng đích (target phải là snake_case).")
    if not spec.sources:
        errors.append("Chưa chọn nguồn dữ liệu nào.")
    if not spec.grain:
        errors.append("Chưa xác định grain (cột xác định một dòng).")
    names = [c.name for c in spec.output_columns]
    if len(names) != len(set(names)) or not names:
        errors.append("Danh sách cột đầu ra rỗng hoặc bị trùng tên.")
    errors.extend(
        f"Cột grain '{g}' không nằm trong cột đầu ra; grain chỉ được chọn trong: {', '.join(names)}."
        for g in spec.grain
        if g not in names
    )
    return errors


def _sources_exist(spec: PipelineSpec, catalog: list[dict]) -> list[str]:
    known = {item["name"]: item["kind"] for item in catalog}
    return [
        f"Nguồn '{s.name}' không có trong thư mục dữ liệu."
        if s.name not in known
        else f"Nguồn '{s.name}' sai loại ({s.kind} ≠ {known[s.name]})."
        for s in spec.sources
        if known.get(s.name) != s.kind
    ]


def _unknowns(spec: PipelineSpec) -> list[str]:
    if not spec.unknowns:
        return []
    errors = [f"Còn {len(spec.unknowns)} điểm chưa rõ: " + "; ".join(spec.unknowns)]
    if not spec.questions:
        errors.append("Có điểm chưa rõ nhưng Planner không đặt câu hỏi làm rõ.")
    return errors


NUMERIC_PREFIXES = ("BIGINT", "INT", "HUGEINT", "SMALLINT", "DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC")


def _dimensions_in_grain(spec: PipelineSpec) -> list[str]:
    """Bảng gộp theo phân loại (có chỉ số, grain không có cột mã): cột không phải số phải nằm trong grain.

    Grain có cột mã (`id`, `*_id`) thì cột mô tả (tên, chức danh) phụ thuộc vào mã, không gây trùng dòng → bỏ qua.
    """
    if not spec.metrics or any(g.lower() == "id" or g.lower().endswith("_id") for g in spec.grain):
        return []
    return [
        f"Cột '{c.name}' ({c.type}) không phải chỉ số nhưng không nằm trong grain {spec.grain}: thêm vào grain hoặc bỏ."
        for c in spec.output_columns
        if c.name not in spec.grain and not c.type.upper().startswith(NUMERIC_PREFIXES)
    ]


def _mode_matches(spec: PipelineSpec) -> list[str]:
    expected, _ = decide_mode(signals_from_sources(spec.sources, spec.signals))
    return [] if spec.mode == expected else [f"Mode {spec.mode} không khớp tín hiệu (phải là {expected})."]


def check_spec(spec_data: dict, catalog: list[dict]) -> list[str]:
    """Danh sách lỗi của đặc tả (rỗng = đạt)."""
    if not spec_data:
        return ["Chưa có đặc tả hợp lệ từ Planner."]
    spec = PipelineSpec.model_validate(spec_data)
    checks = _unknowns(spec) + _required_fields(spec) + _dimensions_in_grain(spec)
    return checks + _sources_exist(spec, catalog) + _mode_matches(spec)


def spec_check_node(state: PipelineState) -> dict:
    """Soát spec; giữ lỗi định dạng của Planner nếu có."""
    if not state.get("spec") and state.get("spec_errors"):
        return {"spec_errors": state["spec_errors"]}
    return {"spec_errors": check_spec(state.get("spec", {}), state.get("source_catalog", []))}
