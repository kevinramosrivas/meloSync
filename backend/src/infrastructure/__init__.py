"""Infrastructure layer entrypoint."""

from .audio import FFmpegAudioProcessor, MutagenTaggingService
from .downloader import YtDlpAudioDownloader
from .metadata import ITunesMetadataProvider, RegexTitleCleaner
from .persistence import (
    DatabaseManager,
    SqlAlchemyPlaylistRepository,
    SqlAlchemySettingsRepository,
    SqlAlchemyTrackRepository,
    SqlAlchemyUnitOfWork,
)

__all__ = [
    "DatabaseManager",
    "FFmpegAudioProcessor",
    "ITunesMetadataProvider",
    "MutagenTaggingService",
    "RegexTitleCleaner",
    "SqlAlchemyPlaylistRepository",
    "SqlAlchemySettingsRepository",
    "SqlAlchemyTrackRepository",
    "SqlAlchemyUnitOfWork",
    "YtDlpAudioDownloader",
]
