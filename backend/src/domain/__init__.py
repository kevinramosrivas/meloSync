"""meloSync Domain Layer."""

from .entities import (
    AppSettings,
    AudioQuality,
    DownloadStatus,
    Playlist,
    SearchResult,
    Track,
    TrackMetadata,
    get_default_music_dir,
    utc_now,
)
from .exceptions import (
    AudioProcessingException,
    DownloadException,
    InvalidStateTransitionException,
    MeloSyncDomainException,
    MetadataFetchException,
    PlaylistNotFoundException,
    TaggingException,
    TrackNotFoundException,
)
from .repositories import (
    IPlaylistRepository,
    ISettingsRepository,
    ITrackRepository,
    IUnitOfWork,
)
from .services import (
    IAudioDownloaderService,
    IAudioProcessorService,
    IMetadataProviderService,
    ITaggingService,
    ITitleCleanerService,
    IYouTubeSearchService,
    ProgressCallback,
)

__all__ = [
    "AppSettings",
    "AudioProcessingException",
    "AudioQuality",
    "DownloadException",
    "DownloadStatus",
    "IAudioDownloaderService",
    "IAudioProcessorService",
    "IMetadataProviderService",
    "IPlaylistRepository",
    "ISettingsRepository",
    "ITaggingService",
    "ITitleCleanerService",
    "ITrackRepository",
    "IUnitOfWork",
    "IYouTubeSearchService",
    "InvalidStateTransitionException",
    "MeloSyncDomainException",
    "MetadataFetchException",
    "Playlist",
    "PlaylistNotFoundException",
    "ProgressCallback",
    "SearchResult",
    "TaggingException",
    "Track",
    "TrackMetadata",
    "TrackNotFoundException",
    "get_default_music_dir",
    "utc_now",
]
