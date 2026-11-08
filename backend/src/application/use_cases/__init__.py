"""Application use cases module."""

from .download_and_process import (
    DownloadAndProcessTrackUseCase,
)
from .edit_metadata import (
    SearchMetadataCandidatesUseCase,
    UpdateTrackMetadataUseCase,
)
from .manage_library import (
    BatchDeleteTracksUseCase,
    DeleteTrackUseCase,
    GetLibraryTracksUseCase,
    GetTrackByIdUseCase,
)
from .manage_playlists import (
    AddTrackToPlaylistUseCase,
    AddTracksBatchToPlaylistUseCase,
    CreatePlaylistUseCase,
    DeletePlaylistUseCase,
    GetPlaylistByIdUseCase,
    GetPlaylistsGroupedUseCase,
    GetPlaylistsUseCase,
    RecordTrackPlayUseCase,
    RemoveTrackFromPlaylistUseCase,
    SyncSmartPlaylistsUseCase,
)
from .consolidate_library import ConsolidateLibraryUseCase, ConsolidateReportDTO
from .export_data import ExportBackupUseCase
from .import_data import ImportBackupUseCase
from .manage_settings import (
    GetSettingsUseCase,
    UpdateSettingsUseCase,
)
from .search_youtube import SearchYouTubeUseCase
from .sync_library import SyncLibraryUseCase, SyncReportDTO

__all__ = [
    "AddTrackToPlaylistUseCase",
    "ConsolidateLibraryUseCase",
    "ConsolidateReportDTO",
    "CreatePlaylistUseCase",
    "DeletePlaylistUseCase",
    "DeleteTrackUseCase",
    "DownloadAndProcessTrackUseCase",
    "ExportBackupUseCase",
    "GetLibraryTracksUseCase",
    "GetPlaylistByIdUseCase",
    "GetPlaylistsGroupedUseCase",
    "GetPlaylistsUseCase",
    "GetSettingsUseCase",
    "GetTrackByIdUseCase",
    "ImportBackupUseCase",
    "RecordTrackPlayUseCase",
    "RemoveTrackFromPlaylistUseCase",
    "SearchMetadataCandidatesUseCase",
    "SearchYouTubeUseCase",
    "SyncLibraryUseCase",
    "SyncReportDTO",
    "SyncSmartPlaylistsUseCase",
    "UpdateSettingsUseCase",
    "UpdateTrackMetadataUseCase",
]
