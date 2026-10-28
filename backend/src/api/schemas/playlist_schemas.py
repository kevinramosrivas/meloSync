"""Pydantic schemas for Playlists API."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

from ...domain.entities import Playlist
from . import TrackResponse


class PlaylistCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str = Field("", max_length=1024)


class PlaylistUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    description: Optional[str] = Field(None, max_length=1024)


class AddTrackToPlaylistRequest(BaseModel):
    track_id: str = Field(..., min_length=1)


class PlaylistSummaryResponse(BaseModel):
    id: str
    name: str
    description: str
    is_smart: bool
    playlist_type: str
    filter_query: Optional[str] = None
    cover_url: Optional[str] = None
    track_count: int
    duration_seconds: int
    created_at_iso: str
    updated_at_iso: str
    sample_cover_track_ids: list[str] = []

    @classmethod
    def from_domain(cls, p: Playlist) -> PlaylistSummaryResponse:
        total_duration = sum(t.duration_seconds for t in p.tracks)
        # Sample up to 4 track IDs for mosaic cover rendering
        cover_sample_ids = [t.id for t in p.tracks[:4]]

        return cls(
            id=p.id,
            name=p.name,
            description=p.description,
            is_smart=p.is_smart,
            playlist_type=p.playlist_type,
            filter_query=p.filter_query,
            cover_url=p.cover_url,
            track_count=len(p.tracks),
            duration_seconds=total_duration,
            created_at_iso=p.created_at.isoformat(),
            updated_at_iso=p.updated_at.isoformat(),
            sample_cover_track_ids=cover_sample_ids,
        )


class PlaylistDetailResponse(BaseModel):
    id: str
    name: str
    description: str
    is_smart: bool
    playlist_type: str
    filter_query: Optional[str] = None
    cover_url: Optional[str] = None
    track_count: int
    duration_seconds: int
    created_at_iso: str
    updated_at_iso: str
    sample_cover_track_ids: list[str] = []
    tracks: list[TrackResponse]

    @classmethod
    def from_domain(cls, p: Playlist) -> PlaylistDetailResponse:
        total_duration = sum(t.duration_seconds for t in p.tracks)
        cover_sample_ids = [t.id for t in p.tracks[:4]]
        track_responses = [TrackResponse.from_dto(t) for t in p.tracks]

        return cls(
            id=p.id,
            name=p.name,
            description=p.description,
            is_smart=p.is_smart,
            playlist_type=p.playlist_type,
            filter_query=p.filter_query,
            cover_url=p.cover_url,
            track_count=len(p.tracks),
            duration_seconds=total_duration,
            created_at_iso=p.created_at.isoformat(),
            updated_at_iso=p.updated_at.isoformat(),
            sample_cover_track_ids=cover_sample_ids,
            tracks=track_responses,
        )


class PlaylistsGroupedResponse(BaseModel):
    user_playlists: list[PlaylistSummaryResponse]
    for_you_playlists: list[PlaylistSummaryResponse]
    artist_playlists: list[PlaylistSummaryResponse]
    genre_playlists: list[PlaylistSummaryResponse]
