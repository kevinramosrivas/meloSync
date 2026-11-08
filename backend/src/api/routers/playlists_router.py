"""FastAPI router for Playlists management."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException

from ...domain.exceptions import PlaylistNotFoundException, TrackNotFoundException
from ..dependencies import Container, get_container
from ..schemas.playlist_schemas import (
    AddTrackToPlaylistRequest,
    BatchAddTracksRequest,
    PlaylistCreateRequest,
    PlaylistDetailResponse,
    PlaylistSummaryResponse,
    PlaylistUpdateRequest,
    PlaylistsGroupedResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playlists", tags=["Playlists"])


@router.get("", response_model=PlaylistsGroupedResponse)
def get_grouped_playlists(container: Container = Depends(get_container)) -> PlaylistsGroupedResponse:
    """Retrieves all playlists grouped into tiered sections (User, For You, Artists, Genres)."""
    use_case = container.get_playlists_grouped_use_case()
    grouped = use_case.execute()

    return PlaylistsGroupedResponse(
        user_playlists=[PlaylistSummaryResponse.from_domain(p) for p in grouped["user_playlists"]],
        for_you_playlists=[PlaylistSummaryResponse.from_domain(p) for p in grouped["for_you_playlists"]],
        artist_playlists=[PlaylistSummaryResponse.from_domain(p) for p in grouped["artist_playlists"]],
        genre_playlists=[PlaylistSummaryResponse.from_domain(p) for p in grouped["genre_playlists"]],
    )


@router.post("", response_model=PlaylistDetailResponse)
def create_playlist(
    request: PlaylistCreateRequest,
    container: Container = Depends(get_container),
) -> PlaylistDetailResponse:
    """Creates a user-defined custom playlist."""
    use_case = container.get_create_playlist_use_case()
    playlist = use_case.execute(name=request.name, description=request.description)
    return PlaylistDetailResponse.from_domain(playlist)


@router.post("/sync-smart")
def sync_smart_playlists(
    background_enrich: bool = True,
    container: Container = Depends(get_container),
):
    """Triggers instant local synchronization of smart playlists with non-blocking background enrichment."""
    use_case = container.get_sync_smart_playlists_use_case()
    result = use_case.execute(background_enrich=background_enrich)
    return {
        "message": "Listas inteligentes sincronizadas correctamente.",
        "artist_count": result.get("artist_count", 0),
        "genre_count": result.get("genre_count", 0),
        "pending_artists": result.get("pending_artists", 0),
        "pending_genres": result.get("pending_genres", 0),
    }


@router.get("/{playlist_id}", response_model=PlaylistDetailResponse)
def get_playlist_by_id(
    playlist_id: str,
    container: Container = Depends(get_container),
) -> PlaylistDetailResponse:
    """Retrieves full playlist details with track list."""
    try:
        use_case = container.get_playlist_by_id_use_case()
        playlist = use_case.execute(playlist_id)
        return PlaylistDetailResponse.from_domain(playlist)
    except PlaylistNotFoundException:
        raise HTTPException(status_code=404, detail="Lista de reproducción no encontrada.")


@router.put("/{playlist_id}", response_model=PlaylistDetailResponse)
def update_playlist(
    playlist_id: str,
    request: PlaylistUpdateRequest,
    container: Container = Depends(get_container),
) -> PlaylistDetailResponse:
    """Updates name or description of a custom playlist."""
    try:
        use_case = container.get_update_playlist_use_case()
        updated = use_case.execute(playlist_id, name=request.name, description=request.description)
        return PlaylistDetailResponse.from_domain(updated)
    except PlaylistNotFoundException:
        raise HTTPException(status_code=404, detail="Lista de reproducción no encontrada.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{playlist_id}")
def delete_playlist(
    playlist_id: str,
    container: Container = Depends(get_container),
):
    """Deletes a custom playlist."""
    try:
        use_case = container.get_delete_playlist_use_case()
        use_case.execute(playlist_id)
        return {"message": "Lista eliminada correctamente.", "playlist_id": playlist_id}
    except PlaylistNotFoundException:
        raise HTTPException(status_code=404, detail="Lista de reproducción no encontrada.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{playlist_id}/tracks", response_model=PlaylistDetailResponse)
def add_track_to_playlist(
    playlist_id: str,
    request: AddTrackToPlaylistRequest,
    container: Container = Depends(get_container),
) -> PlaylistDetailResponse:
    """Adds a track to a custom playlist."""
    try:
        use_case = container.get_add_track_to_playlist_use_case()
        updated = use_case.execute(playlist_id, request.track_id)
        return PlaylistDetailResponse.from_domain(updated)
    except PlaylistNotFoundException:
        raise HTTPException(status_code=404, detail="Lista de reproducción no encontrada.")
    except TrackNotFoundException:
        raise HTTPException(status_code=404, detail="Pista no encontrada.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{playlist_id}/batch-tracks", response_model=PlaylistDetailResponse)
def add_tracks_batch_to_playlist(
    playlist_id: str,
    request: BatchAddTracksRequest,
    container: Container = Depends(get_container),
) -> PlaylistDetailResponse:
    """Adds multiple tracks to a custom playlist in a single atomic transaction."""
    try:
        use_case = container.get_add_tracks_batch_to_playlist_use_case()
        updated = use_case.execute(playlist_id, request.track_ids)
        return PlaylistDetailResponse.from_domain(updated)
    except PlaylistNotFoundException:
        raise HTTPException(status_code=404, detail="Lista de reproducción no encontrada.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{playlist_id}/tracks/{track_id}", response_model=PlaylistDetailResponse)
def remove_track_from_playlist(
    playlist_id: str,
    track_id: str,
    container: Container = Depends(get_container),
) -> PlaylistDetailResponse:
    """Removes a track from a custom playlist."""
    try:
        use_case = container.get_remove_track_from_playlist_use_case()
        updated = use_case.execute(playlist_id, track_id)
        return PlaylistDetailResponse.from_domain(updated)
    except PlaylistNotFoundException:
        raise HTTPException(status_code=404, detail="Lista de reproducción no encontrada.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
