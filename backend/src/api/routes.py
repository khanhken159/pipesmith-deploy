"""Router gốc `/api/v1`; pipeline routes require a real session."""

from fastapi import APIRouter, Depends

from src.api import auth, catalog, error_book, reviews, runs
from src.api.deps import current_user
from src.config import APP_VERSION, get_settings

router = APIRouter()
router.include_router(auth.router)
router.include_router(auth.admin_router)

# Keep all existing business URLs and response models. Authentication wraps the same routers;
# role checks for writes live at their route boundaries and in the unchanged runner review policy.
protected = APIRouter(dependencies=[Depends(current_user)])
protected.include_router(runs.router)
protected.include_router(reviews.router)
protected.include_router(error_book.router)
protected.include_router(catalog.router)


@protected.get("/status")
async def agent_status() -> dict[str, str | bool]:
    """Existing agent status contract, now available only to authenticated users."""
    settings = get_settings()
    return {
        "status": "ready",
        "agent": f"P-113 Pipeline Agent v{APP_VERSION}",
        "llm_provider": settings.llm_provider,
        "models": settings.models_summary,
        "simulated": settings.is_mock,
        "require_separate_reviewer": settings.require_separate_reviewer,
    }


router.include_router(protected)
