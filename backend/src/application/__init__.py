"""meloSync Application Layer."""

from .dto import (
    DownloadProgressDTO,
    DownloadTrackCommand,
    SearchResultDTO,
    SettingsDTO,
    TrackDTO,
    TrackMetadataDTO,
    UpdateSettingsCommand,
    UpdateTrackMetadataCommand,
)
from .events import ApplicationEvent, IEventPublisher
from .use_cases import (
    AddTrackToPlaylistUseCase,
    CreatePlaylistUseCase,
    DeleteTrackUseCase,
    DownloadAndProcessTrackUseCase,
    GetLibraryTracksUseCase,
    GetPlaylistsUseCase,
    GetSettingsUseCase,
    GetTrackByIdUseCase,
    SearchMetadataCandidatesUseCase,
    SearchYouTubeUseCase,
    UpdateSettingsUseCase,
    UpdateTrackMetadataUseCase,
)

__all__ = [
    "AddTrackToPlaylistUseCase",
    "ApplicationEvent",
    "CreatePlaylistUseCase",
    "DeleteTrackUseCase",
    "DownloadAndProcessTrackUseCase",
    "DownloadProgressDTO",
    "DownloadTrackCommand",
    "GetLibraryTracksUseCase",
    "GetPlaylistsUseCase",
    "GetSettingsUseCase",
    "GetTrackByIdUseCase",
    "IEventPublisher",
    "SearchResultDTO",
    "SearchMetadataCandidatesUseCase",
    "SearchYouTubeUseCase",
    "SettingsDTO",
    "TrackDTO",
    "TrackMetadataDTO",
    "UpdateSettingsCommand",
    "UpdateSettingsUseCase",
    "UpdateTrackMetadataCommand",
    "UpdateTrackMetadataUseCase",
]
