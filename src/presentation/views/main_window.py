"""Main application window for meloSync."""

from __future__ import annotations

from collections.abc import Callable
import logging

from PySide6.QtCore import QThreadPool, Qt, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.application.dto import (
    DownloadTrackCommand,
    SearchQueryDTO,
    SearchResultItemDTO,
    TrackDTO,
)
from src.application.use_cases import (
    DeleteTrackUseCase,
    DownloadAndProcessTrackUseCase,
    GetLibraryTracksUseCase,
    GetTrackByIdUseCase,
    SearchMetadataCandidatesUseCase,
    SearchYouTubeUseCase,
    UpdateTrackMetadataUseCase,
)
from src.domain.repositories import IUnitOfWork
from src.domain.services import IMetadataProviderService
from src.presentation.concurrency.workers import DownloadWorker, SearchWorker
from src.presentation.views.bottom_bar import BottomBarWidget
from src.presentation.views.downloads_view import DownloadsView
from src.presentation.views.library_view import LibraryView
from src.presentation.views.metadata_dialog import MetadataEditDialog
from src.presentation.views.search_view import SearchView
from src.presentation.views.sidebar import SidebarWidget

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """meloSync Primary GUI Window coordinating sidebar, views, and QThreadPool workers."""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        search_use_case: SearchYouTubeUseCase,
        download_use_case: DownloadAndProcessTrackUseCase,
        get_library_use_case: GetLibraryTracksUseCase,
        delete_track_use_case: DeleteTrackUseCase,
        get_track_by_id_use_case: GetTrackByIdUseCase,
        search_metadata_use_case: SearchMetadataCandidatesUseCase,
        update_metadata_use_case: UpdateTrackMetadataUseCase,
        metadata_provider: IMetadataProviderService,
        music_directory: str,
    ) -> None:
        super().__init__()
        self._uow_factory = uow_factory
        self._search_use_case = search_use_case
        self._download_use_case = download_use_case
        self._get_library_use_case = get_library_use_case
        self._delete_track_use_case = delete_track_use_case
        self._get_track_by_id_use_case = get_track_by_id_use_case
        self._search_metadata_use_case = search_metadata_use_case
        self._update_metadata_use_case = update_metadata_use_case
        self._metadata_provider = metadata_provider
        self._music_directory = music_directory
        self._thread_pool = QThreadPool.globalInstance()

        self._setup_window()
        self._setup_ui()
        self._connect_signals()

        # Load initial library tracks
        self.refresh_library()

    def _setup_window(self) -> None:
        self.setWindowTitle("meloSync — Gestor Inteligente de Música")
        self.resize(1140, 740)
        self.setMinimumSize(960, 620)

    def _setup_ui(self) -> None:
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar
        self.sidebar = SidebarWidget(music_directory=self._music_directory)
        root_layout.addWidget(self.sidebar)

        # 2. Main Content Area (Views + Persistent Bottom Bar)
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Central Stacked Views
        self.stacked_views = QStackedWidget()
        self.search_view = SearchView()
        self.library_view = LibraryView()
        self.downloads_view = DownloadsView()

        self.stacked_views.addWidget(self.search_view)      # Index 0
        self.stacked_views.addWidget(self.library_view)     # Index 1
        self.stacked_views.addWidget(self.downloads_view)   # Index 2

        content_layout.addWidget(self.stacked_views, stretch=1)

        # Persistent Bottom Bar
        self.bottom_bar = BottomBarWidget()
        content_layout.addWidget(self.bottom_bar)

        root_layout.addWidget(content_container, stretch=1)

    def _connect_signals(self) -> None:
        # Navigation
        self.sidebar.tab_changed.connect(self._on_tab_changed)

        # Search View
        self.search_view.search_requested.connect(self._on_search_requested)
        self.search_view.download_requested.connect(self._on_download_requested)

        # Library View
        self.library_view.refresh_requested.connect(self.refresh_library)
        self.library_view.delete_requested.connect(self._on_delete_requested)
        self.library_view.edit_requested.connect(self._on_edit_metadata_requested)

    # -------------------------------------------------------------------------
    # Navigation Slot
    # -------------------------------------------------------------------------
    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        self.stacked_views.setCurrentIndex(index)
        if index == 0:
            self.search_view._adjust_columns()
        elif index == 1:
            self.refresh_library()
            self.library_view._adjust_columns()
        elif index == 2:
            self.downloads_view._adjust_columns()

    # -------------------------------------------------------------------------
    # Search Async Slot
    # -------------------------------------------------------------------------
    @Slot(SearchQueryDTO)
    def _on_search_requested(self, query_dto: SearchQueryDTO) -> None:
        worker = SearchWorker(self._search_use_case, query_dto)
        worker.signals.results_ready.connect(self.search_view.set_results)
        worker.signals.error.connect(self.search_view.set_error)
        self._thread_pool.start(worker)

    # -------------------------------------------------------------------------
    # Download & Pipeline Async Slot
    # -------------------------------------------------------------------------
    @Slot(SearchResultItemDTO)
    def _on_download_requested(self, item: SearchResultItemDTO) -> None:
        command = DownloadTrackCommand(
            youtube_id=item.youtube_id,
            url=item.url,
            original_title=item.title,
            duration_seconds=item.duration_seconds,
            channel_name=item.channel_name,
        )

        # Notify UI Views of new job
        self.downloads_view.register_item(item.youtube_id, item.title)
        self.bottom_bar.on_job_added(item.title)

        # Create Worker and connect Qt signals
        worker = DownloadWorker(self._download_use_case, command)
        worker.signals.progress.connect(self._on_job_progress)
        worker.signals.finished.connect(self._on_job_finished)
        worker.signals.error.connect(self._on_job_error)

        self._thread_pool.start(worker)

    @Slot(object)
    def _on_job_progress(self, dto) -> None:
        self.downloads_view.update_progress(dto)
        self.bottom_bar.on_progress(dto)

    @Slot(object)
    def _on_job_finished(self, track_dto: TrackDTO) -> None:
        self.downloads_view.mark_completed(track_dto)
        self.bottom_bar.on_job_completed(track_dto)
        # Update library automatically so newly downloaded track appears
        self.refresh_library()

    @Slot(str, str)
    def _on_job_error(self, youtube_id: str, error_msg: str) -> None:
        self.downloads_view.mark_error(youtube_id, error_msg)
        self.bottom_bar.on_job_error(youtube_id, error_msg)

    # -------------------------------------------------------------------------
    # Library Slots
    # -------------------------------------------------------------------------
    @Slot()
    def refresh_library(self) -> None:
        """Fetches completed tracks and updates library table."""
        try:
            tracks = self._get_library_use_case.execute()
            self.library_view.set_tracks(tracks)
        except Exception as e:
            logger.error("Failed to refresh library: %s", e)

    @Slot(str)
    def _on_delete_requested(self, track_id: str) -> None:
        """Deletes track and updates library."""
        try:
            self._delete_track_use_case.execute(track_id, delete_file=True)
            self.refresh_library()
        except Exception as e:
            logger.error("Failed to delete track: %s", e)

    @Slot(str)
    def _on_edit_metadata_requested(self, track_id: str) -> None:
        """Opens the Apple Music metadata editor dialog for the specified track."""
        try:
            track = self._get_track_by_id_use_case.execute(track_id)
            if not track:
                return

            dialog = MetadataEditDialog(
                track=track,
                search_use_case=self._search_metadata_use_case,
                update_use_case=self._update_metadata_use_case,
                metadata_provider=self._metadata_provider,
                parent=self,
            )
            dialog.metadata_saved.connect(self._on_metadata_saved)
            dialog.exec()
        except Exception as e:
            logger.exception("Failed to open metadata edit dialog for track %s: %s", track_id, e)

    @Slot(object)
    def _on_metadata_saved(self, updated_track: TrackDTO) -> None:
        """Refreshes library and updates bottom status bar upon saving metadata."""
        self.refresh_library()
        self.bottom_bar.on_metadata_updated(updated_track)


