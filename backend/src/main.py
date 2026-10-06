"""Điểm vào FastAPI."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.health import router as health_router
from src.api.routes import router
from src.config import APP_VERSION, get_settings
from src.logging_config import setup_logging
from src.services.seed import ensure_demo_sources
from src.services.tracing import configure_tracing

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Khởi động/tắt ứng dụng."""
    load_dotenv()  # để LangChain/LangSmith đọc được biến trong .env
    settings = get_settings()
    setup_logging(settings.log_level)
    warning = configure_tracing()
    if warning:
        logger.warning(warning)
    if ensure_demo_sources(settings.sources_dir, settings.seed):
        logger.info("demo sources seeded", extra={"dir": str(settings.sources_dir)})
    logger.info("app starting", extra={"env": settings.app_env, "llm_provider": settings.llm_provider})
    yield
    logger.info("app stopping")


app = FastAPI(
    title="P-113 Pipeline Agent",
    description="Agent sinh và tối ưu pipeline ELT/ETL (dbt + Airflow), chạy thử trong sandbox DuckDB.",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(router, prefix="/api/v1")


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Dữ liệu gửi lên sai khuôn → 422 với thông báo tiếng Việt (kèm vị trí trường lỗi)."""
    fields = [".".join(str(p) for p in err.get("loc", [])[1:]) for err in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"detail": "Dữ liệu gửi lên không hợp lệ.", "fields": [f for f in fields if f]},
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Ranh giới cuối: ghi log đầy đủ, chỉ trả thông báo thân thiện (không lộ traceback)."""
    logger.exception("unhandled api error", extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"detail": "Có lỗi nội bộ. Vui lòng thử lại hoặc xem log máy chủ."})
