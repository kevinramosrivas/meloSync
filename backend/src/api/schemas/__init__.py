"""Pydantic schemas for API request and response validation."""

from __future__ import annotations

from pathlib import Path
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
            has_cover_bytes=getattr(dto, "has_cover_bytes", False) or bool(getattr(dto, "cover_bytes", None)),
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
    is_in_active_directory: bool = True
    error_message: Optional[str] = None
    metadata: Optional[TrackMetadataResponse] = None
    play_count: int = 0
    last_played_at_iso: Optional[str] = None
    created_at_iso: str = ""
    updated_at_iso: str = ""

    @classmethod
    def from_dto(cls, dto: Any, active_dir: Optional[Path] = None) -> TrackResponse:
        file_exists = True
        is_in_active_directory = True

        if dto.status == DownloadStatus.COMPLETADA:
            if dto.file_path:
                try:
                    p = Path(dto.file_path)
                    file_exists = p.is_file()
                    if active_dir and file_exists:
                        p_res = p.resolve()
                        is_in_active_directory = (p_res.parent == active_dir or p_res.is_relative_to(active_dir))
                except Exception:
                    file_exists = False
                    is_in_active_directory = False
            else:
                file_exists = False
                is_in_active_directory = False

        # Support both TrackDTO (created_at_iso) and domain Track (created_at datetime)
        created_at_val = getattr(dto, "created_at_iso", None)
        if not created_at_val:
            raw_created = getattr(dto, "created_at", None)
            created_at_val = raw_created.isoformat() if raw_created else ""

        updated_at_val = getattr(dto, "updated_at_iso", None)
        if not updated_at_val:
            raw_updated = getattr(dto, "updated_at", None)
            updated_at_val = raw_updated.isoformat() if raw_updated else ""

        last_played_val = getattr(dto, "last_played_at_iso", None)
        if not last_played_val:
            raw_last_played = getattr(dto, "last_played_at", None)
            last_played_val = raw_last_played.isoformat() if raw_last_played else None

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
            is_in_active_directory=is_in_active_directory,
            error_message=dto.error_message,
            metadata=TrackMetadataResponse.from_dto(dto.metadata),
            play_count=getattr(dto, "play_count", 0),
            last_played_at_iso=last_played_val,
            created_at_iso=created_at_val,
            updated_at_iso=updated_at_val,
        )


class SyncLibraryResponse(BaseModel):
    repaired_count: int
    imported_count: int
    missing_count: int
    total_tracks: int
    message: str


class BatchDeleteTracksRequest(BaseModel):
    track_ids: list[str] = Field(..., min_length=1)
    delete_files: bool = True


class BatchDeleteTracksResponse(BaseModel):
    message: str
    deleted_count: int
    failed_ids: list[str] = []


class BatchAddTracksRequest(BaseModel):
    track_ids: list[str] = Field(..., min_length=1)


# Settings Schemas
class SettingsResponse(BaseModel):
    music_download_directory: str
    default_audio_quality: AudioQuality
    normalize_audio_lufs: float
    auto_tag_metadata: bool
    skip_non_music_sections: bool = True
    trim_silence: bool = True
    backend_version: str = "2.1.0"

    @classmethod
    def from_dto(cls, dto: Any, backend_version: str = "2.1.0") -> SettingsResponse:
        return cls(
            music_download_directory=dto.music_download_directory,
            default_audio_quality=dto.default_audio_quality,
            normalize_audio_lufs=dto.normalize_audio_lufs,
            auto_tag_metadata=dto.auto_tag_metadata,
            skip_non_music_sections=getattr(dto, "skip_non_music_sections", True),
            trim_silence=getattr(dto, "trim_silence", True),
            backend_version=backend_version,
        )


class UpdateSettingsRequest(BaseModel):
    music_download_directory: str
    default_audio_quality: AudioQuality = AudioQuality.BEST
    normalize_audio_lufs: float = -14.0
    auto_tag_metadata: bool = True
    skip_non_music_sections: bool = True
    trim_silence: bool = True


class StorageStatsResponse(BaseModel):
    active_directory: str
    active_dir_track_count: int
    other_locations_track_count: int
    missing_files_count: int
    total_library_tracks: int
    active_dir_size_bytes: int = 0
    active_dir_size_formatted: str = ""


class ConsolidateRequest(BaseModel):
    target_directory: Optional[str] = None
    move_files: bool = True


class ConsolidateResponse(BaseModel):
    moved_count: int
    already_there_count: int
    missing_count: int
    total_tracks: int
    target_directory: str
    message: str


# Backup Schemas
from .backup_schemas import (
    BackupPayloadSchema,
    BackupPlaylistSchema,
    BackupSettingsSchema,
    BackupTrackMetadataSchema,
    BackupTrackSchema,
    ImportBackupOptionsRequest,
    ImportBackupRequest,
    ImportBackupResponse,
)
