"""Test API Phase 7 (mock, không cần khóa): tạo yêu cầu → J1 → bản duyệt → duyệt; cấu trúc dữ liệu; sổ lỗi; lỗi thân thiện.

Chạy nền thật (hàng đợi một luồng); test chờ bằng `get_jobs().wait(run_id)`.
"""

import io
import zipfile
from pathlib import Path

import pytest
from httpx import AsyncClient

from src.services.jobs import get_jobs

API = "/api/v1"
REQUEST = {"request_text": "Gộp đơn hàng 3 nguồn, tính doanh thu ngày"}


async def _create_and_answer(client: AsyncClient, user: str) -> str:
    """Tạo yêu cầu, trả lời J1 bằng lựa chọn đầu, đồng ý kế hoạch J1b, chờ tới bản duyệt; trả về run_id."""
    created = await client.post(f"{API}/runs", json=REQUEST, headers={"X-User": user})
    assert created.status_code == 202
    run_id = created.json()["run_id"]
    get_jobs().wait(run_id)
    detail = (await client.get(f"{API}/runs/{run_id}")).json()
    assert detail["record"]["status"] == "waiting_clarification" and detail["pending"]["kind"] == "clarify"
    answers = {q["id"]: q["options"][0] for q in detail["pending"]["questions"]}
    assert (await client.post(f"{API}/runs/{run_id}/answers", json={"answers": answers})).status_code == 202
    get_jobs().wait(run_id)
    plan = (await client.get(f"{API}/runs/{run_id}")).json()
    assert plan["record"]["status"] == "waiting_plan_review" and plan["pending"]["steps"]
    blank = await client.post(f"{API}/runs/{run_id}/plan", json={"decision": "revise"})
    assert blank.status_code == 422 and "ghi chú" in blank.json()["detail"]
    assert (await client.post(f"{API}/runs/{run_id}/plan", json={"decision": "approve"})).status_code == 202
    get_jobs().wait(run_id)
    return run_id


@pytest.mark.slow
async def test_full_flow_single_de_role(client: AsyncClient, seeded_sources: Path):
    """Mặc định một vai trò DE: người tạo yêu cầu tự xem bằng chứng và duyệt."""
    run_id = await _create_and_answer(client, "an")
    detail = (await client.get(f"{API}/runs/{run_id}")).json()
    assert detail["record"]["status"] == "waiting_review" and detail["busy"] is False
    assert detail["spec"]["target"] == "fct_daily_revenue" and detail["evidence"]["measured"]
    assert detail["spec"]["plan"] and detail["spec"]["plan_summary"]  # kế hoạch đã duyệt vẫn xem lại được
    assert any(e["node"] == "sandbox_run" and e["ok"] for e in detail["events"])
    files = (await client.get(f"{API}/runs/{run_id}/files")).json()
    assert "models/marts/fct_daily_revenue.sql" in files["code_files"] and files["test_files"]
    assert detail["answered"] and detail["answered"][0]["answer"]
    download = await client.get(f"{API}/runs/{run_id}/download")
    assert download.status_code == 200 and download.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(download.content)).namelist()
    assert f"p113-{run_id}/models/marts/fct_daily_revenue.sql" in names
    assert not any(n.endswith(".duckdb") or "/datasets/" in n or n.endswith("profiles.yml") for n in names)
    assert run_id in [r["id"] for r in (await client.get(f"{API}/reviews/queue")).json()]
    review = await client.post(f"{API}/runs/{run_id}/review", json={"decision": "approve"}, headers={"X-User": "an"})
    assert review.status_code == 202
    get_jobs().wait(run_id)
    assert (await client.get(f"{API}/runs/{run_id}")).json()["record"]["status"] == "approved"


@pytest.mark.slow
async def test_separate_reviewer_mode_blocks_self_approval(
    client: AsyncClient, seeded_sources: Path, separate_reviewer
):
    run_id = await _create_and_answer(client, "an")
    approve = {"decision": "approve"}
    self_review = await client.post(
        f"{API}/runs/{run_id}/review", json=approve, headers={"X-User": "an", "X-Role": "reviewer"}
    )
    assert self_review.status_code == 403 and "tự duyệt" in self_review.json()["detail"]
    wrong_role = await client.post(f"{API}/runs/{run_id}/review", json=approve, headers={"X-User": "binh"})
    assert wrong_role.status_code == 403
    ok = await client.post(
        f"{API}/runs/{run_id}/review", json=approve, headers={"X-User": "binh", "X-Role": "reviewer"}
    )
    assert ok.status_code == 202


@pytest.mark.slow
async def test_run_catalog_shows_tables_lineage_and_keys(client: AsyncClient, seeded_sources: Path):
    run_id = await _create_and_answer(client, "an")
    catalog = (await client.get(f"{API}/runs/{run_id}/catalog")).json()
    tables = {t["id"]: t for t in catalog["tables"]}
    assert {"raw.shopee_orders", "main.stg_shopee_orders", "main.fct_daily_revenue"} <= set(tables)
    assert tables["main.fct_daily_revenue"]["layer"] == "mart" and tables["main.fct_daily_revenue"]["rows"] > 0
    assert any(c["name"] == "order_date" and c["is_key"] for c in tables["main.fct_daily_revenue"]["columns"])
    assert tables["raw.shopee_orders"]["duplicate_keys"] > 0  # dữ liệu giả lập có đơn trùng
    edges = {(e["source"], e["target"]) for e in catalog["lineage"]}
    assert ("raw.shopee_orders", "main.stg_shopee_orders") in edges
    assert ("main.stg_shopee_orders", "main.fct_daily_revenue") in edges


async def test_sources_catalog_suggests_join_keys(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    from src.config import get_settings

    golden = Path(__file__).resolve().parents[2] / "eval" / "datasets" / "golden" / "g09_customer_dimension" / "sources"
    monkeypatch.setenv("SOURCES_DIR", str(golden))
    get_settings.cache_clear()
    try:
        catalog = (await client.get(f"{API}/catalog/sources")).json()
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
    assert {t["name"] for t in catalog["tables"]} == {"customers", "orders"}
    assert catalog["joins"][0]["how"] == "gợi ý" and "customer_id" in catalog["joins"][0]["left"]


@pytest.mark.parametrize(
    ("method", "path", "body", "code"),
    [
        ("get", "/runs/khong-co", None, 404),
        ("get", "/runs/khong-co/catalog", None, 404),
        ("get", "/runs/khong-co/download", None, 404),
        ("post", "/runs", {"request_text": "x"}, 422),
        ("post", "/runs/khong-co/review", {"decision": "approve"}, 404),
        ("post", "/runs/khong-co/plan", {"decision": "approve"}, 404),
        ("post", "/errors/999999/approve", {"fix": "x"}, 404),
    ],
)
async def test_friendly_errors(client: AsyncClient, method: str, path: str, body: dict | None, code: int):
    response = await getattr(client, method)(f"{API}{path}", **({"json": body} if body is not None else {}))
    assert response.status_code == code
    assert isinstance(response.json()["detail"], str) and "Traceback" not in response.text


async def test_review_requires_note_and_waiting_state(client: AsyncClient):
    from src.services.store import get_store

    run_id = get_store().create_run("doanh thu", "an").id
    reject = await client.post(f"{API}/runs/{run_id}/review", json={"decision": "reject"})
    assert reject.status_code == 422 and "ghi chú" in reject.json()["detail"]
    approve = await client.post(f"{API}/runs/{run_id}/review", json={"decision": "approve"})
    assert approve.status_code == 409  # chưa ở bước chờ duyệt
    answer = await client.post(f"{API}/runs/{run_id}/answers", json={"answers": {"q": "a"}})
    assert answer.status_code == 409


async def test_status_reports_review_mode(client: AsyncClient):
    data = (await client.get(f"{API}/status")).json()
    assert data["simulated"] is True and data["require_separate_reviewer"] is False and data["models"] == "mock"


async def test_error_book_listing(client: AsyncClient):
    response = await client.get(f"{API}/errors")
    assert response.status_code == 200 and isinstance(response.json(), list)
