"""Bật/tắt LangSmith an toàn: chỉ bật khi có khóa thật, tránh lỗi 403 làm ồn terminal."""

import logging
import os

from src.config import get_settings

logger = logging.getLogger(__name__)
TRACING_VARS = ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING")


def configure_tracing() -> str:
    """Tắt tracing nếu đang bật mà chưa có khóa thật; trả về cảnh báo (rỗng nếu không có gì)."""
    settings = get_settings()
    enabled = settings.langchain_tracing_v2 or os.environ.get("LANGSMITH_TRACING", "").lower() == "true"
    if not enabled or settings.has_langsmith_key:
        return ""
    for name in TRACING_VARS:
        os.environ[name] = "false"
    return "LangSmith đang bật nhưng chưa có khóa thật nên đã tạm tắt. Đặt LANGCHAIN_TRACING_V2=false trong .env để ẩn cảnh báo này."
