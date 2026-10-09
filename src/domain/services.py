"""Domain external service interfaces (Protocols/ABCs) for downloader, audio processor, metadata and tagging."""

from abc import ABC, abstractmethod
from typing import Callable, Optional

from src.domain.entities import AudioQuality, SearchResult, TrackMetadata


# Progress callback signature: (percent: float, speed_text: str, eta_text: str)
ProgressCallback = Callable[[float, str, str], None]


class IYouTubeSearchService(ABC):
    """Contract for searching YouTube videos and fetching video metadata."""

    @abstractmethod
    def search(self, query: str, max_results: int = 15) -> list[SearchResult]:
        """Performs a query search on YouTube and returns a list of results."""
        raise NotImplementedError

    @abstractmethod
    def get_info(self, url_or_id: str) -> Optional[SearchResult]:
        """Fetches metadata for a single YouTube video or URL."""
        raise NotImplementedError


class IAudioDownloaderService(ABC):
    """Contract for downloading raw audio streams from YouTube."""

    @abstractmethod
    def download(
        self,
        url: str,
        output_directory: str,
        quality: AudioQuality = AudioQuality.BEST,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """Downloads audio stream in best quality and returns the downloaded file path."""
        raise NotImplementedError


class IAudioProcessorService(ABC):
    """Contract for post-processing audio: loudness normalization and silence trimming."""

    @abstractmethod
    def normalize_and_trim(
        self,
        input_file_path: str,
        output_directory: str,
        target_loudness_lufs: float = -14.0,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> str:
        """Applies loudnorm and silenceremove filters and returns the processed audio path."""
        raise NotImplementedError


class IMetadataProviderService(ABC):
    """Contract for querying external metadata databases (iTunes Search API)."""

    @abstractmethod
    def lookup(self, query: str, artist: Optional[str] = None) -> Optional[TrackMetadata]:
        """Searches external database and returns highest match enriched metadata + high-res cover."""
        raise NotImplementedError

    @abstractmethod
    def search_candidates(self, query: str, limit: int = 15) -> list[TrackMetadata]:
        """Searches external database and returns a list of candidate matches with cover URLs."""
        raise NotImplementedError

    @abstractmethod
    def download_cover_bytes(self, cover_url: str) -> Optional[bytes]:
        """Downloads cover art image bytes from a remote URL."""
        raise NotImplementedError


class ITitleCleanerService(ABC):
    """Contract for cleaning dirty YouTube video titles using regex patterns."""

    @abstractmethod
    def clean(self, raw_title: str) -> tuple[str, str]:
        """Extracts (artist, clean_title) stripping noise such as 'Official Video', '4K', etc."""
        raise NotImplementedError


class ITaggingService(ABC):
    """Contract for writing ID3/MP4 metadata and cover artwork to audio files."""

    @abstractmethod
    def apply_tags(self, audio_file_path: str, metadata: TrackMetadata) -> None:
        """Embeds metadata tags and album art into the audio file."""
        raise NotImplementedError
