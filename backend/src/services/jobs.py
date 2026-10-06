"""Hàng đợi chạy nền cho API: graph chạy lâu (tới vài phút) nên API trả về ngay, web hỏi tiến trình định kỳ.

Các lần chạy được xếp hàng **lần lượt trên một luồng**: checkpointer SQLite dùng chung một kết nối nên không chạy
song song (đủ cho bản demo một DE). Tiến trình từng bước giữ trong bộ nhớ (mất khi khởi động lại; trạng thái và
kết quả vẫn nằm trong store/checkpointer).
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from functools import lru_cache

from src.agents.progress import StepEvent
from src.agents.runner import PermissionDeniedError, RunOutcome, RunStateError
from src.models.schemas import RunStatus
from src.services.store import get_store

logger = logging.getLogger(__name__)
EventSink = Callable[[StepEvent], None]
Job = Callable[[EventSink], RunOutcome]


class JobQueue:
    """Một luồng nền chạy graph; lưu sự kiện từng bước theo run_id."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="p113-run")
        self._lock = threading.Lock()
        self._events: dict[str, list[dict]] = {}
        self._futures: dict[str, Future] = {}

    def _record(self, run_id: str) -> EventSink:
        def sink(event: StepEvent) -> None:
            with self._lock:
                self._events.setdefault(run_id, []).append(event.model_dump())

        return sink

    def _run(self, run_id: str, job: Job) -> None:
        try:
            job(self._record(run_id))
        except (RunStateError, PermissionDeniedError) as exc:  # thao tác lặp (bấm 2 lần) hoặc trạng thái đã đổi
            logger.warning("job rejected", extra={"run_id": run_id, "error": str(exc)})
        except Exception:  # ranh giới luồng nền: không để luồng chết, đánh dấu lần chạy lỗi
            logger.exception("job crashed", extra={"run_id": run_id})
            record = get_store().get_run(run_id)
            summary = {**(record.summary if record else {}), "error": "Có lỗi nội bộ khi chạy nền. Xem log."}
            get_store().update_run(run_id, RunStatus.FAILED, summary)

    def submit(self, run_id: str, job: Job) -> None:
        """Đánh dấu đang chạy rồi đưa vào hàng đợi."""
        get_store().update_run(run_id, RunStatus.RUNNING)
        with self._lock:
            self._futures[run_id] = self._executor.submit(self._run, run_id, job)

    def events(self, run_id: str) -> list[dict]:
        """Các bước đã chạy của lần chạy (theo thứ tự)."""
        with self._lock:
            return list(self._events.get(run_id, []))

    def busy(self, run_id: str) -> bool:
        """Lần chạy đang chạy hoặc đang xếp hàng."""
        with self._lock:
            future = self._futures.get(run_id)
        return bool(future and not future.done())

    def wait(self, run_id: str, timeout: float = 600) -> None:
        """Chờ lần chạy xong (dùng cho test/CLI)."""
        with self._lock:
            future = self._futures.get(run_id)
        if future:
            future.result(timeout=timeout)


@lru_cache
def get_jobs() -> JobQueue:
    """Hàng đợi dùng chung của tiến trình API."""
    return JobQueue()
