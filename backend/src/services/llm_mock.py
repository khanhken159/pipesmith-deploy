"""Nhà cung cấp LLM giả (`LLM_PROVIDER=mock`): câu trả lời CỐ ĐỊNH theo từng node, dùng cho test/CI/demo.

Đây KHÔNG phải chất lượng của mô hình thật. Câu trả lời được viết sẵn cho kịch bản mẫu
"gộp đơn hàng 3 nguồn (Shopee CSV, Tiki JSON, website SQLite), tính doanh thu theo ngày".
"""

import json
from collections.abc import Callable
from string import Template

import sqlglot
from sqlglot import exp

from src.models.schemas import LLMUsage
from src.services.llm import LLMRequest, LLMResponse

Q_STATUS = "q_status"
Q_DUPLICATES = "q_duplicates"
STATUS_OPTIONS = ["Chỉ đơn đã giao/hoàn tất", "Mọi đơn trừ đơn đã hủy (kể cả đơn hoàn tiền)"]
DUPLICATE_OPTIONS = ["Tính một lần (bỏ dòng trùng mã đơn)", "Giữ nguyên mọi dòng"]
RAW_STATUS = {
    "shopee_orders": ("upper(status)", "'COMPLETED'", "'RETURNED'"),
    "tiki_orders": ("lower(state)", "'delivered'", "'refunded'"),
    "website_orders": ("lower(status)", "'paid'", "'refunded'"),
}

STAGING = {
    "shopee_orders": """-- Chuẩn hóa đơn Shopee: ngày dd/mm/yyyy hoặc yyyy-mm-dd, tiền VND dạng chuỗi "1.075.000"
select
    'shopee' as source,
    cast(order_id as varchar) as order_id,
    coalesce(
        try_strptime(cast(order_date as varchar), '%d/%m/%Y'),
        try_strptime(cast(order_date as varchar), '%Y-%m-%d')
    )::date as order_date,
    case upper(status)
        when 'COMPLETED' then 'completed'
        when 'CANCELLED' then 'cancelled'
        when 'RETURNED' then 'refunded'
        else 'other'
    end as status,
    try_cast(nullif(replace(cast(total_amount as varchar), '.', ''), '') as bigint) as amount_vnd
from {{ source('raw', 'shopee_orders') }}
""",
    "tiki_orders": """-- Chuẩn hóa đơn Tiki (JSON từ API): created_at ISO 8601, grand_total số thực
select
    'tiki' as source,
    cast(id as varchar) as order_id,
    cast(created_at as timestamp)::date as order_date,
    case lower(state)
        when 'delivered' then 'completed'
        when 'canceled' then 'cancelled'
        when 'refunded' then 'refunded'
        else 'other'
    end as status,
    cast(round(grand_total) as bigint) as amount_vnd
from {{ source('raw', 'tiki_orders') }}
""",
    "website_orders": """-- Chuẩn hóa đơn website (SQLite): created_ts dạng 'YYYY-MM-DD HH:MM:SS'
select
    'website' as source,
    cast(order_id as varchar) as order_id,
    cast(created_ts as timestamp)::date as order_date,
    case lower(status)
        when 'paid' then 'completed'
        when 'cancelled' then 'cancelled'
        when 'refunded' then 'refunded'
        else 'other'
    end as status,
    cast(amount_vnd as bigint) as amount_vnd
from {{ source('raw', 'website_orders') }}
""",
}

MART_DEDUP = Template("""-- Doanh thu theo ngày từ 3 nguồn; mỗi (nguồn, mã đơn) tính một lần
with all_orders as (
$unions
),

deduped as (
    select *
    from all_orders
    qualify row_number() over (
        partition by source, order_id
        order by order_date, amount_vnd desc nulls last, status
    ) = 1
)

select
    order_date,
    count(*) as order_count,
    cast(coalesce(sum(amount_vnd), 0) as bigint) as revenue_vnd
from deduped
where status in ($statuses)
group by order_date
order by order_date
""")

MART_KEEP_ALL = Template("""-- Doanh thu theo ngày từ 3 nguồn; giữ nguyên mọi dòng
with all_orders as (
$unions
)

select
    order_date,
    count(*) as order_count,
    cast(coalesce(sum(amount_vnd), 0) as bigint) as revenue_vnd
from all_orders
where status in ($statuses)
group by order_date
order by order_date
""")

DAG = Template('''"""DAG Airflow chạy pipeline dbt `$target` hằng ngày (agent sinh, Engineer duyệt trước khi merge)."""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

DBT_CMD = "cd {{ var.value.p113_dbt_project_dir }} && dbt"

with DAG(
    dag_id="p113_$target",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["p113", "dbt"],
) as dag:
    build_models = BashOperator(task_id="dbt_run", bash_command=DBT_CMD + " run --select +$target")
    run_tests = BashOperator(task_id="dbt_test", bash_command=DBT_CMD + " test --select +$target")

    build_models >> run_tests
''')

EXPECTED_DAILY = Template("""-- Kỳ vọng tính độc lập từ raw: mỗi ngày một dòng, số đơn hợp lệ và tổng tiền
select
    order_date,
    count(*) as order_count,
    cast(coalesce(sum(amount), 0) as bigint) as revenue_vnd
from (
    select $distinct
        'shopee' as source,
        cast(order_id as varchar) as order_id,
        coalesce(
            try_strptime(cast(order_date as varchar), '%d/%m/%Y'),
            try_strptime(cast(order_date as varchar), '%Y-%m-%d')
        )::date as order_date,
        try_cast(nullif(replace(cast(total_amount as varchar), '.', ''), '') as bigint) as amount
    from {{ source('raw', 'shopee_orders') }} where upper(status) in ($shopee)
    union all
    select $distinct 'tiki', cast(id as varchar), cast(created_at as timestamp)::date, cast(round(grand_total) as bigint)
    from {{ source('raw', 'tiki_orders') }} where lower(state) in ($tiki)
    union all
    select $distinct 'website', cast(order_id as varchar), cast(created_ts as timestamp)::date, cast(amount_vnd as bigint)
    from {{ source('raw', 'website_orders') }} where lower(status) in ($website)
) as src
group by order_date
""")


def _usage(task: str) -> LLMUsage:
    return LLMUsage(task=task, provider="mock", model="mock", simulated=True)


def _load(variables: dict[str, str], key: str, default: dict | list) -> dict | list:
    """JSON trong biến prompt; trống, sai cú pháp hoặc sai kiểu (dict/list) → `default`."""
    try:
        value = json.loads(variables.get(key) or "null")
    except json.JSONDecodeError:
        return default
    return value if isinstance(value, type(default)) else default


def _choices(spec: dict) -> tuple[bool, bool]:
    """(chỉ đơn hoàn tất?, bỏ trùng?) từ câu trả lời J1 trong spec."""
    decisions = spec.get("decisions", {})
    completed_only = decisions.get(Q_STATUS, STATUS_OPTIONS[0]) == STATUS_OPTIONS[0]
    dedup = decisions.get(Q_DUPLICATES, DUPLICATE_OPTIONS[0]) == DUPLICATE_OPTIONS[0]
    return completed_only, dedup


def _spec_body(catalog: list[dict]) -> dict:
    tabular = [s for s in catalog if s.get("kind") in ("csv", "json", "parquet", "sqlite")]
    known = [s for s in tabular if s["name"] in STAGING]  # kho có nhiều hệ thống: kịch bản mẫu chỉ cần 3 nguồn đơn
    tabular = known or tabular
    return {
        "sources": [{"name": s["name"], "kind": s["kind"], "path": s["path"]} for s in tabular],
        "target": "fct_daily_revenue",
        "grain": ["order_date"],
        "output_columns": [
            {"name": "order_date", "type": "DATE", "description": "Ngày đặt đơn", "references": ""},
            {"name": "order_count", "type": "BIGINT", "description": "Số đơn hợp lệ trong ngày", "references": ""},
            {"name": "revenue_vnd", "type": "BIGINT", "description": "Tổng doanh thu (VND)", "references": ""},
        ],
        "metrics": [{"name": "revenue_vnd", "description": "Tổng tiền các đơn hợp lệ theo ngày, đơn vị VND"}],
        "filters": ["Chỉ tính đơn có trạng thái hợp lệ theo câu trả lời làm rõ"],
        "signals": {"restricted_pii": False, "small_subset_of_large": False},
    }


def _mock_plan(answers: dict) -> dict:
    """Kế hoạch có giải thích cho kịch bản mẫu (DE duyệt ở J1b)."""
    completed_only = answers.get(Q_STATUS, STATUS_OPTIONS[0]) == STATUS_OPTIONS[0]
    dedup = answers.get(Q_DUPLICATES, DUPLICATE_OPTIONS[0]) == DUPLICATE_OPTIONS[0]
    status_rule = "chỉ đơn đã giao/hoàn tất" if completed_only else "mọi đơn trừ đơn đã hủy"
    return {
        "plan_summary": (
            "Tạo bảng fct_daily_revenue: mỗi ngày một dòng, cho biết số đơn và doanh thu (VND) gộp từ Shopee, Tiki "
            f"và website; {status_rule}."
        ),
        "plan": [
            {
                "title": "Làm sạch đơn Shopee",
                "detail": "stg_shopee_orders: đọc order_date dạng dd/mm/yyyy lẫn yyyy-mm-dd, total_amount dạng '1.075.000'.",
                "reason": "Mẫu dữ liệu Shopee có hai kiểu ngày và tiền là chuỗi có dấu chấm.",
            },
            {
                "title": "Làm sạch đơn Tiki và website",
                "detail": "stg_tiki_orders (created_at ISO, grand_total số), stg_website_orders (created_ts, amount_vnd).",
                "reason": "Mỗi nguồn đặt tên cột và trạng thái khác nhau; phải đưa về cùng bộ cột.",
            },
            {
                "title": "Gộp 3 nguồn" + (", bỏ đơn trùng" if dedup else ""),
                "detail": "Ghép các đơn bằng UNION, giữ cột nguồn"
                + ("; mỗi (nguồn, mã đơn) chỉ tính một lần." if dedup else "; giữ mọi dòng."),
                "reason": "Bạn đã chọn: " + DUPLICATE_OPTIONS[0 if dedup else 1] + ".",
            },
            {
                "title": "Tính doanh thu theo ngày",
                "detail": f"fct_daily_revenue: order_date, order_count, revenue_vnd; {status_rule}.",
                "reason": "Yêu cầu là doanh thu ngày; trạng thái được tính theo câu trả lời làm rõ.",
            },
        ],
    }


def mock_planner(variables: dict[str, str]) -> dict:
    """Lần đầu: hỏi 2 câu làm rõ. Khi đã có câu trả lời: trả đặc tả đầy đủ."""
    answers = _load(variables, "answers", {})
    body = _spec_body(_load(variables, "source_catalog", []))
    if isinstance(answers, dict) and {Q_STATUS, Q_DUPLICATES} <= set(answers):
        body.update(unknowns=[], questions=[], assumptions=[f"{k}: {v}" for k, v in answers.items()])
        body.update(_mock_plan(answers))
        return body
    body.update(
        unknowns=["Trạng thái đơn nào được tính doanh thu", "Cách xử lý mã đơn bị trùng trong cùng nguồn"],
        assumptions=[],
        questions=[
            {"id": Q_STATUS, "question": "Đơn ở trạng thái nào được tính vào doanh thu?", "options": STATUS_OPTIONS},
            {
                "id": Q_DUPLICATES,
                "question": "Một mã đơn xuất hiện nhiều lần trong cùng nguồn thì sao?",
                "options": DUPLICATE_OPTIONS,
            },
        ],
    )
    return body


def _staging_names(spec: dict) -> list[str]:
    return [s["name"] for s in spec.get("sources", []) if s["name"] in STAGING]


def mock_codegen(variables: dict[str, str]) -> dict:
    """Sinh model staging + mart + DAG cố định cho kịch bản doanh thu ngày."""
    spec = _load(variables, "spec", {})
    completed_only, dedup = _choices(spec)
    target, names = spec.get("target") or "fct_daily_revenue", _staging_names(spec)
    statuses = "'completed'" if completed_only else "'completed', 'refunded'"
    joiner = "\n    union\n" if dedup else "\n    union all\n"
    unions = joiner.join(f"    select * from {{{{ ref('stg_{n}') }}}}" for n in names)
    mart = (MART_DEDUP if dedup else MART_KEEP_ALL).substitute(unions=unions, statuses=statuses)
    files = {f"models/staging/stg_{n}.sql": STAGING[n] for n in names}
    files[f"models/marts/{target}.sql"] = mart
    files[f"dags/{target}_dag.py"] = DAG.substitute(target=target)
    notes = [
        "Mỗi nguồn một model staging chuẩn hóa ngày, tiền VND và trạng thái về cùng một bộ giá trị.",
        "Model đích gộp 3 nguồn, "
        + ("bỏ trùng theo (nguồn, mã đơn)" if dedup else "giữ mọi dòng")
        + ", tính theo ngày.",
        "DAG Airflow chạy dbt run rồi dbt test hằng ngày.",
    ]
    return {"files": files, "notes": notes}


def _raw_status_list(name: str, completed_only: bool) -> str:
    _, done, refund = RAW_STATUS[name]
    return done if completed_only else f"{done}, {refund}"


def mock_testgen(variables: dict[str, str]) -> dict:
    """Test đối soát viết độc lập từ đặc tả + danh mục (không nhìn code của Coder)."""
    spec = _load(variables, "spec", {})
    completed_only, dedup = _choices(spec)
    params = {name.split("_")[0]: _raw_status_list(name, completed_only) for name in RAW_STATUS}
    expected = EXPECTED_DAILY.substitute(params, distinct="distinct" if dedup else "")
    notes = ["Tính lại từ raw: mỗi ngày một dòng, số đơn và tổng tiền các đơn hợp lệ (bỏ dòng trùng nếu được chọn)."]
    return {"expected_sql": expected, "notes": notes}


def mock_optimizer(variables: dict[str, str]) -> dict:
    """Viết lại cố định: đổi UNION (khử trùng) thành UNION ALL nếu có."""
    tree = sqlglot.parse_one(variables.get("sql", ""), read="duckdb")
    unions = [u for u in tree.find_all(exp.Union) if u.args.get("distinct")]
    for union in unions:
        union.set("distinct", False)
    explanation = (
        "Đổi UNION thành UNION ALL: bước bỏ trùng theo (nguồn, mã đơn) phía sau đã xử lý trùng, "
        "nên không cần băm toàn bộ dữ liệu thêm một lần."
        if unions
        else "Không tìm thấy cách viết lại an toàn; giữ nguyên câu gốc."
    )
    hints = ["BigQuery/Snowflake: phân vùng bảng đích theo order_date và cluster theo source (chỉ gợi ý)."]
    return {"sql": tree.sql(dialect="duckdb", pretty=True), "explanation": explanation, "warehouse_hints": hints}


HANDLERS: dict[str, Callable[[dict[str, str]], dict]] = {
    "planner": mock_planner,
    "codegen": mock_codegen,
    "testgen": mock_testgen,
    "optimizer": mock_optimizer,
}


class MockProvider:
    """LLM giả: không gọi mạng, 0 token, đánh dấu `simulated=True`."""

    def complete(self, request: LLMRequest, prompt: tuple[str, str]) -> LLMResponse:
        """Trả câu trả lời cố định của tác vụ (prompt được dựng nhưng không dùng)."""
        handler = HANDLERS.get(request.task)
        if handler is None:
            return LLMResponse(text="{}", usage=_usage(request.task))
        return LLMResponse(text=json.dumps(handler(request.variables), ensure_ascii=False), usage=_usage(request.task))
