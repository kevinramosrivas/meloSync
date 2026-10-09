"""Concrete SQLAlchemy 2.0 implementations of Domain Repositories."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.domain.entities import DownloadStatus, Playlist, Track
from src.domain.repositories import IPlaylistRepository, ITrackRepository
from src.infrastructure.persistence.models import PlaylistModel, TrackModel

logger = logging.getLogger(__name__)


class SqlAlchemyTrackRepository(ITrackRepository):
    """Concrete repository for Track entities backed by SQLAlchemy 2.0."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, track: Track) -> Track:
        model = TrackModel.from_entity(track)
        self.session.add(model)
        return track

    def get_by_id(self, track_id: str) -> Optional[Track]:
        stmt = select(TrackModel).where(TrackModel.id == track_id)
        model = self.session.scalar(stmt)
        return model.to_entity() if model else None

    def get_by_youtube_id(self, youtube_id: str) -> Optional[Track]:
        stmt = select(TrackModel).where(TrackModel.youtube_id == youtube_id)
        model = self.session.scalar(stmt)
        return model.to_entity() if model else None

    def list_all(self) -> list[Track]:
        stmt = select(TrackModel).order_by(TrackModel.created_at.desc())
        models = self.session.scalars(stmt).all()
        return [m.to_entity() for m in models]

    def list_by_status(self, status: DownloadStatus) -> list[Track]:
        stmt = (
            select(TrackModel)
            .where(TrackModel.status == status.value)
            .order_by(TrackModel.created_at.desc())
        )
        models = self.session.scalars(stmt).all()
        return [m.to_entity() for m in models]

    def update(self, track: Track) -> Track:
        model = self.session.get(TrackModel, track.id)
        if not model:
            model = TrackModel.from_entity(track)
            self.session.add(model)
        else:
            model.status = track.status.value
            model.progress_percent = track.progress_percent
            model.file_path = track.file_path
            model.error_message = track.error_message
            model.original_title = track.original_title
            model.duration_seconds = track.duration_seconds
            model.channel_name = track.channel_name
            if track.metadata:
                model.meta_title = track.metadata.title
                model.meta_artist = track.metadata.artist
                model.meta_album = track.metadata.album
                model.meta_year = track.metadata.year
                model.meta_genre = track.metadata.genre
                model.meta_cover_url = track.metadata.cover_url
        return track

    def delete(self, track_id: str) -> bool:
        model = self.session.get(TrackModel, track_id)
        if model:
            self.session.delete(model)
            return True
        return False


class SqlAlchemyPlaylistRepository(IPlaylistRepository):
    """Concrete repository for Playlist entities backed by SQLAlchemy 2.0."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, playlist: Playlist) -> Playlist:
        model = PlaylistModel.from_entity(playlist)
        self.session.add(model)
        return playlist

    def get_by_id(self, playlist_id: str) -> Optional[Playlist]:
        stmt = select(PlaylistModel).where(PlaylistModel.id == playlist_id)
        model = self.session.scalar(stmt)
        return model.to_entity() if model else None

    def list_all(self) -> list[Playlist]:
        stmt = select(PlaylistModel).order_by(PlaylistModel.created_at.desc())
        models = self.session.scalars(stmt).all()
        return [m.to_entity() for m in models]

    def update(self, playlist: Playlist) -> Playlist:
        model = self.session.get(PlaylistModel, playlist.id)
        if not model:
            model = PlaylistModel.from_entity(playlist)
            self.session.add(model)
        else:
            model.name = playlist.name
            model.description = playlist.description
            # Sync track associations
            track_ids = [t.id for t in playlist.tracks]
            if track_ids:
                stmt = select(TrackModel).where(TrackModel.id.in_(track_ids))
                model.tracks = list(self.session.scalars(stmt).all())
            else:
                model.tracks = []
        return playlist

    def delete(self, playlist_id: str) -> bool:
        model = self.session.get(PlaylistModel, playlist_id)
        if model:
            self.session.delete(model)
            return True
        return False
