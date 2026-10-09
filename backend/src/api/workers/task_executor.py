"""Background worker task executor for concurrent download processing."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Callable, Optional

from ...application.dto import DownloadTrackCommand
from ...application.use_cases import DownloadAndProcessTrackUseCase

logger = logging.getLogger(__name__)


class BackgroundDownloadExecutor:
    """Dispatches CPU/IO heavy yt-dlp & FFmpeg downloads to a worker thread pool."""

    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="meloSyncWorker")

    def submit_download(
        self,
        use_case: DownloadAndProcessTrackUseCase,
        command: DownloadTrackCommand,
        loop: asyncio.AbstractEventLoop,
    ) -> asyncio.Future:
        """Schedules download use case execution in the worker thread pool."""
        return loop.run_in_executor(
            self._executor,
            use_case.execute,
            command,
        )

    def shutdown(self) -> None:
        """Shuts down the executor pool."""
        self._executor.shutdown(wait=False)
