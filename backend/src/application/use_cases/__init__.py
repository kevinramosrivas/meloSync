"""Application use cases module."""

from .download_and_process import (
    DownloadAndProcessTrackUseCase,
)
from .edit_metadata import (
    SearchMetadataCandidatesUseCase,
    UpdateTrackMetadataUseCase,
)
from .manage_library import (
    DeleteTrackUseCase,
    GetLibraryTracksUseCase,
    GetTrackByIdUseCase,
)
from .manage_playlists import (
    AddTrackToPlaylistUseCase,
    CreatePlaylistUseCase,
    DeletePlaylistUseCase,
    GetPlaylistByIdUseCase,
    GetPlaylistsGroupedUseCase,
    GetPlaylistsUseCase,
    RecordTrackPlayUseCase,
    RemoveTrackFromPlaylistUseCase,
    SyncSmartPlaylistsUseCase,
)
from .manage_settings import (
    GetSettingsUseCase,
    UpdateSettingsUseCase,
)
from .search_youtube import SearchYouTubeUseCase
from .sync_library import SyncLibraryUseCase, SyncReportDTO

__all__ = [
    "AddTrackToPlaylistUseCase",
    "CreatePlaylistUseCase",
    "DeletePlaylistUseCase",
    "DeleteTrackUseCase",
    "DownloadAndProcessTrackUseCase",
    "GetLibraryTracksUseCase",
    "GetPlaylistByIdUseCase",
    "GetPlaylistsGroupedUseCase",
    "GetPlaylistsUseCase",
    "GetSettingsUseCase",
    "GetTrackByIdUseCase",
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
