"""Background worker task executor for concurrent download processing."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import threading
from typing import Callable, Optional

from ...application.dto import DownloadTrackCommand
from ...application.use_cases import DownloadAndProcessTrackUseCase
from ...domain.exceptions import DownloadCancelledException

logger = logging.getLogger(__name__)


class BackgroundDownloadExecutor:
    """Dispatches CPU/IO heavy yt-dlp & FFmpeg downloads to a worker thread pool."""

    def __init__(self, max_workers: int = 4) -> None:
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="meloSyncWorker")
        self._lock = threading.Lock()
        self._cancelled_track_ids: set[str] = set()
        self._cancelled_youtube_ids: set[str] = set()

    def _ensure_executor(self) -> ThreadPoolExecutor:
        with self._lock:
            if getattr(self._executor, "_shutdown", False):
                self._executor = ThreadPoolExecutor(max_workers=self._max_workers, thread_name_prefix="meloSyncWorker")
            return self._executor

    def request_cancel(self, track_id: Optional[str] = None, youtube_id: Optional[str] = None) -> None:
        """Flags an ongoing or queued download for cancellation."""
        with self._lock:
            if track_id:
                self._cancelled_track_ids.add(track_id)
            if youtube_id:
                self._cancelled_youtube_ids.add(youtube_id)
        logger.info("Cancellation requested for track_id=%s, youtube_id=%s", track_id, youtube_id)

    def clear_cancel_flag(self, track_id: Optional[str] = None, youtube_id: Optional[str] = None) -> None:
        """Clears cancellation flag (e.g. when retrying or starting a download)."""
        with self._lock:
            if track_id:
                self._cancelled_track_ids.discard(track_id)
            if youtube_id:
                self._cancelled_youtube_ids.discard(youtube_id)

    def is_cancelled(self, track_id: Optional[str] = None, youtube_id: Optional[str] = None) -> bool:
        """Checks if a download task has been requested to cancel."""
        with self._lock:
            if track_id and track_id in self._cancelled_track_ids:
                return True
            if youtube_id and youtube_id in self._cancelled_youtube_ids:
                return True
            return False

    def submit_download(
        self,
        use_case: DownloadAndProcessTrackUseCase,
        command: DownloadTrackCommand,
        loop: asyncio.AbstractEventLoop,
        on_success: Optional[Callable[[], None]] = None,
    ) -> asyncio.Future:
        """Schedules download use case execution in the worker thread pool."""
        cancel_check = lambda: self.is_cancelled(youtube_id=command.youtube_id)

        executor = self._ensure_executor()
        fut = loop.run_in_executor(
            executor,
            lambda: use_case.execute(command, cancel_check=cancel_check),
        )

        def _handle_completion(f: asyncio.Future) -> None:
            try:
                f.result()
                if on_success:
                    try:
                        on_success()
                    except Exception as se:
                        logger.warning("Background on_success callback failed: %s", se)
            except DownloadCancelledException:
                logger.info("Background download task cancelled for %s", command.youtube_id)
            except Exception as e:
                logger.error("Background download task failed for %s: %s", command.youtube_id, e, exc_info=True)
            finally:
                self.clear_cancel_flag(youtube_id=command.youtube_id)

        fut.add_done_callback(_handle_completion)
        return fut

    def shutdown(self) -> None:
        """Shuts down the executor pool."""
        self._executor.shutdown(wait=False)

