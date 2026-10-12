"""Library Router: Manage downloaded tracks, streaming, cover art, and OS actions."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from ..dependencies import Container, get_container
from ..schemas import SyncLibraryResponse, TrackResponse
from ...application.services.path_resolver import TrackFileResolver
from ...domain.entities import DownloadStatus
from ...domain.exceptions import TrackNotFoundException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/library", tags=["Library"])


@router.get("", response_model=list[TrackResponse])
def get_library(
    status: Optional[DownloadStatus] = None,
    container: Container = Depends(get_container),
):
    """Retrieves all tracks in the library, optionally filtered by status."""
    use_case = container.get_library_use_case()
    tracks = use_case.execute(status=status)
    return [TrackResponse.from_dto(t) for t in tracks]


@router.post("/sync", response_model=SyncLibraryResponse)
def sync_library(
    container: Container = Depends(get_container),
):
    """Reconciles track paths and discovers unindexed local audio files."""
    sync_uc = container.get_sync_library_use_case()
    result = sync_uc.execute()
    container.ws_manager.publish_library_updated()
    return SyncLibraryResponse(
        repaired_count=result.repaired_count,
        imported_count=result.imported_count,
        missing_count=result.missing_count,
        total_tracks=result.total_tracks,
        message=result.message,
    )


@router.get("/{track_id}", response_model=TrackResponse)
def get_track(
    track_id: str,
    container: Container = Depends(get_container),
):
    """Retrieves single track by ID."""
    use_case = container.get_track_by_id_use_case()
    track = use_case.execute(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Pista no encontrada.")
    return TrackResponse.from_dto(track)


@router.get("/{track_id}/stream")
def stream_audio(
    track_id: str,
    request: Request,
    container: Container = Depends(get_container),
):
    """Streams audio file with HTTP 206 Partial Content (Range header support for seeking)."""
    with container.uow_factory() as uow:
        track = uow.tracks.get_by_id(track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Pista no encontrada.")

        settings = uow.settings.get()
        file_path = TrackFileResolver.resolve(
            track=track,
            active_music_dir=settings.music_download_directory,
            uow=uow,
        )

        if not file_path or not file_path.exists():
            target_name = Path(track.file_path).name if track.file_path else track.display_title
            raise HTTPException(
                status_code=404,
                detail=f"El archivo físico '{target_name}' no existe en la carpeta de música.",
            )

        file_size = file_path.stat().st_size
        range_header = request.headers.get("Range")

        if not range_header:
            # Full content
            def file_iterator():
                with open(file_path, "rb") as f:
                    while chunk := f.read(64 * 1024):
                        yield chunk

            return StreamingResponse(
                file_iterator(),
                media_type="audio/mpeg",
                headers={"Content-Length": str(file_size), "Accept-Ranges": "bytes"},
            )

        # Parse Range: bytes=start-end
        range_match = range_header.replace("bytes=", "").split("-")
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
        end = min(end, file_size - 1)
        chunk_size = (end - start) + 1

        def ranged_iterator():
            with open(file_path, "rb") as f:
                f.seek(start)
                bytes_left = chunk_size
                while bytes_left > 0:
                    to_read = min(bytes_left, 64 * 1024)
                    data = f.read(to_read)
                    if not data:
                        break
                    bytes_left -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
        }

        return StreamingResponse(ranged_iterator(), status_code=206, media_type="audio/mpeg", headers=headers)


@router.get("/{track_id}/cover")
def get_track_cover(
    track_id: str,
    container: Container = Depends(get_container),
):
    """Retrieves embedded cover art bytes for a track."""
    with container.uow_factory() as uow:
        track = uow.tracks.get_by_id(track_id)
        if not track or not track.metadata or not track.metadata.cover_bytes:
            raise HTTPException(status_code=404, detail="Carátula no disponible.")

        cover_bytes = track.metadata.cover_bytes
        mime_type = "image/jpeg"
        if cover_bytes.startswith(b"\x89PNG"):
            mime_type = "image/png"

        return Response(content=cover_bytes, media_type=mime_type)


@router.post("/{track_id}/open-file")
def open_in_system_player(
    track_id: str,
    container: Container = Depends(get_container),
):
    """Opens audio file in the default OS media player."""
    with container.uow_factory() as uow:
        track = uow.tracks.get_by_id(track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Pista no encontrada.")

        settings = uow.settings.get()
        file_path = TrackFileResolver.resolve(
            track=track,
            active_music_dir=settings.music_download_directory,
            uow=uow,
        )

        if not file_path or not file_path.exists():
            target_name = Path(track.file_path).name if track.file_path else track.display_title
            raise HTTPException(
                status_code=404,
                detail=f"El archivo físico '{target_name}' no se encuentra en el disco.",
            )

        path_str = str(file_path)
        if sys.platform == "win32":
            os.startfile(path_str)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path_str])
        else:
            subprocess.Popen(["xdg-open", path_str])

        return {"message": "Abriendo en reproductor del sistema.", "file_path": path_str}


@router.post("/{track_id}/open-folder")
def open_containing_folder(
    track_id: str,
    container: Container = Depends(get_container),
):
    """Reveals audio file in the OS file explorer."""
    with container.uow_factory() as uow:
        track = uow.tracks.get_by_id(track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Pista no encontrada.")

        settings = uow.settings.get()
        file_path = TrackFileResolver.resolve(
            track=track,
            active_music_dir=settings.music_download_directory,
            uow=uow,
        )

        if not file_path or not file_path.exists():
            target_name = Path(track.file_path).name if track.file_path else track.display_title
            raise HTTPException(
                status_code=404,
                detail=f"El archivo físico '{target_name}' no se encuentra en la carpeta de música.",
            )

        path_str = str(file_path)
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{path_str}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path_str])
        else:
            subprocess.Popen(["xdg-open", str(file_path.parent)])

        return {"message": "Abriendo carpeta contenedora.", "file_path": path_str}


@router.delete("/{track_id}")
def delete_track(
    track_id: str,
    delete_file: bool = Query(True, description="Also remove file from disk"),
    container: Container = Depends(get_container),
):
    """Deletes track record and optionally physical audio file."""
    try:
        use_case = container.get_delete_track_use_case()
        success = use_case.execute(track_id, delete_file=delete_file)
        if success:
            container.ws_manager.publish_library_updated()
            return {"message": "Pista eliminada correctamente.", "track_id": track_id}
        raise HTTPException(status_code=404, detail="No se pudo eliminar la pista.")
    except TrackNotFoundException:
        raise HTTPException(status_code=404, detail="Pista no encontrada.")
