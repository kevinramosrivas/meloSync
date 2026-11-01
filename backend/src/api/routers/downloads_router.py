"""Downloads Router: Start, monitor, and retry audio downloads."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import Container, get_container
from ..schemas import DownloadRequest, TrackResponse
from ...application.dto import DownloadTrackCommand
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

    use_case = container.get_download_use_case()
    loop = asyncio.get_running_loop()

    # Schedule non-blocking execution in the worker thread pool
    container.task_executor.submit_download(use_case, command, loop)

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
    # Filter non-completed tracks (pending, downloading, processing, fetching metadata, error)
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

    command = DownloadTrackCommand(
        youtube_id=track.youtube_id,
        url=track.url,
        original_title=track.original_title,
        duration_seconds=track.duration_seconds,
        channel_name=track.channel_name,
    )

    use_case = container.get_download_use_case()
    loop = asyncio.get_running_loop()
    container.task_executor.submit_download(use_case, command, loop)

    return {"message": "Reintento de descarga iniciado.", "track_id": track_id}
