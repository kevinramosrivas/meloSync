"""Pydantic schemas for API request and response validation."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

from ...domain.entities import AudioQuality, DownloadStatus


# Search Schemas
class SearchResultResponse(BaseModel):
    youtube_id: str
    title: str
    duration_seconds: int
    duration_formatted: str
    channel_name: str
    thumbnail_url: str
    url: str

    @classmethod
    def from_dto(cls, dto: Any) -> SearchResultResponse:
        return cls(
            youtube_id=dto.youtube_id,
            title=dto.title,
            duration_seconds=dto.duration_seconds,
            duration_formatted=dto.duration_formatted,
            channel_name=dto.channel_name,
            thumbnail_url=dto.thumbnail_url,
            url=dto.url,
        )


# Download Schemas
class DownloadRequest(BaseModel):
    youtube_id: str
    url: str
    original_title: str
    duration_seconds: int = 0
    channel_name: str = ""
    quality: AudioQuality = AudioQuality.BEST


class DownloadProgressResponse(BaseModel):
    track_id: str
    youtube_id: str
    status: DownloadStatus
    progress_percent: float
    stage_description: str
    speed_text: str = ""
    eta_text: str = ""


# Metadata Schemas
class TrackMetadataResponse(BaseModel):
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
    def from_dto(cls, dto: Any) -> Optional[TrackMetadataResponse]:
        if not dto:
            return None
        return cls(
            title=dto.title,
            artist=dto.artist,
            album=dto.album,
            year=dto.year,
            genre=dto.genre,
            track_number=dto.track_number,
            disc_number=getattr(dto, "disc_number", None),
            cover_url=dto.cover_url,
            has_cover_bytes=getattr(dto, "has_cover_bytes", False),
            lyrics=getattr(dto, "lyrics", None),
        )


class UpdateMetadataRequest(BaseModel):
    title: str
    artist: str
    album: str
    year: Optional[int] = None
    genre: Optional[str] = None
    track_number: Optional[int] = None
    cover_url: Optional[str] = None


# Track Schemas
class TrackResponse(BaseModel):
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
    file_exists: bool = True
    error_message: Optional[str] = None
    metadata: Optional[TrackMetadataResponse] = None
    created_at_iso: str = ""
    updated_at_iso: str = ""

    @classmethod
    def from_dto(cls, dto: Any) -> TrackResponse:
        file_exists = True
        if dto.status == DownloadStatus.COMPLETADA:
            file_exists = bool(dto.file_path and Path(dto.file_path).exists())

        return cls(
            id=dto.id,
            youtube_id=dto.youtube_id,
            url=dto.url,
            original_title=dto.original_title,
            display_title=dto.display_title,
            display_artist=dto.display_artist,
            display_album=dto.display_album,
            duration_seconds=dto.duration_seconds,
            duration_formatted=dto.duration_formatted,
            channel_name=dto.channel_name,
            status=dto.status,
            progress_percent=dto.progress_percent,
            file_path=dto.file_path,
            file_exists=file_exists,
            error_message=dto.error_message,
            metadata=TrackMetadataResponse.from_dto(dto.metadata),
            created_at_iso=dto.created_at_iso,
            updated_at_iso=dto.updated_at_iso,
        )


class SyncLibraryResponse(BaseModel):
    repaired_count: int
    imported_count: int
    missing_count: int
    total_tracks: int
    message: str


# Settings Schemas
class SettingsResponse(BaseModel):
    music_download_directory: str
    default_audio_quality: AudioQuality
    normalize_audio_lufs: float
    auto_tag_metadata: bool

    @classmethod
    def from_dto(cls, dto: Any) -> SettingsResponse:
        return cls(
            music_download_directory=dto.music_download_directory,
            default_audio_quality=dto.default_audio_quality,
            normalize_audio_lufs=dto.normalize_audio_lufs,
            auto_tag_metadata=dto.auto_tag_metadata,
        )


class UpdateSettingsRequest(BaseModel):
    music_download_directory: str
    default_audio_quality: AudioQuality = AudioQuality.BEST
    normalize_audio_lufs: float = -14.0
    auto_tag_metadata: bool = True
