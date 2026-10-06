"""E4 — ứng viên viết lại TẤT ĐỊNH (không LLM): luật trên cây sqlglot + sqlglot.optimizer.

Mỗi luật hoặc tương đương tuyệt đối, hoặc ghi rõ giả định về dữ liệu kèm SQL kiểm chứng (trả về số vi phạm, 0 = đúng).
V3 vẫn đối chiếu kết quả trên mọi bộ dữ liệu và chạy SQL kiểm chứng giả định trước khi chấp nhận.
Chuyển từ nhánh `feature/optimizer-agent` (TrungTuyenDo02), viết lại theo chuẩn code của repo; thêm: luật chỉ áp
cho bảng thật (không áp cho tên CTE).
"""

from collections.abc import Callable

import sqlglot
from pydantic import BaseModel, Field
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer import optimize

from src.agents.tools.slow_patterns import is_top_level
from src.agents.tools.sql_tools import DIALECT

MAX_PASSES = 20
ORDER_SENSITIVE = (exp.GroupConcat, exp.ArrayAgg, exp.First, exp.Last, exp.AnyValue)
INTEGER_TYPES = {"TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT", "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT"}


class Assumption(BaseModel):
    """Giả định về dữ liệu; `check_sql` trả về số vi phạm (0 = giả định đúng)."""

    text: str
    check_sql: str = ""


class RuleCandidate(BaseModel):
    """Bản viết lại do luật/sqlglot sinh ra."""

    source: str
    sql: str
    explanation: str
    applied: list[str] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)


class RuleContext:
    """Ghi lại luật đã áp, lời giải thích, giả định; biết tên CTE để không coi chúng là bảng thật."""

    def __init__(self, tree: exp.Expression, schema: dict) -> None:
        self.schema = schema
        self.ctes = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
        self.applied: list[str] = []
        self.explanations: list[str] = []
        self.assumptions: list[Assumption] = []

    def note(self, rule: str, explanation: str, assumptions: list[Assumption] | None = None) -> None:
        """Ghi một lần áp luật."""
        self.applied.append(rule)
        if explanation not in self.explanations:
            self.explanations.append(explanation)
        known = {a.text for a in self.assumptions}
        self.assumptions.extend(a for a in assumptions or [] if a.text not in known)


def _table_sql(table: exp.Table) -> str:
    return exp.table_(table.name, db=table.db or None).sql(DIALECT)


def _real_table(node: exp.Expression | None, ctx: RuleContext) -> exp.Table | None:
    if not isinstance(node, exp.Table) or (not node.db and node.name.lower() in ctx.ctes):
        return None
    return node


def _single_table(select: exp.Select, ctx: RuleContext) -> exp.Table | None:
    """Bảng thật duy nhất trong FROM (không JOIN), hoặc None."""
    source = select.args.get("from_")
    if source is None or select.args.get("joins"):
        return None
    return _real_table(source.this, ctx)


def _is_star_select(select: exp.Select) -> bool:
    return len(select.expressions) == 1 and isinstance(select.expressions[0], exp.Star)


def _star_base_table(select: exp.Select, ctx: RuleContext) -> exp.Table | None:
    """Bảng gốc nếu FROM là bảng thật hoặc chuỗi subquery `SELECT * FROM ... [WHERE]` dẫn về một bảng."""
    source = select.args.get("from_")
    if source is None or select.args.get("joins"):
        return None
    if isinstance(source.this, exp.Table):
        return _real_table(source.this, ctx)
    inner = source.this.this if isinstance(source.this, exp.Subquery) else None
    if not isinstance(inner, exp.Select) or not _is_star_select(inner):
        return None
    if any(inner.args.get(k) for k in ("distinct", "group", "limit", "offset", "order", "having")):
        return None
    return _star_base_table(inner, ctx)


def _no_duplicate_rows(table: exp.Table) -> Assumption:
    name = _table_sql(table)
    return Assumption(
        text=f"Bảng {name} không có dòng trùng lặp hoàn toàn",
        check_sql=f"SELECT (SELECT count(*) FROM {name}) - (SELECT count(*) FROM (SELECT DISTINCT * FROM {name}))",
    )


def drop_subquery_order_by(tree: exp.Expression, ctx: RuleContext) -> bool:
    """ORDER BY trong subquery không có LIMIT/OFFSET không ảnh hưởng kết quả."""
    if tree.find(*ORDER_SENSITIVE):
        return False
    changed = False
    for select in list(tree.find_all(exp.Select)):
        if is_top_level(select, tree) or not select.args.get("order"):
            continue
        if not (select.args.get("limit") or select.args.get("offset")):
            select.set("order", None)
            changed = True
    if changed:
        ctx.note(
            "drop_subquery_order_by", "Bỏ ORDER BY trong subquery: SQL không đảm bảo thứ tự ở đó, chỉ tốn sắp xếp."
        )
    return changed


def self_union_to_distinct(tree: exp.Expression, ctx: RuleContext) -> bool:
    """`X UNION X` ≡ `SELECT DISTINCT ... X` (tương đương tuyệt đối)."""
    for union in list(tree.find_all(exp.Union)):
        left, right = union.left, union.right
        if not union.args.get("distinct") or left.sql() != right.sql() or not isinstance(left, exp.Select):
            continue
        if left.args.get("limit") or left.args.get("order") or left.args.get("distinct"):
            continue
        replacement = left.copy()
        replacement.set("distinct", exp.Distinct())
        union.replace(replacement)
        ctx.note("self_union_to_distinct", "Hai nhánh UNION giống hệt nhau: X UNION X chỉ là X đã khử trùng.")
        return True
    return False


def drop_distinct_star_table(tree: exp.Expression, ctx: RuleContext) -> bool:
    """`SELECT DISTINCT * FROM t` (trong subquery) → bỏ DISTINCT nếu t không có dòng trùng (có giả định)."""
    for select in list(tree.find_all(exp.Select)):
        table = _star_base_table(select, ctx)
        if is_top_level(select, tree) or table is None or not select.args.get("distinct"):
            continue
        if not _is_star_select(select) or select.args.get("group"):
            continue
        select.set("distinct", None)
        ctx.note(
            "drop_distinct_star_table",
            f"Bỏ DISTINCT trên {_table_sql(table)}: bảng không có dòng trùng nên "
            "DISTINCT không loại gì mà vẫn băm toàn bộ dữ liệu.",
            [_no_duplicate_rows(table)],
        )
        return True
    return False


def _same_table_star_branches(union: exp.Union, ctx: RuleContext) -> exp.Table | None:
    left, right = union.left, union.right
    if not isinstance(left, exp.Select) or not isinstance(right, exp.Select):
        return None
    lt, rt = _single_table(left, ctx), _single_table(right, ctx)
    if lt is None or rt is None or _table_sql(lt) != _table_sql(rt):
        return None
    ok = _is_star_select(left) and _is_star_select(right) and left.args.get("where") and right.args.get("where")
    return lt if ok else None


def union_to_union_all(tree: exp.Expression, ctx: RuleContext) -> bool:
    """UNION hai nhánh `SELECT * FROM t WHERE p` cùng bảng → UNION ALL nếu p1, p2 không giao nhau và t không trùng dòng."""
    for union in list(tree.find_all(exp.Union)):
        table = _same_table_star_branches(union, ctx) if union.args.get("distinct") else None
        if table is None:
            continue
        name = _table_sql(table)
        lw, rw = union.left.args["where"].this.sql(DIALECT), union.right.args["where"].this.sql(DIALECT)
        overlap = Assumption(
            text=f"Hai điều kiện lọc của UNION không giao nhau trên {name}",
            check_sql=f"SELECT count(*) FROM {name} WHERE ({lw}) AND ({rw})",
        )
        union.set("distinct", False)
        ctx.note(
            "union_to_union_all",
            "Đổi UNION thành UNION ALL: hai nhánh lấy các dòng khác nhau của cùng một bảng "
            "không trùng dòng nên bước khử trùng là thừa.",
            [_no_duplicate_rows(table), overlap],
        )
        return True
    return False


def rownumber_to_constant(tree: exp.Expression, ctx: RuleContext) -> bool:
    """row_number() OVER (PARTITION BY k) trên bảng thật mà k duy nhất luôn = 1 → hằng 1 (có giả định)."""
    for window in list(tree.find_all(exp.Window)):
        partition = window.args.get("partition_by") or []
        select = window.find_ancestor(exp.Select)
        table = _single_table(select, ctx) if select else None
        if not isinstance(window.this, exp.RowNumber) or not partition or table is None:
            continue
        if not all(isinstance(p, exp.Column) for p in partition):
            continue
        keys, name = ", ".join(p.sql(DIALECT) for p in partition), _table_sql(table)
        check = f"SELECT count(*) FROM (SELECT {keys} FROM {name} GROUP BY {keys} HAVING count(*) > 1)"
        window.replace(exp.Literal.number(1))
        ctx.note(
            "rownumber_to_constant",
            f"row_number() theo khóa ({keys}) luôn bằng 1 vì khóa duy nhất: bỏ bước phân vùng/sắp xếp.",
            [Assumption(text=f"({keys}) là khóa duy nhất của {name}", check_sql=check)],
        )
        return True
    return False


VOLATILE_FUNCTIONS = {"RANDOM", "RAND", "UUID", "GEN_RANDOM_UUID", "NEXTVAL", "SETSEED"}


def _is_volatile(node: exp.Expression) -> bool:
    """Biểu thức đổi giá trị mỗi lần gọi (random(), uuid()...): gộp hai lần gọi thành một làm đổi kết quả."""
    for func in node.find_all(exp.Func):
        name = func.name if isinstance(func, exp.Anonymous) else func.sql_name()
        if name.upper() in VOLATILE_FUNCTIONS:
            return True
    return False


def _comparison_key(node: exp.Expression) -> tuple[str, str] | None:
    """Chuẩn hóa `a >= b` và `b <= a` về cùng dạng (a, b)."""
    if isinstance(node, exp.GTE):
        return node.this.sql(), node.expression.sql()
    if isinstance(node, exp.LTE):
        return node.expression.sql(), node.this.sql()
    return None


def _merge_range_pairs(condition: exp.Expression) -> exp.Expression | None:
    conjuncts = list(condition.flatten()) if isinstance(condition, exp.And) else [condition]
    for i, first in enumerate(conjuncts):
        key = _comparison_key(first)
        if key and _is_volatile(first):
            continue
        partner = next((j for j, c in enumerate(conjuncts) if j != i and key and _comparison_key(c) == key[::-1]), None)
        if partner is None:
            continue
        a, b = (first.this, first.expression) if isinstance(first, exp.GTE) else (first.expression, first.this)
        rest = [c for k, c in enumerate(conjuncts) if k not in (i, partner)]
        return exp.and_(exp.EQ(this=a.copy(), expression=b.copy()), *rest)
    return None


def range_to_equality(tree: exp.Expression, ctx: RuleContext) -> bool:
    """`a >= b AND a <= b` ≡ `a = b` (đúng cả với NULL) → cho phép hash join."""
    for holder in list(tree.find_all(exp.Where, exp.Join)):
        key = "this" if isinstance(holder, exp.Where) else "on"
        condition = holder.args.get(key)
        merged = _merge_range_pairs(condition) if condition is not None else None
        if merged is not None:
            holder.set(key, merged)
            ctx.note("range_to_equality", "Cặp `a >= b AND a <= b` chính là `a = b`; viết dạng bằng để dùng hash join.")
            return True
    return False


def _column_types(schema: dict) -> dict[str, set[str]]:
    types: dict[str, set[str]] = {}
    stack = [schema]
    while stack:
        for key, value in stack.pop().items():
            if isinstance(value, dict):
                stack.append(value)
            else:
                types.setdefault(key.lower(), set()).add(str(value).upper())
    return types


def cast_equality(tree: exp.Expression, ctx: RuleContext) -> bool:
    """CAST(x AS T) = CAST(y AS T) với x, y số nguyên ≡ x = y."""
    types = _column_types(ctx.schema)
    for eq in list(tree.find_all(exp.EQ)):
        left, right = eq.this, eq.expression
        if not (isinstance(left, exp.Cast) and isinstance(right, exp.Cast)):
            continue
        if (
            not (isinstance(left.this, exp.Column) and isinstance(right.this, exp.Column))
            or left.to.sql() != right.to.sql()
        ):
            continue
        found = types.get(left.this.name.lower(), set()) | types.get(right.this.name.lower(), set())
        if found and found <= INTEGER_TYPES and left.this.name.lower() in types and right.this.name.lower() in types:
            eq.replace(exp.EQ(this=left.this.copy(), expression=right.this.copy()))
            ctx.note(
                "cast_equality", "Hai vế đều là số nguyên bị CAST sang cùng kiểu: so trực tiếp nhanh hơn, cùng kết quả."
            )
            return True
    return False


RULES: tuple[Callable[[exp.Expression, RuleContext], bool], ...] = (
    range_to_equality,
    cast_equality,
    drop_subquery_order_by,
    self_union_to_distinct,
    union_to_union_all,
    drop_distinct_star_table,
    rownumber_to_constant,
)


def rules_candidate(sql: str, schema: dict) -> RuleCandidate | None:
    """Áp các luật tới điểm dừng; None nếu không luật nào áp được."""
    tree = sqlglot.parse_one(sql, read=DIALECT)
    ctx = RuleContext(tree, schema)
    for _ in range(MAX_PASSES):
        if not any(rule(tree, ctx) for rule in RULES):
            break
    if not ctx.applied:
        return None
    return RuleCandidate(
        source="rules",
        sql=tree.sql(dialect=DIALECT, pretty=True),
        explanation=" ".join(ctx.explanations),
        applied=ctx.applied,
        assumptions=ctx.assumptions,
    )


def _canonical(sql: str) -> str:
    return sqlglot.parse_one(sql, read=DIALECT).sql(dialect=DIALECT, normalize=True)


def sqlglot_candidate(sql: str, schema: dict) -> RuleCandidate | None:
    """sqlglot.optimizer (gắn tên bảng, đẩy lọc xuống, gộp subquery, rút gọn); None nếu không đổi hoặc lỗi."""
    try:
        new_sql = optimize(sqlglot.parse_one(sql, read=DIALECT), schema=schema or None, dialect=DIALECT).sql(
            dialect=DIALECT, pretty=True
        )
    except (SqlglotError, KeyError, ValueError):
        return None
    if _canonical(new_sql) == _canonical(sql):
        return None
    return RuleCandidate(
        source="sqlglot",
        sql=new_sql,
        applied=["sqlglot.optimizer"],
        explanation="sqlglot.optimizer chuẩn hóa query: đẩy điều kiện lọc xuống, gộp/khử subquery, "
        "rút gọn biểu thức. Không đổi logic.",
    )
