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
    GetPlaylistsUseCase,
)
from .manage_settings import (
    GetSettingsUseCase,
    UpdateSettingsUseCase,
)
from .search_youtube import SearchYouTubeUseCase

__all__ = [
    "AddTrackToPlaylistUseCase",
    "CreatePlaylistUseCase",
    "DeleteTrackUseCase",
    "DownloadAndProcessTrackUseCase",
    "GetLibraryTracksUseCase",
    "GetPlaylistsUseCase",
    "GetSettingsUseCase",
    "GetTrackByIdUseCase",
    "SearchMetadataCandidatesUseCase",
    "SearchYouTubeUseCase",
    "UpdateSettingsUseCase",
    "UpdateTrackMetadataUseCase",
]
