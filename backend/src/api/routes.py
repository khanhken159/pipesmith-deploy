"""Router gốc `/api/v1`."""

from fastapi import APIRouter

from src.api import catalog, error_book, reviews, runs
from src.config import APP_VERSION, get_settings

router = APIRouter()
router.include_router(runs.router)
router.include_router(reviews.router)
router.include_router(error_book.router)
router.include_router(catalog.router)


@router.get("/status")
async def agent_status() -> dict[str, str | bool]:
    """Trạng thái agent: LLM đang dùng, có phải mô phỏng không, chế độ duyệt (web hiển thị nhãn tương ứng)."""
    settings = get_settings()
    return {
        "status": "ready",
        "agent": f"P-113 Pipeline Agent v{APP_VERSION}",
        "llm_provider": settings.llm_provider,
        "models": settings.models_summary,
        "simulated": settings.is_mock,
        "require_separate_reviewer": settings.require_separate_reviewer,
    }
