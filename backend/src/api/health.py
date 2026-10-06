"""Health check cho Docker HEALTHCHECK, Render và UptimeRobot."""

from datetime import UTC, datetime

from fastapi import APIRouter

from src.config import APP_VERSION, get_settings
from src.models.schemas import HealthResponse
from src.services.store import get_store

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Trạng thái dịch vụ; `status` luôn là "ok" khi tiến trình còn sống, `database` báo riêng."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
        version=APP_VERSION,
        env=settings.app_env,
        database="ok" if get_store().ping() else "error",
        llm_provider=settings.llm_provider,
    )
