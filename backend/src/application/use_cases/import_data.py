"""Use Case: Import and Restore Library, Playlists, and Settings from a Backup."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any, Optional

from ..dto import (
    DownloadTrackCommand,
    ImportBackupOptionsDTO,
    ImportBackupResultDTO,
)
from ..events import IEventPublisher
from ..services.path_resolver import TrackFileResolver
from ...domain.entities import (
    AudioQuality,
    DownloadStatus,
    Playlist,
    Track,
    TrackMetadata,
    utc_now,
)
from ...domain.repositories import IUnitOfWork

logger = logging.getLogger(__name__)

SUPPORTED_FORMAT = "melosync-backup"
SUPPORTED_VERSIONS = {1}


def _is_downloadable_track(yt_id: str, track_url: str) -> bool:
    """Checks whether a track can be downloaded from YouTube rather than being a local file."""
    if yt_id.startswith("local_") or track_url.startswith("local://"):
        return False
    if track_url.startswith("http://") or track_url.startswith("https://"):
        return True
    if len(yt_id) == 11 and not any(c in yt_id for c in "/\\ :?#"):
        return True
    return False


def _normalize_download_url(yt_id: str, track_url: str) -> str:
    """Ensures a valid full YouTube URL for downloadable tracks."""
    if track_url.startswith("http://") or track_url.startswith("https://"):
        return track_url
    if len(yt_id) == 11 and not yt_id.startswith("local_"):
        return f"https://www.youtube.com/watch?v={yt_id}"
    return track_url


class ImportBackupUseCase:
    """Restores settings, reconciles tracks and custom playlists, and triggers async downloads."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(
        self,
        backup_dict: dict[str, Any],
        options: Optional[ImportBackupOptionsDTO] = None,
        task_executor: Optional[Any] = None,
        download_use_case: Optional[Any] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        event_publisher: Optional[IEventPublisher] = None,
    ) -> ImportBackupResultDTO:
        opts = options or ImportBackupOptionsDTO()

        # -------------------------------------------------------------
        # 1. Validation of Backup Format and Schema
        # -------------------------------------------------------------
        backup_format = backup_dict.get("format")
        if backup_format != SUPPORTED_FORMAT:
            raise ValueError(
                f"Formato de archivo de respaldo no válido: '{backup_format}'. Se esperaba '{SUPPORTED_FORMAT}'."
            )

        backup_version = backup_dict.get("version")
        if backup_version not in SUPPORTED_VERSIONS:
            raise ValueError(
                f"Versión de respaldo '{backup_version}' no soportada por esta versión de meloSync."
            )

        tracks_data = backup_dict.get("tracks", [])
        playlists_data = backup_dict.get("playlists", [])
        settings_data = backup_dict.get("settings", {})
        user_preferences = settings_data.get("user_preferences", {})

        settings_restored = False
        tracks_imported_count = 0
        tracks_already_present_count = 0
        playlists_imported_count = 0
        tracks_to_download: list[Track] = []

        with self._uow_factory() as uow:
            # -------------------------------------------------------------
            # 2. Settings Restoration
            # -------------------------------------------------------------
            current_settings = uow.settings.get()
            if opts.restore_settings and settings_data:
                quality_str = settings_data.get("default_audio_quality", current_settings.default_audio_quality.value)
                quality_enum = (
                    AudioQuality(quality_str)
                    if quality_str in AudioQuality._value2member_map_
                    else AudioQuality.BEST
                )

                current_settings.default_audio_quality = quality_enum
                current_settings.normalize_audio_lufs = float(
                    settings_data.get("normalize_audio_lufs", current_settings.normalize_audio_lufs)
                )
                current_settings.auto_tag_metadata = bool(
                    settings_data.get("auto_tag_metadata", current_settings.auto_tag_metadata)
                )
                if "skip_non_music_sections" in settings_data:
                    current_settings.skip_non_music_sections = bool(settings_data["skip_non_music_sections"])
                if "trim_silence" in settings_data:
                    current_settings.trim_silence = bool(settings_data["trim_silence"])
                current_settings.updated_at = utc_now()
                uow.settings.update(current_settings)
                settings_restored = True

            # -------------------------------------------------------------
            # 3. Track Upserting & Disk Reconciliation
            # -------------------------------------------------------------
            # Index current tracks by youtube_id for O(1) lookup
            existing_tracks = {t.youtube_id: t for t in uow.tracks.list_all() if t.youtube_id}

            for t_raw in tracks_data:
                yt_id = t_raw.get("youtube_id", "").strip()
                if not yt_id:
                    continue

                url = t_raw.get("url") or f"https://www.youtube.com/watch?v={yt_id}"
                original_title = t_raw.get("original_title") or "Pista de meloSync"
                duration = int(t_raw.get("duration_seconds", 0))
                channel = t_raw.get("channel_name", "")
                play_count = int(t_raw.get("play_count", 0))

                last_played_at: Optional[datetime] = None
                raw_last_played = t_raw.get("last_played_at_iso")
                if raw_last_played:
                    try:
                        last_played_at = datetime.fromisoformat(raw_last_played)
                    except Exception:
                        pass

                meta_raw = t_raw.get("metadata")
                track_meta: Optional[TrackMetadata] = None
                if meta_raw:
                    track_meta = TrackMetadata(
                        title=meta_raw.get("title", original_title),
                        artist=meta_raw.get("artist", channel or "Desconocido"),
                        album=meta_raw.get("album", "Sencillo"),
                        year=meta_raw.get("year"),
                        genre=meta_raw.get("genre"),
                        track_number=meta_raw.get("track_number"),
                        disc_number=meta_raw.get("disc_number"),
                        cover_url=meta_raw.get("cover_url"),
                        lyrics=meta_raw.get("lyrics"),
                    )

                existing_track = existing_tracks.get(yt_id)

                if existing_track:
                    tracks_already_present_count += 1
                    # Check if audio file physically exists on this machine
                    resolved_file = TrackFileResolver.resolve(
                        track=existing_track,
                        active_music_dir=current_settings.music_download_directory,
                        uow=uow,
                    )

                    if resolved_file and resolved_file.exists():
                        # File is present on disk!
                        if opts.overwrite_existing_metadata and track_meta:
                            existing_track.metadata = track_meta
                        if play_count > existing_track.play_count:
                            existing_track.play_count = play_count
                            existing_track.last_played_at = last_played_at or existing_track.last_played_at
                        existing_track.status = DownloadStatus.COMPLETADA
                        uow.tracks.update(existing_track)
                    else:
                        # File is missing locally. Check if it can be downloaded from YouTube
                        existing_track.status = DownloadStatus.PENDIENTE
                        existing_track.progress_percent = 0.0
                        if track_meta:
                            existing_track.metadata = track_meta

                        if _is_downloadable_track(existing_track.youtube_id, existing_track.url):
                            tracks_to_download.append(existing_track)
                        else:
                            existing_track.error_message = (
                                "Archivo local no encontrado en la carpeta de música. Cópialo manualmente para reproducirlo."
                            )
                        uow.tracks.update(existing_track)
                else:
                    # Brand new track in this meloSync instance
                    new_track = Track(
                        youtube_id=yt_id,
                        url=url,
                        original_title=original_title,
                        duration_seconds=duration,
                        channel_name=channel,
                        status=DownloadStatus.PENDIENTE,
                        progress_percent=0.0,
                        metadata=track_meta,
                        play_count=play_count,
                        last_played_at=last_played_at,
                    )

                    # Check if the file happens to be in the music folder already
                    resolved_file = TrackFileResolver.resolve(
                        track=new_track,
                        active_music_dir=current_settings.music_download_directory,
                        uow=uow,
                    )
                    if resolved_file and resolved_file.exists():
                        new_track.status = DownloadStatus.COMPLETADA
                        new_track.file_path = str(resolved_file)
                        new_track.progress_percent = 100.0
                    else:
                        if _is_downloadable_track(new_track.youtube_id, new_track.url):
                            new_track.url = _normalize_download_url(new_track.youtube_id, new_track.url)
                            tracks_to_download.append(new_track)
                        else:
                            new_track.error_message = (
                                "Archivo local no encontrado en la carpeta de música. Cópialo manualmente para reproducirlo."
                            )

                    saved = uow.tracks.add(new_track)
                    existing_tracks[yt_id] = saved
                    tracks_imported_count += 1

            uow.commit()

            # -------------------------------------------------------------
            # 4. Custom Playlists Reconstruction
            # -------------------------------------------------------------
            existing_playlists = {p.name: p for p in uow.playlists.list_all() if p.playlist_type == "custom"}

            for p_raw in playlists_data:
                p_name = p_raw.get("name", "").strip()
                if not p_name:
                    continue

                p_desc = p_raw.get("description", "")
                p_cover = p_raw.get("cover_url")
                p_track_yt_ids = p_raw.get("track_youtube_ids", [])

                playlist = existing_playlists.get(p_name)
                if not playlist:
                    playlist = Playlist(
                        name=p_name,
                        description=p_desc,
                        is_smart=False,
                        playlist_type="custom",
                        cover_url=p_cover,
                    )
                    playlist = uow.playlists.add(playlist)
                    existing_playlists[p_name] = playlist

                # Associate tracks in exact exported order
                for yt_id in p_track_yt_ids:
                    matched_track = existing_tracks.get(yt_id)
                    if matched_track:
                        playlist.add_track(matched_track)

                uow.playlists.update(playlist)
                playlists_imported_count += 1

            uow.commit()

        # -------------------------------------------------------------
        # 5. Background Asynchronous Downloads Dispatch
        # -------------------------------------------------------------
        queued_count = 0
        if opts.download_missing_audio and tracks_to_download:
            if task_executor and download_use_case and loop:
                for track in tracks_to_download:
                    target_url = _normalize_download_url(track.youtube_id, track.url)
                    cmd = DownloadTrackCommand(
                        youtube_id=track.youtube_id,
                        url=target_url,
                        original_title=track.original_title,
                        duration_seconds=track.duration_seconds,
                        channel_name=track.channel_name,
                        preferred_metadata=track.metadata,
                    )
                    task_executor.submit_download(download_use_case, cmd, loop)
                    queued_count += 1
            else:
                logger.warning(
                    "Async task_executor, download_use_case, or event loop was not provided; "
                    "%d tracks left in PENDIENTE state.",
                    len(tracks_to_download),
                )
                queued_count = len(tracks_to_download)

        # -------------------------------------------------------------
        # 6. Notify UI via WebSockets
        # -------------------------------------------------------------
        if event_publisher:
            event_publisher.publish_library_updated()

        return ImportBackupResultDTO(
            status="success",
            message=f"Importación completada: {tracks_imported_count} canciones añadidas, "
                    f"{queued_count} encoladas para descarga, {playlists_imported_count} listas restauradas.",
            total_tracks_in_backup=len(tracks_data),
            tracks_imported=tracks_imported_count,
            tracks_already_present=tracks_already_present_count,
            tracks_queued_for_download=queued_count,
            playlists_imported=playlists_imported_count,
            settings_restored=settings_restored,
            user_preferences=user_preferences if opts.restore_preferences else {},
        )

