"""E4 bước 1 — phát hiện dấu hiệu query chậm trên cây cú pháp (sqlglot, không dùng LLM).

Một phần quy tắc chuyển từ nhánh `feature/optimizer-agent` (TrungTuyenDo02), viết lại theo chuẩn code của repo.
"""

from collections import Counter
from collections.abc import Callable

from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope

from src.agents.tools.sql_tools import parse_single_select
from src.models.evidence import Finding


def is_top_level(node: exp.Expression, root: exp.Expression) -> bool:
    """True nếu node là SELECT ngoài cùng (hoặc một nhánh của UNION ngoài cùng)."""
    parent = node.parent
    while isinstance(parent, exp.SetOperation):
        parent = parent.parent
    return node is root or parent is None


def _select_star(tree: exp.Expression) -> list[Finding]:
    if any(isinstance(s, exp.Star) for sel in tree.find_all(exp.Select) for s in sel.expressions):
        return [Finding(rule="select_star", message="Dùng SELECT *: đọc thừa cột, khó kiểm soát schema.")]
    return []


def _union_distinct(tree: exp.Expression) -> list[Finding]:
    for union in tree.find_all(exp.Union):
        if union.args.get("distinct"):
            same = union.left.sql() == union.right.sql()
            what = "giữa hai nhánh giống hệt nhau" if same else "thay vì UNION ALL"
            return [
                Finding(
                    rule="union_distinct", message=f"UNION (khử trùng) {what}: phải băm toàn bộ dòng để loại trùng."
                )
            ]
    return []


def _function_in_where(tree: exp.Expression) -> list[Finding]:
    for where in tree.find_all(exp.Where):
        for func in where.find_all(exp.Func):
            if func.find(exp.Column) and not isinstance(func, (exp.And, exp.Or, exp.Not, exp.Binary, exp.In)):
                return [Finding(rule="function_in_where", message="Hàm bọc cột trong WHERE làm mất khả năng lọc sớm.")]
    return []


def _implicit_cross_join(tree: exp.Expression) -> list[Finding]:
    for select in tree.find_all(exp.Select):
        joins = select.args.get("joins") or []
        bare = [j for j in joins if not j.args.get("on") and not j.args.get("using") and j.args.get("kind") != "CROSS"]
        if bare and not any(isinstance(j.this, exp.Unnest) for j in joins):
            return [Finding(rule="implicit_cross_join", message="JOIN không có điều kiện (tích Đề-các ngầm).")]
    return []


def _correlated_subquery(tree: exp.Expression) -> list[Finding]:
    if any(scope.is_correlated_subquery for scope in traverse_scope(tree)):
        return [Finding(rule="correlated_subquery", message="Truy vấn con tương quan: có thể chạy lại theo từng dòng.")]
    return []


def _redundant_distinct(tree: exp.Expression) -> list[Finding]:
    for select in tree.find_all(exp.Select):
        if select.args.get("distinct") and select.args.get("group"):
            return [Finding(rule="redundant_distinct", message="DISTINCT thừa khi đã GROUP BY.")]
        if select.args.get("distinct") and not is_top_level(select, tree):
            return [
                Finding(
                    rule="distinct_in_subquery",
                    message="DISTINCT trong subquery/CTE: khử trùng toàn bộ dữ liệu trung gian.",
                )
            ]
    return []


def _order_in_subquery(tree: exp.Expression) -> list[Finding]:
    for select in tree.find_all(exp.Select):
        inner = not is_top_level(select, tree)
        if inner and select.args.get("order") and not (select.args.get("limit") or select.args.get("offset")):
            return [
                Finding(
                    rule="order_in_subquery", message="ORDER BY trong subquery không có LIMIT: tốn sắp xếp mà vô ích."
                )
            ]
    return []


def _window_dedupe(tree: exp.Expression) -> list[Finding]:
    for window in tree.find_all(exp.Window):
        if isinstance(window.this, exp.RowNumber) and window.args.get("partition_by"):
            return [
                Finding(
                    rule="window_dedupe",
                    message="row_number() theo PARTITION BY để khử trùng: tốn phân vùng/sắp xếp; thừa nếu khóa đã duy nhất.",
                )
            ]
    return []


def _join_conditions(tree: exp.Expression) -> list[Finding]:
    findings = []
    ge_pairs = {(n.this.sql(), n.expression.sql()) for n in tree.find_all(exp.GTE)}
    if any((le.this.sql(), le.expression.sql()) in ge_pairs for le in tree.find_all(exp.LTE)):
        findings.append(
            Finding(
                rule="range_equality_join",
                message="Cặp `a >= b AND a <= b` thực chất là phép bằng nhưng buộc dùng range join.",
            )
        )
    if any(isinstance(eq.this, exp.Cast) and isinstance(eq.expression, exp.Cast) for eq in tree.find_all(exp.EQ)):
        findings.append(
            Finding(rule="cast_in_join", message="So sánh qua CAST ở cả hai vế làm phép nối chậm hơn so khóa gốc.")
        )
    return findings


def _repeated_work(tree: exp.Expression) -> list[Finding]:
    findings = []
    counts = Counter(s.this.sql() for s in tree.find_all(exp.Subquery) if isinstance(s.this, exp.Select))
    if any(n > 1 for n in counts.values()):
        findings.append(Finding(rule="repeated_subquery", message="Cùng một subquery xuất hiện nhiều lần (tính lặp)."))
    if any(cte.args.get("materialized") for cte in tree.find_all(exp.CTE)):
        findings.append(
            Finding(rule="materialized_cte", message="CTE MATERIALIZED có thể chặn đẩy điều kiện lọc/cắt cột.")
        )
    return findings


PATTERNS: tuple[Callable[[exp.Expression], list[Finding]], ...] = (
    _select_star,
    _union_distinct,
    _function_in_where,
    _implicit_cross_join,
    _correlated_subquery,
    _redundant_distinct,
    _order_in_subquery,
    _window_dedupe,
    _join_conditions,
    _repeated_work,
)


def detect_slow_patterns(sql: str) -> list[Finding]:
    """Danh sách dấu hiệu chậm (mỗi quy tắc tối đa một mục)."""
    tree = parse_single_select(sql)
    return [finding for pattern in PATTERNS for finding in pattern(tree)]
