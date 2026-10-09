"""Metadata Router: Query candidates from iTunes and update track metadata."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import Container, get_container
from ..schemas import TrackMetadataResponse, TrackResponse, UpdateMetadataRequest
from ...application.dto import UpdateTrackMetadataCommand

router = APIRouter(prefix="/metadata", tags=["Metadata"])


@router.get("/candidates", response_model=list[TrackMetadataResponse])
def search_metadata_candidates(
    q: str = Query(..., min_length=1, description="Song title or artist query"),
    limit: int = Query(15, ge=1, le=50),
    container: Container = Depends(get_container),
):
    """Searches iTunes API for official track metadata candidates."""
    use_case = container.get_search_metadata_use_case()
    candidates = use_case.execute(query=q, limit=limit)
    return [
        TrackMetadataResponse(
            title=c.title,
            artist=c.artist,
            album=c.album,
            year=c.year,
            genre=c.genre,
            track_number=c.track_number,
            disc_number=c.disc_number,
            cover_url=c.cover_url,
            has_cover_bytes=c.has_cover_bytes,
            lyrics=c.lyrics,
        )
        for c in candidates
    ]


@router.put("/tracks/{track_id}", response_model=TrackResponse)
def update_track_metadata(
    track_id: str,
    body: UpdateMetadataRequest,
    container: Container = Depends(get_container),
):
    """Applies updated metadata and tags to a track and its audio file."""
    use_case = container.get_update_metadata_use_case()
    command = UpdateTrackMetadataCommand(
        track_id=track_id,
        title=body.title,
        artist=body.artist,
        album=body.album,
        year=body.year,
        genre=body.genre,
        track_number=body.track_number,
        cover_url=body.cover_url,
    )
    try:
        updated = use_case.execute(command)
        container.ws_manager.publish_library_updated()
        return TrackResponse.from_dto(updated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando metadatos: {e}")
