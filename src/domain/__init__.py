"""Domain layer: Core business entities, enums, exceptions and interfaces.

Zero external dependencies to frameworks (PySide6, SQLAlchemy, yt-dlp).
"""

from src.domain.entities import (
    AudioQuality,
    DownloadStatus,
    Playlist,
    SearchResult,
    Track,
    TrackMetadata,
)
from src.domain.exceptions import (
    AudioProcessingException,
    DomainException,
    DownloadException,
    EntityNotFoundException,
    InvalidStateTransitionException,
    MetadataFetchException,
    TaggingException,
)
from src.domain.repositories import (
    IPlaylistRepository,
    ITrackRepository,
    IUnitOfWork,
)
from src.domain.services import (
    IAudioDownloaderService,
    IAudioProcessorService,
    IMetadataProviderService,
    ITaggingService,
    ITitleCleanerService,
    IYouTubeSearchService,
)

__all__ = [
    "AudioQuality",
    "DownloadStatus",
    "Playlist",
    "SearchResult",
    "Track",
    "TrackMetadata",
    "DomainException",
    "EntityNotFoundException",
    "InvalidStateTransitionException",
    "DownloadException",
    "AudioProcessingException",
    "MetadataFetchException",
    "TaggingException",
    "ITrackRepository",
    "IPlaylistRepository",
    "IUnitOfWork",
    "IYouTubeSearchService",
    "IAudioDownloaderService",
    "IAudioProcessorService",
    "IMetadataProviderService",
    "ITaggingService",
    "ITitleCleanerService",
]
