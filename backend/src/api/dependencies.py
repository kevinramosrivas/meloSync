"""FastAPI Dependency Injection container and service factories."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Callable

from .websockets.connection_manager import WebSocketConnectionManager
from .websockets.events_router import ws_manager
from .workers.task_executor import BackgroundDownloadExecutor
from ..application.use_cases import (
    DeleteTrackUseCase,
    DownloadAndProcessTrackUseCase,
    GetLibraryTracksUseCase,
    GetSettingsUseCase,
    GetTrackByIdUseCase,
    SearchMetadataCandidatesUseCase,
    SearchYouTubeUseCase,
    SyncLibraryUseCase,
    UpdateSettingsUseCase,
    UpdateTrackMetadataUseCase,
)
from ..domain.repositories import IUnitOfWork
from ..infrastructure.audio import FFmpegAudioProcessor, MutagenTaggingService
from ..infrastructure.downloader import YtDlpAudioDownloader
from ..infrastructure.metadata import ITunesMetadataProvider, RegexTitleCleaner
from ..infrastructure.persistence import DatabaseManager, SqlAlchemyUnitOfWork


class Container:
    """Dependency Injection Container holding application singletons."""

    def __init__(self) -> None:
        home_dir = Path.home()
        app_data_dir = home_dir / ".melosync"
        app_data_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(app_data_dir / "melosync.db")

        # Infrastructure
        self.db_manager = DatabaseManager(db_path=db_path)
        self.db_manager.init_database()

        self.downloader = YtDlpAudioDownloader()
        self.audio_processor = FFmpegAudioProcessor()
        self.metadata_provider = ITunesMetadataProvider()
        self.title_cleaner = RegexTitleCleaner()
        self.tagging_service = MutagenTaggingService()

        # WebSockets & Worker Pool
        self.ws_manager: WebSocketConnectionManager = ws_manager
        self.task_executor = BackgroundDownloadExecutor(max_workers=4)

    def uow_factory(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.db_manager)

    # Use cases
    def get_search_use_case(self) -> SearchYouTubeUseCase:
        return SearchYouTubeUseCase(search_service=self.downloader)

    def get_download_use_case(self) -> DownloadAndProcessTrackUseCase:
        return DownloadAndProcessTrackUseCase(
            uow_factory=self.uow_factory,
            downloader_service=self.downloader,
            audio_processor=self.audio_processor,
            metadata_provider=self.metadata_provider,
            title_cleaner=self.title_cleaner,
            tagging_service=self.tagging_service,
            event_publisher=self.ws_manager,
        )

    def get_library_use_case(self) -> GetLibraryTracksUseCase:
        return GetLibraryTracksUseCase(uow_factory=self.uow_factory)

    def get_track_by_id_use_case(self) -> GetTrackByIdUseCase:
        return GetTrackByIdUseCase(uow_factory=self.uow_factory)

    def get_delete_track_use_case(self) -> DeleteTrackUseCase:
        return DeleteTrackUseCase(uow_factory=self.uow_factory)

    def get_search_metadata_use_case(self) -> SearchMetadataCandidatesUseCase:
        return SearchMetadataCandidatesUseCase(metadata_provider=self.metadata_provider)

    def get_update_metadata_use_case(self) -> UpdateTrackMetadataUseCase:
        return UpdateTrackMetadataUseCase(
            uow_factory=self.uow_factory,
            metadata_provider=self.metadata_provider,
            tagging_service=self.tagging_service,
        )

    def get_settings_use_case(self) -> GetSettingsUseCase:
        return GetSettingsUseCase(uow_factory=self.uow_factory)

    def get_update_settings_use_case(self) -> UpdateSettingsUseCase:
        return UpdateSettingsUseCase(uow_factory=self.uow_factory)

    def get_sync_library_use_case(self) -> SyncLibraryUseCase:
        return SyncLibraryUseCase(uow_factory=self.uow_factory)

    # Playlist use cases
    def get_create_playlist_use_case(self) -> CreatePlaylistUseCase:
        from ..application.use_cases.manage_playlists import CreatePlaylistUseCase
        return CreatePlaylistUseCase(uow_factory=self.uow_factory)

    def get_playlists_grouped_use_case(self) -> GetPlaylistsGroupedUseCase:
        from ..application.use_cases.manage_playlists import GetPlaylistsGroupedUseCase
        return GetPlaylistsGroupedUseCase(uow_factory=self.uow_factory)

    def get_playlist_by_id_use_case(self) -> GetPlaylistByIdUseCase:
        from ..application.use_cases.manage_playlists import GetPlaylistByIdUseCase
        return GetPlaylistByIdUseCase(
            uow_factory=self.uow_factory,
            itunes_provider=self.metadata_provider,
        )

    def get_update_playlist_use_case(self) -> UpdatePlaylistUseCase:
        from ..application.use_cases.manage_playlists import UpdatePlaylistUseCase
        return UpdatePlaylistUseCase(uow_factory=self.uow_factory)

    def get_delete_playlist_use_case(self) -> DeletePlaylistUseCase:
        from ..application.use_cases.manage_playlists import DeletePlaylistUseCase
        return DeletePlaylistUseCase(uow_factory=self.uow_factory)

    def get_add_track_to_playlist_use_case(self) -> AddTrackToPlaylistUseCase:
        from ..application.use_cases.manage_playlists import AddTrackToPlaylistUseCase
        return AddTrackToPlaylistUseCase(uow_factory=self.uow_factory)

    def get_remove_track_from_playlist_use_case(self) -> RemoveTrackFromPlaylistUseCase:
        from ..application.use_cases.manage_playlists import RemoveTrackFromPlaylistUseCase
        return RemoveTrackFromPlaylistUseCase(uow_factory=self.uow_factory)

    def get_record_track_play_use_case(self) -> RecordTrackPlayUseCase:
        from ..application.use_cases.manage_playlists import RecordTrackPlayUseCase
        return RecordTrackPlayUseCase(uow_factory=self.uow_factory)

    def get_sync_smart_playlists_use_case(self) -> SyncSmartPlaylistsUseCase:
        from ..application.use_cases.manage_playlists import SyncSmartPlaylistsUseCase
        return SyncSmartPlaylistsUseCase(
            uow_factory=self.uow_factory,
            itunes_provider=self.metadata_provider,
        )


@lru_cache(maxsize=1)
def get_container() -> Container:
    """Returns application dependency container singleton."""
    return Container()
