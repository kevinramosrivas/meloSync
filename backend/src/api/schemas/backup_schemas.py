"""Pydantic schemas for Backup Export and Import API."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

from ...application.dto import ExportBackupDTO, ImportBackupResultDTO


class BackupTrackMetadataSchema(BaseModel):
    title: str
    artist: str
    album: str = "Unknown Album"
    year: Optional[int] = None
    genre: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    cover_url: Optional[str] = None
    lyrics: Optional[str] = None


class BackupTrackSchema(BaseModel):
    youtube_id: str
    url: str
    original_title: str
    duration_seconds: int = 0
    channel_name: str = ""
    metadata: Optional[BackupTrackMetadataSchema] = None
    play_count: int = 0
    last_played_at_iso: Optional[str] = None


class BackupPlaylistSchema(BaseModel):
    name: str
    description: str = ""
    cover_url: Optional[str] = None
    track_youtube_ids: list[str] = Field(default_factory=list)


class BackupSettingsSchema(BaseModel):
    default_audio_quality: str
    normalize_audio_lufs: float
    auto_tag_metadata: bool
    skip_non_music_sections: bool = True
    trim_silence: bool = True
    user_preferences: dict[str, Any] = Field(default_factory=dict)


class BackupPayloadSchema(BaseModel):
    """Full portable backup payload."""
    format: str = "melosync-backup"
    version: int = 1
    exported_at_iso: str
    app_version: str = "2.1.0"
    settings: BackupSettingsSchema
    tracks: list[BackupTrackSchema] = Field(default_factory=list)
    playlists: list[BackupPlaylistSchema] = Field(default_factory=list)

    @classmethod
    def from_dto(cls, dto: ExportBackupDTO) -> BackupPayloadSchema:
        tracks = [
            BackupTrackSchema(
                youtube_id=t.youtube_id,
                url=t.url,
                original_title=t.original_title,
                duration_seconds=t.duration_seconds,
                channel_name=t.channel_name,
                metadata=(
                    BackupTrackMetadataSchema(
                        title=t.metadata.title,
                        artist=t.metadata.artist,
                        album=t.metadata.album,
                        year=t.metadata.year,
                        genre=t.metadata.genre,
                        track_number=t.metadata.track_number,
                        disc_number=t.metadata.disc_number,
                        cover_url=t.metadata.cover_url,
                        lyrics=t.metadata.lyrics,
                    )
                    if t.metadata
                    else None
                ),
                play_count=t.play_count,
                last_played_at_iso=t.last_played_at_iso,
            )
            for t in dto.tracks
        ]

        playlists = [
            BackupPlaylistSchema(
                name=p.name,
                description=p.description,
                cover_url=p.cover_url,
                track_youtube_ids=p.track_youtube_ids,
            )
            for p in dto.playlists
        ]

        settings = BackupSettingsSchema(
            default_audio_quality=dto.settings.default_audio_quality,
            normalize_audio_lufs=dto.settings.normalize_audio_lufs,
            auto_tag_metadata=dto.settings.auto_tag_metadata,
            user_preferences=dto.settings.user_preferences,
        )

        return cls(
            format=dto.format,
            version=dto.version,
            exported_at_iso=dto.exported_at_iso,
            app_version=dto.app_version,
            settings=settings,
            tracks=tracks,
            playlists=playlists,
        )


class ImportBackupOptionsRequest(BaseModel):
    download_missing_audio: bool = True
    restore_settings: bool = True
    restore_preferences: bool = True
    overwrite_existing_metadata: bool = False


class ImportBackupRequest(BaseModel):
    backup_data: BackupPayloadSchema
    options: ImportBackupOptionsRequest = Field(default_factory=ImportBackupOptionsRequest)


class ImportBackupResponse(BaseModel):
    status: str
    message: str
    total_tracks_in_backup: int
    tracks_imported: int
    tracks_already_present: int
    tracks_queued_for_download: int
    playlists_imported: int
    settings_restored: bool
    user_preferences: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dto(cls, dto: ImportBackupResultDTO) -> ImportBackupResponse:
        return cls(
            status=dto.status,
            message=dto.message,
            total_tracks_in_backup=dto.total_tracks_in_backup,
            tracks_imported=dto.tracks_imported,
            tracks_already_present=dto.tracks_already_present,
            tracks_queued_for_download=dto.tracks_queued_for_download,
            playlists_imported=dto.playlists_imported,
            settings_restored=dto.settings_restored,
            user_preferences=dto.user_preferences,
        )

