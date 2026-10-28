"""Data Transfer Objects (DTOs) and Commands for use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..domain.entities import (
    AppSettings,
    AudioQuality,
    DownloadStatus,
    SearchResult,
    Track,
    TrackMetadata,
)


@dataclass(slots=True, frozen=True)
class TrackMetadataDTO:
    """DTO representing enriched track metadata."""
    title: str
    artist: str
    album: str = "Unknown Album"
    year: Optional[int] = None
    genre: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    cover_url: Optional[str] = None
    has_cover_bytes: bool = False
    lyrics: Optional[str] = None

    @classmethod
    def from_domain(cls, meta: Optional[TrackMetadata]) -> Optional[TrackMetadataDTO]:
        if not meta:
            return None
        return cls(
            title=meta.title,
            artist=meta.artist,
            album=meta.album,
            year=meta.year,
            genre=meta.genre,
            track_number=meta.track_number,
            disc_number=meta.disc_number,
            cover_url=meta.cover_url,
            has_cover_bytes=bool(meta.cover_bytes),
            lyrics=meta.lyrics,
        )


@dataclass(slots=True, frozen=True)
class TrackDTO:
    """DTO representing full Track state for presentation layer."""
    id: str
    youtube_id: str
    url: str
    original_title: str
    display_title: str
    display_artist: str
    display_album: str
    duration_seconds: int
    duration_formatted: str
    channel_name: str
    status: DownloadStatus
    progress_percent: float
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[TrackMetadataDTO] = None
    play_count: int = 0
    last_played_at_iso: Optional[str] = None
    created_at_iso: str = ""
    updated_at_iso: str = ""

    @classmethod
    def from_domain(cls, track: Track) -> TrackDTO:
        return cls(
            id=track.id,
            youtube_id=track.youtube_id,
            url=track.url,
            original_title=track.original_title,
            display_title=track.display_title,
            display_artist=track.display_artist,
            display_album=track.display_album,
            duration_seconds=track.duration_seconds,
            duration_formatted=track.duration_formatted,
            channel_name=track.channel_name,
            status=track.status,
            progress_percent=track.progress_percent,
            file_path=track.file_path,
            error_message=track.error_message,
            metadata=TrackMetadataDTO.from_domain(track.metadata),
            play_count=track.play_count,
            last_played_at_iso=track.last_played_at.isoformat() if track.last_played_at else None,
            created_at_iso=track.created_at.isoformat(),
            updated_at_iso=track.updated_at.isoformat(),
        )


@dataclass(slots=True, frozen=True)
class SearchResultDTO:
    """DTO representing YouTube search query match."""
    youtube_id: str
    title: str
    duration_seconds: int
    duration_formatted: str
    channel_name: str
    thumbnail_url: str
    url: str

    @classmethod
    def from_domain(cls, r: SearchResult) -> SearchResultDTO:
        return cls(
            youtube_id=r.youtube_id,
            title=r.title,
            duration_seconds=r.duration_seconds,
            duration_formatted=r.duration_formatted,
            channel_name=r.channel_name,
            thumbnail_url=r.thumbnail_url,
            url=r.url,
        )


@dataclass(slots=True, frozen=True)
class DownloadProgressDTO:
    """DTO for broadcasting live download pipeline progress to UI/WebSockets."""
    track_id: str
    youtube_id: str
    status: DownloadStatus
    progress_percent: float
    stage_description: str
    speed_text: str = ""
    eta_text: str = ""


@dataclass(slots=True, frozen=True)
class DownloadTrackCommand:
    """Command requesting track download and processing."""
    youtube_id: str
    url: str
    original_title: str
    duration_seconds: int = 0
    channel_name: str = ""
    custom_output_dir: Optional[str] = None
    custom_quality: AudioQuality = AudioQuality.BEST


@dataclass(slots=True, frozen=True)
class UpdateTrackMetadataCommand:
    """Command requesting manual update of a track's metadata and re-tagging."""
    track_id: str
    title: str
    artist: str
    album: str
    year: Optional[int] = None
    genre: Optional[str] = None
    track_number: Optional[int] = None
    cover_url: Optional[str] = None
    cover_bytes: Optional[bytes] = None


@dataclass(slots=True, frozen=True)
class SettingsDTO:
    """DTO representing global application settings."""
    music_download_directory: str
    default_audio_quality: AudioQuality
    normalize_audio_lufs: float
    auto_tag_metadata: bool

    @classmethod
    def from_domain(cls, s: AppSettings) -> SettingsDTO:
        return cls(
            music_download_directory=s.music_download_directory,
            default_audio_quality=s.default_audio_quality,
            normalize_audio_lufs=s.normalize_audio_lufs,
            auto_tag_metadata=s.auto_tag_metadata,
        )


@dataclass(slots=True, frozen=True)
class UpdateSettingsCommand:
    """Command requesting update of application settings."""
    music_download_directory: str
    default_audio_quality: AudioQuality = AudioQuality.BEST
    normalize_audio_lufs: float = -14.0
    auto_tag_metadata: bool = True
