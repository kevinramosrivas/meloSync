"""Downloads Router: Start, monitor, and retry audio downloads."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import Container, get_container
from ..schemas import DownloadRequest, TrackResponse
from ...application.dto import DownloadProgressDTO, DownloadTrackCommand, TrackDTO
from ...application.services.path_resolver import TrackFileResolver
from ...domain.entities import DownloadStatus, Track

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/downloads", tags=["Downloads"])


@router.post("", response_model=dict)
async def start_download(
    request: DownloadRequest,
    container: Container = Depends(get_container),
):
    """Enqueues audio download and starts the processing pipeline in the background."""
    command = DownloadTrackCommand(
        youtube_id=request.youtube_id,
        url=request.url,
        original_title=request.original_title,
        duration_seconds=request.duration_seconds,
        channel_name=request.channel_name,
        custom_quality=request.quality,
    )

    # Synchronously register/reset the track in the database in PENDIENTE state.
    # This guarantees that when the frontend immediately navigates to /downloads,
    # the track is already visible and ready for live progress streaming without race conditions.
    with container.uow_factory() as uow:
        existing = uow.tracks.get_by_youtube_id(command.youtube_id)
        if existing:
            existing.status = DownloadStatus.PENDIENTE
            existing.progress_percent = 0.0
            existing.error_message = None
            existing.original_title = command.original_title
            existing.duration_seconds = command.duration_seconds
            existing.channel_name = command.channel_name
            track = uow.tracks.update(existing)
        else:
            track = Track(
                youtube_id=command.youtube_id,
                url=command.url,
                original_title=command.original_title,
                duration_seconds=command.duration_seconds,
                channel_name=command.channel_name,
                status=DownloadStatus.PENDIENTE,
            )
            track = uow.tracks.add(track)
        uow.commit()

    # Clear any previous cancellation flag for this track
    container.task_executor.clear_cancel_flag(track_id=track.id, youtube_id=command.youtube_id)

    use_case = container.get_download_use_case()
    loop = asyncio.get_running_loop()

    def _sync_on_success() -> None:
        try:
            container.get_sync_smart_playlists_use_case().execute(background_enrich=True)
        except Exception as e:
            logger.warning("Could not auto-sync smart playlists after download: %s", e)

    # Schedule non-blocking execution in the worker thread pool
    container.task_executor.submit_download(use_case, command, loop, on_success=_sync_on_success)

    return {
        "message": "Descarga encolada e iniciada en segundo plano.",
        "track_id": track.id,
        "youtube_id": track.youtube_id,
        "status": track.status.value,
    }


@router.get("", response_model=list[TrackResponse])
def list_active_downloads(
    container: Container = Depends(get_container),
):
    """Lists all tracks currently in downloading, processing or metadata states."""
    library_uc = container.get_library_use_case()
    all_tracks = library_uc.execute()
    # Filter non-completed tracks (pending, downloading, processing, fetching metadata, error, cancelled)
    active = [t for t in all_tracks if t.status != DownloadStatus.COMPLETADA]
    return [TrackResponse.from_dto(t) for t in active]


@router.post("/{track_id}/retry", response_model=dict)
async def retry_download(
    track_id: str,
    container: Container = Depends(get_container),
):
    """Retries a failed track download."""
    track_uc = container.get_track_by_id_use_case()
    track = track_uc.execute(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Pista no encontrada.")

    # Local tracks cannot be downloaded from YouTube; try to re-resolve on disk
    if track.youtube_id.startswith("local_") or track.url.startswith("local://"):
        with container.uow_factory() as uow:
            settings = uow.settings.get()
            track_entity = uow.tracks.get_by_id(track_id)
            if not track_entity:
                raise HTTPException(status_code=404, detail="Pista no encontrada.")

            resolved = TrackFileResolver.resolve(
                track=track_entity,
                active_music_dir=settings.music_download_directory,
                uow=uow,
            )
            if resolved and resolved.exists():
                track_entity.status = DownloadStatus.COMPLETADA
                track_entity.file_path = str(resolved)
                track_entity.progress_percent = 100.0
                track_entity.error_message = None
                saved = uow.tracks.update(track_entity)
                uow.commit()
                container.ws_manager.publish_track_completed(TrackDTO.from_domain(saved))
                container.ws_manager.publish_library_updated()
                return {"message": "Archivo local vinculado correctamente.", "track_id": track_id, "status": "COMPLETADA"}
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Este archivo proviene de una importación local y no está en YouTube. Cópialo a tu carpeta de música para vincularlo.",
                )

    url = track.url
    if not url.startswith("http") and len(track.youtube_id) == 11 and not track.youtube_id.startswith("local_"):
        url = f"https://www.youtube.com/watch?v={track.youtube_id}"

    command = DownloadTrackCommand(
        youtube_id=track.youtube_id,
        url=url,
        original_title=track.original_title,
        duration_seconds=track.duration_seconds,
        channel_name=track.channel_name,
    )

    # Clear any previous cancellation flag
    container.task_executor.clear_cancel_flag(track_id=track.id, youtube_id=command.youtube_id)

    use_case = container.get_download_use_case()
    loop = asyncio.get_running_loop()

    def _sync_on_success() -> None:
        try:
            container.get_sync_smart_playlists_use_case().execute(background_enrich=True)
        except Exception as e:
            logger.warning("Could not auto-sync smart playlists after download: %s", e)

    container.task_executor.submit_download(use_case, command, loop, on_success=_sync_on_success)

    return {"message": "Reintento de descarga iniciado.", "track_id": track_id}


@router.post("/{track_id}/cancel", response_model=dict)
def cancel_download(
    track_id: str,
    container: Container = Depends(get_container),
):
    """Cancels an ongoing or queued download."""
    with container.uow_factory() as uow:
        track = uow.tracks.get_by_id(track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Pista no encontrada.")

        # Request cancellation in the worker thread pool
        container.task_executor.request_cancel(track_id=track.id, youtube_id=track.youtube_id)

        if track.status == DownloadStatus.COMPLETADA:
            return {"message": "La descarga ya está completada.", "track_id": track_id, "status": track.status.value}

        track.mark_cancelled("Descarga cancelada por el usuario")
        updated_track = uow.tracks.update(track)
        settings = uow.settings.get()
        music_dir = Path(settings.music_download_directory)
        uow.commit()

    # Clean up any partial raw download files for this track
    try:
        if music_dir.exists():
            for p in music_dir.glob(f"{track.youtube_id}*"):
                if p.is_file() and not p.name.endswith(".mp3"):
                    p.unlink(missing_ok=True)
    except Exception as e:
        logger.warning("Error cleaning partial files on cancel: %s", e)

    # Publish progress via WebSocket so all connected clients update immediately
    container.ws_manager.publish_progress(
        DownloadProgressDTO(
            track_id=updated_track.id,
            youtube_id=updated_track.youtube_id,
            status=DownloadStatus.CANCELADA,
            progress_percent=updated_track.progress_percent,
            stage_description="Descarga cancelada por el usuario",
        )
    )
    container.ws_manager.publish_library_updated()

    return {"message": "Descarga cancelada exitosamente.", "track_id": track_id, "status": "CANCELADA"}


@router.delete("/{track_id}", response_model=dict)
def delete_download(
    track_id: str,
    container: Container = Depends(get_container),
):
    """Cancels and permanently deletes a download (active, failed, or cancelled) and its partial files."""
    with container.uow_factory() as uow:
        track = uow.tracks.get_by_id(track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Pista no encontrada.")

        # Request worker cancellation immediately
        container.task_executor.request_cancel(track_id=track.id, youtube_id=track.youtube_id)

        settings = uow.settings.get()
        music_dir = Path(settings.music_download_directory)

        # Delete from DB
        uow.tracks.delete(track_id)
        uow.commit()

    # Clean up any raw/partial files
    try:
        if music_dir.exists():
            for p in music_dir.glob(f"{track.youtube_id}*"):
                if p.is_file():
                    p.unlink(missing_ok=True)
        # If there was a partially written file_path and status was not COMPLETADA:
        if track.file_path and track.status != DownloadStatus.COMPLETADA:
            p_file = Path(track.file_path)
            if p_file.exists():
                p_file.unlink(missing_ok=True)
    except Exception as e:
        logger.warning("Error removing files on download delete: %s", e)

    # Notify WebSocket to remove track from active list
    container.ws_manager.publish_progress(
        DownloadProgressDTO(
            track_id=track.id,
            youtube_id=track.youtube_id,
            status=DownloadStatus.CANCELADA,
            progress_percent=0.0,
            stage_description="Descarga eliminada",
        )
    )
    container.ws_manager.publish_library_updated()

    return {"message": "Descarga eliminada correctamente.", "track_id": track_id}


@router.delete("", response_model=dict)
def clear_failed_and_cancelled_downloads(
    container: Container = Depends(get_container),
):
    """Removes all failed and cancelled downloads from the database and monitor."""
    deleted_count = 0
    with container.uow_factory() as uow:
        all_tracks = uow.tracks.list_all()
        to_delete = [
            t for t in all_tracks
            if t.status in (DownloadStatus.ERROR, DownloadStatus.CANCELADA)
        ]
        settings = uow.settings.get()
        music_dir = Path(settings.music_download_directory)

        for track in to_delete:
            container.task_executor.request_cancel(track_id=track.id, youtube_id=track.youtube_id)
            uow.tracks.delete(track.id)
            deleted_count += 1
            # Clean partials
            try:
                if music_dir.exists():
                    for p in music_dir.glob(f"{track.youtube_id}*"):
                        if p.is_file():
                            p.unlink(missing_ok=True)
            except Exception:
                pass
        uow.commit()

    if deleted_count > 0:
        container.ws_manager.publish_library_updated()

    return {
        "message": f"Se eliminaron {deleted_count} descargas fallidas o canceladas.",
        "deleted_count": deleted_count,
    }

