"""Application layer Data Transfer Objects (DTOs) and command objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.domain.entities import AudioQuality, DownloadStatus, Track


@dataclass(slots=True)
class SearchQueryDTO:
    """Input query parameters for searching YouTube."""
    query: str
    max_results: int = 15


@dataclass(slots=True)
class SearchResultItemDTO:
    """Presentation-ready YouTube search item."""
    youtube_id: str
    title: str
    duration_seconds: int
    duration_formatted: str
    channel_name: str
    thumbnail_url: str
    url: str


@dataclass(slots=True)
class DownloadTrackCommand:
    """Command requesting the download and processing of a specific track."""
    youtube_id: str
    url: str
    original_title: str
    duration_seconds: int = 0
    channel_name: str = ""
    custom_artist: Optional[str] = None
    custom_title: Optional[str] = None
    quality: AudioQuality = AudioQuality.BEST


@dataclass(slots=True)
class DownloadProgressDTO:
    """Progress event payload emitted during the multi-stage pipeline."""
    track_id: str
    youtube_id: str
    status: DownloadStatus
    progress_percent: float
    stage_description: str
    speed_text: str = ""
    eta_text: str = ""


@dataclass(slots=True)
class TrackDTO:
    """Read model representation of a Track for Presentation consumption."""
    id: str
    youtube_id: str
    title: str
    artist: str
    album: str
    duration_seconds: int
    duration_formatted: str
    status: str
    progress_percent: float
    file_path: Optional[str]
    cover_url: Optional[str]
    error_message: Optional[str]
    created_at_iso: str

    @classmethod
    def from_entity(cls, track: Track) -> TrackDTO:
        """Converts a domain Track entity to a presentation TrackDTO."""
        return cls(
            id=track.id,
            youtube_id=track.youtube_id,
            title=track.display_title,
            artist=track.display_artist,
            album=track.display_album,
            duration_seconds=track.duration_seconds,
            duration_formatted=track.duration_formatted,
            status=track.status.value,
            progress_percent=track.progress_percent,
            file_path=track.file_path,
            cover_url=track.metadata.cover_url if track.metadata else None,
            error_message=track.error_message,
            created_at_iso=track.created_at.isoformat(),
        )


@dataclass(slots=True)
class MetadataCandidateDTO:
    """Apple Music candidate item for metadata selection."""
    title: str
    artist: str
    album: str
    year: Optional[int] = None
    genre: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    cover_url: Optional[str] = None
    thumbnail_url: Optional[str] = None


@dataclass(slots=True)
class UpdateTrackMetadataCommand:
    """Command to update track metadata, re-embed tags/artwork, and update database."""
    track_id: str
    title: str
    artist: str
    album: str = "Unknown Album"
    year: Optional[int] = None
    genre: Optional[str] = None
    track_number: Optional[int] = None
    cover_url: Optional[str] = None
    cover_bytes: Optional[bytes] = None
    rename_file: bool = True
