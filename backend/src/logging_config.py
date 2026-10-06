"""Structured logging (JSON) cho API và CLI."""

import json
import logging
import sys
from datetime import UTC, datetime

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}


class JSONFormatter(logging.Formatter):
    """Ghi mỗi dòng log thành một object JSON (dễ tìm kiếm, dễ đưa vào công cụ giám sát)."""

    def format(self, record: logging.LogRecord) -> str:
        """Chuyển LogRecord thành chuỗi JSON, giữ các trường `extra`."""
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Cấu hình root logger ghi JSON ra stderr. Gọi một lần lúc khởi động."""
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")  # terminal Windows mặc định cp1252
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
