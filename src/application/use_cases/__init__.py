"""Application use cases package."""

from src.application.use_cases.download_and_process import DownloadAndProcessTrackUseCase
from src.application.use_cases.edit_metadata import (
    SearchMetadataCandidatesUseCase,
    UpdateTrackMetadataUseCase,
)
from src.application.use_cases.manage_library import (
    DeleteTrackUseCase,
    GetLibraryTracksUseCase,
    GetTrackByIdUseCase,
)
from src.application.use_cases.manage_playlists import (
    AddTrackToPlaylistUseCase,
    CreatePlaylistUseCase,
    GetPlaylistsUseCase,
)
from src.application.use_cases.search_youtube import SearchYouTubeUseCase

__all__ = [
    "SearchYouTubeUseCase",
    "DownloadAndProcessTrackUseCase",
    "GetLibraryTracksUseCase",
    "DeleteTrackUseCase",
    "GetTrackByIdUseCase",
    "CreatePlaylistUseCase",
    "AddTrackToPlaylistUseCase",
    "GetPlaylistsUseCase",
    "SearchMetadataCandidatesUseCase",
    "UpdateTrackMetadataUseCase",
]
