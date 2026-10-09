"""QRunnable workers executing domain use cases on QThreadPool without blocking the GUI."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QRunnable, Slot

from src.application.dto import (
    DownloadTrackCommand,
    MetadataCandidateDTO,
    SearchQueryDTO,
    UpdateTrackMetadataCommand,
)
from src.application.use_cases.download_and_process import DownloadAndProcessTrackUseCase
from src.application.use_cases.edit_metadata import (
    SearchMetadataCandidatesUseCase,
    UpdateTrackMetadataUseCase,
)
from src.application.use_cases.search_youtube import SearchYouTubeUseCase
from src.domain.services import IMetadataProviderService
from src.presentation.concurrency.signals import (
    CoverDownloadSignals,
    DownloadWorkerSignals,
    MetadataSearchWorkerSignals,
    SearchWorkerSignals,
    UpdateMetadataWorkerSignals,
)

logger = logging.getLogger(__name__)


class DownloadWorker(QRunnable):
    """Executes the download, ffmpeg audio pipeline and metadata tagging in QThreadPool."""

    def __init__(
        self,
        use_case: DownloadAndProcessTrackUseCase,
        command: DownloadTrackCommand,
    ) -> None:
        super().__init__()
        self.use_case = use_case
        self.command = command
        self.signals = DownloadWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Worker thread entrypoint."""
        try:
            try:
                self.signals.started.emit(self.command.youtube_id)
            except RuntimeError:
                return

            def on_progress(dto) -> None:
                try:
                    self.signals.progress.emit(dto)
                except RuntimeError:
                    pass

            result = self.use_case.execute(self.command, progress_callback=on_progress)
            try:
                self.signals.finished.emit(result)
            except RuntimeError:
                pass

        except Exception as exc:
            logger.exception("DownloadWorker failed for '%s': %s", self.command.youtube_id, exc)
            try:
                self.signals.error.emit(self.command.youtube_id, str(exc))
            except RuntimeError:
                pass


class SearchWorker(QRunnable):
    """Executes YouTube queries asynchronously on QThreadPool."""

    def __init__(
        self,
        use_case: SearchYouTubeUseCase,
        query_dto: SearchQueryDTO,
    ) -> None:
        super().__init__()
        self.use_case = use_case
        self.query_dto = query_dto
        self.signals = SearchWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Worker thread entrypoint."""
        try:
            try:
                self.signals.started.emit()
            except RuntimeError:
                return
            results = self.use_case.execute(self.query_dto)
            try:
                self.signals.results_ready.emit(results)
            except RuntimeError:
                pass
        except Exception as exc:
            logger.exception("SearchWorker failed for query '%s': %s", self.query_dto.query, exc)
            try:
                self.signals.error.emit(str(exc))
            except RuntimeError:
                pass


class MetadataCandidateSearchWorker(QRunnable):
    """Executes Apple Music candidate queries asynchronously on QThreadPool."""

    def __init__(
        self,
        use_case: SearchMetadataCandidatesUseCase,
        query: str,
        limit: int = 15,
        search_id: int = 0,
    ) -> None:
        super().__init__()
        self.use_case = use_case
        self.query = query
        self.limit = limit
        self.search_id = search_id
        self.signals = MetadataSearchWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Worker thread entrypoint."""
        try:
            try:
                self.signals.started.emit(self.search_id)
            except RuntimeError:
                return

            results = self.use_case.execute(self.query, limit=self.limit)
            try:
                self.signals.results_ready.emit(self.search_id, results)
            except RuntimeError:
                pass
        except Exception as exc:
            logger.exception("MetadataCandidateSearchWorker failed for '%s': %s", self.query, exc)
            try:
                self.signals.error.emit(self.search_id, str(exc))
            except RuntimeError:
                pass


class CoverDownloadWorker(QRunnable):
    """Downloads HD cover artwork image bytes asynchronously."""

    def __init__(
        self,
        metadata_provider: IMetadataProviderService,
        cover_url: str,
    ) -> None:
        super().__init__()
        self.metadata_provider = metadata_provider
        self.cover_url = cover_url
        self.signals = CoverDownloadSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Worker thread entrypoint."""
        try:
            try:
                self.signals.started.emit(self.cover_url)
            except RuntimeError:
                return

            cover_bytes = self.metadata_provider.download_cover_bytes(self.cover_url)
            if cover_bytes:
                try:
                    self.signals.cover_ready.emit(self.cover_url, cover_bytes)
                except RuntimeError:
                    pass
            else:
                try:
                    self.signals.error.emit(self.cover_url, "No se pudo descargar la imagen de la carátula.")
                except RuntimeError:
                    pass
        except Exception as exc:
            logger.exception("CoverDownloadWorker failed for '%s': %s", self.cover_url, exc)
            try:
                self.signals.error.emit(self.cover_url, str(exc))
            except RuntimeError:
                pass


class UpdateMetadataWorker(QRunnable):
    """Executes metadata updates and audio tagging in the background."""

    def __init__(
        self,
        use_case: UpdateTrackMetadataUseCase,
        command: UpdateTrackMetadataCommand,
    ) -> None:
        super().__init__()
        self.use_case = use_case
        self.command = command
        self.signals = UpdateMetadataWorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Worker thread entrypoint."""
        try:
            try:
                self.signals.started.emit(self.command.track_id)
            except RuntimeError:
                return

            updated_dto = self.use_case.execute(self.command)
            try:
                self.signals.finished.emit(updated_dto)
            except RuntimeError:
                pass
        except Exception as exc:
            logger.exception("UpdateMetadataWorker failed for track '%s': %s", self.command.track_id, exc)
            try:
                self.signals.error.emit(self.command.track_id, str(exc))
            except RuntimeError:
                pass
