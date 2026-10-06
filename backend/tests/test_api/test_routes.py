"""Test API: health, trạng thái agent, đọc danh sách/chi tiết lần chạy."""

from src.services.store import get_store


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["llm_provider"] == "mock"
    assert data["version"] and data["timestamp"]


async def test_agent_status_reports_simulated_mode(client):
    response = await client.get("/api/v1/status")
    assert response.status_code == 200
    assert response.json()["simulated"] is True


async def test_get_unknown_run_returns_friendly_404(client):
    response = await client.get("/api/v1/runs/khong-ton-tai")
    assert response.status_code == 404
    assert "Không tìm thấy" in response.json()["detail"]


async def test_list_and_get_run(client):
    record = get_store().create_run("tính doanh thu ngày", "alice")
    listed = await client.get("/api/v1/runs", params={"limit": 5})
    assert listed.status_code == 200
    assert record.id in [r["id"] for r in listed.json()]
    detail = await client.get(f"/api/v1/runs/{record.id}")
    assert detail.json()["record"]["requester"] == "alice"


async def test_list_runs_rejects_invalid_limit(client):
    response = await client.get("/api/v1/runs", params={"limit": 0})
    assert response.status_code == 422
