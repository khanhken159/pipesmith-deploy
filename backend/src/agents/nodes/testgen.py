"""E3b Testgen: test do code sinh từ spec (not_null, grain duy nhất, khóa ngoại) + test đối soát.

Test đối soát: LLM chỉ viết câu tính KẾT QUẢ KỲ VỌNG từ raw; phép so sánh hai chiều do code dựng (luôn đúng).

Luật: Testgen KHÔNG nhận code của Coder; chỉ thấy spec, danh mục raw và hồ sơ dữ liệu.
"""

import logging

import yaml

from src.agents.nodes.common import sandbox_db, spec_of, usage_of
from src.agents.state import PipelineState
from src.agents.tools.duckdb_tools import RAW_SCHEMA, read_catalog
from src.models.spec import OutputColumn, PipelineSpec
from src.services.llm import LLMOutputError, call_llm, parse_json_output, to_json

logger = logging.getLogger(__name__)


def _column_tests(column: OutputColumn, grain: list[str]) -> dict:
    """Cột grain (khóa dòng) không được rỗng; cột khác có thể rỗng hợp lệ (ví dụ địa điểm chưa có nhân viên)."""
    tests: list = ["not_null"] if column.name in grain else []
    if "." in column.references:
        table, field = column.references.split(".", 1)
        tests.append({"relationships": {"arguments": {"to": f"ref('{table}')", "field": field}}})
    return {"name": column.name, "data_tests": tests}


def generic_tests(spec: PipelineSpec) -> dict[str, str]:
    """Test tất định: schema.yml (grain không rỗng, khóa ngoại) + test grain không trùng."""
    columns = [_column_tests(c, spec.grain) for c in spec.output_columns]
    schema = {"version": 2, "models": [{"name": spec.target, "columns": [c for c in columns if c["data_tests"]]}]}
    grain = ", ".join(spec.grain)
    unique_sql = (
        f"-- Mỗi giá trị grain ({grain}) chỉ có một dòng\n"
        f"select {grain}, count(*) as n\nfrom {{{{ ref('{spec.target}') }}}}\ngroup by {grain}\nhaving count(*) > 1\n"
    )
    return {
        f"models/marts/{spec.target}.yml": yaml.safe_dump(schema, sort_keys=False, allow_unicode=True),
        "tests/assert_grain_unique.sql": unique_sql,
    }


def blind_inputs(state: PipelineState) -> dict[str, str]:
    """Đầu vào cho LLM testgen: chỉ spec + danh mục + hồ sơ. Không có `code_files`."""
    return {
        "spec": to_json(state.get("spec", {})),
        "catalog": to_json(read_catalog(sandbox_db(state)).get(RAW_SCHEMA, {})),
        "profile": to_json(state.get("profile", {})),
    }


def own_test_errors(state: PipelineState) -> list[str]:
    """Lỗi V1 nằm trong file test (chỉ lỗi của test, không chứa code của Coder)."""
    safety = state.get("safety", {})
    return [] if safety.get("passed", True) else [i for i in safety.get("issues", []) if i.startswith("tests/")]


def previous_llm_tests(state: PipelineState, generic: dict[str, str]) -> dict[str, str]:
    """Test đối soát do LLM viết ở vòng trước (không gồm test tất định)."""
    return {k: v for k, v in state.get("test_files", {}).items() if k.startswith("tests/") and k not in generic}


NUMERIC_TYPES = {"BIGINT", "INTEGER", "INT", "HUGEINT", "SMALLINT", "DOUBLE", "FLOAT", "REAL", "DECIMAL", "NUMERIC"}
ABS_TOL, REL_TOL = 1e-6, 1e-9


def _mismatch(column: OutputColumn) -> str:
    """Điều kiện "lệch" cho một cột không thuộc grain: số so có sai số, cột khác so bằng nhau tuyệt đối."""
    name = column.name
    if column.type.upper().split("(")[0] in NUMERIC_TYPES:
        diff = f"abs(coalesce(e.{name}, 0) - coalesce(a.{name}, 0))"
        return f"{diff} > {ABS_TOL} + {REL_TOL} * abs(coalesce(a.{name}, 0))"
    return f"e.{name} is distinct from a.{name}"


def reconcile_test(spec: PipelineSpec, expected_sql: str) -> str:
    """Test đối soát do CODE dựng: kỳ vọng (Testgen tính từ raw) vs bảng đích, hai chiều theo grain; 0 dòng = đạt."""
    others = [c for c in spec.output_columns if c.name not in spec.grain]
    cols = ", ".join([*spec.grain, *(c.name for c in others)])
    keys = " and ".join(f"e.{g} is not distinct from a.{g}" for g in spec.grain)
    shown = [f"coalesce(e.{g}, a.{g}) as {g}" for g in spec.grain]
    shown += [f"e.{c.name} as expected_{c.name}, a.{c.name} as actual_{c.name}" for c in others]
    lines = [
        "-- Đối soát (code dựng): kết quả kỳ vọng do Testgen tính độc lập từ raw, so hai chiều với bảng đích",
        "with expected as (",
        *("    " + line for line in expected_sql.strip().rstrip(";").splitlines()),
        "),",
        "",
        f"expected_rows as (select {cols}, true as _found from expected),",
        "",
        f"actual_rows as (select {cols}, true as _found from {{{{ ref('{spec.target}') }}}})",
        "",
        f"select {', '.join(shown)}",
        "from expected_rows as e",
        f"full outer join actual_rows as a on {keys}",
        "where e._found is null or a._found is null",
        *(f"    or {_mismatch(c)}" for c in others),
    ]
    return "\n".join(lines) + "\n"


def _parse_expected(text: str, spec: PipelineSpec) -> tuple[dict[str, str], list[str]]:
    """Đọc `expected_sql` của LLM → (file test đối soát, ghi chú). Kỳ vọng phải tính từ raw, không đọc bảng đích."""
    try:
        data = parse_json_output(text)
    except LLMOutputError as exc:
        logger.warning("testgen output invalid", extra={"error": str(exc)})
        return {}, [f"Testgen LLM trả về sai định dạng, chỉ dùng test tất định: {exc}"]
    expected, notes = str(data.get("expected_sql") or ""), [str(n) for n in data.get("notes") or []]
    if not expected.strip() or "ref(" in expected:
        return {}, [*notes, "Testgen không trả `expected_sql` hợp lệ (phải tính từ source raw), bỏ test đối soát."]
    return {f"tests/assert_{spec.target}_reconciles.sql": reconcile_test(spec, expected)}, notes


def testgen_node(state: PipelineState) -> dict:
    """Sinh test; LLM chỉ được gọi khi spec có chỉ số cần đối soát và chưa có test đối soát dùng được.

    Đặc tả không đổi thì "đáp án" không đổi theo code: test vòng trước không lỗi được giữ nguyên.
    """
    spec = spec_of(state)
    files, notes = generic_tests(spec), ["Test tất định: cột grain không rỗng, grain không trùng."]
    if not spec.metrics:
        return {"test_files": files, "test_notes": notes}
    previous, errors = previous_llm_tests(state, files), own_test_errors(state)
    if previous and not errors:
        return {"test_files": {**files, **previous}, "test_notes": state.get("test_notes", notes)}
    variables = {**blind_inputs(state), "previous_tests": to_json(previous) if errors else "(chưa có)"}
    response = call_llm("testgen", {**variables, "test_errors": "\n".join(errors) or "(không có)"})
    llm_files, llm_notes = _parse_expected(response.text, spec)
    return {"test_files": {**files, **llm_files}, "test_notes": notes + llm_notes, "llm_usage": usage_of(response)}
