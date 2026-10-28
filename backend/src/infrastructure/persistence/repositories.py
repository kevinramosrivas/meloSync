"""SQLAlchemy implementations of domain repository interfaces."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...domain.entities import AppSettings, DownloadStatus, Playlist, Track, utc_now
from ...domain.repositories import (
    IPlaylistRepository,
    ISettingsRepository,
    ITrackRepository,
)
from .database import (
    PlaylistModel,
    SettingsModel,
    TrackModel,
    TrackPlayHistoryModel,
)


class SqlAlchemyTrackRepository(ITrackRepository):
    """SQLAlchemy implementation of ITrackRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, track: Track) -> Track:
        model = TrackModel.from_domain(track)
        self._session.add(model)
        self._session.flush()
        return model.to_domain()

    def get_by_id(self, track_id: str) -> Optional[Track]:
        model = self._session.get(TrackModel, track_id)
        return model.to_domain() if model else None

    def get_by_youtube_id(self, youtube_id: str) -> Optional[Track]:
        stmt = select(TrackModel).where(TrackModel.youtube_id == youtube_id)
        model = self._session.execute(stmt).scalar_one_or_none()
        return model.to_domain() if model else None

    def list_all(self) -> list[Track]:
        stmt = select(TrackModel).order_by(TrackModel.created_at.desc())
        models = self._session.execute(stmt).scalars().all()
        return [m.to_domain() for m in models]

    def list_by_status(self, status: DownloadStatus) -> list[Track]:
        stmt = select(TrackModel).where(TrackModel.status == status.value).order_by(TrackModel.created_at.desc())
        models = self._session.execute(stmt).scalars().all()
        return [m.to_domain() for m in models]

    def update(self, track: Track) -> Track:
        model = self._session.get(TrackModel, track.id)
        if not model:
            return self.add(track)

        model.status = track.status.value
        model.progress_percent = track.progress_percent
        model.file_path = track.file_path
        model.error_message = track.error_message
        model.duration_seconds = track.duration_seconds
        model.original_title = track.original_title
        model.channel_name = track.channel_name
        model.play_count = track.play_count
        model.last_played_at = track.last_played_at

        if track.metadata:
            model.meta_title = track.metadata.title
            model.meta_artist = track.metadata.artist
            model.meta_album = track.metadata.album
            model.meta_year = track.metadata.year
            model.meta_genre = track.metadata.genre
            model.meta_track_number = track.metadata.track_number
            model.meta_disc_number = track.metadata.disc_number
            model.meta_cover_url = track.metadata.cover_url
            model.meta_cover_bytes = track.metadata.cover_bytes
            model.meta_lyrics = track.metadata.lyrics

        model.updated_at = track.updated_at
        self._session.flush()
        return model.to_domain()

    def delete(self, track_id: str) -> bool:
        model = self._session.get(TrackModel, track_id)
        if model:
            self._session.delete(model)
            self._session.flush()
            return True
        return False

    def record_play(self, track_id: str) -> None:
        model = self._session.get(TrackModel, track_id)
        if model:
            model.play_count = (model.play_count or 0) + 1
            now = utc_now()
            model.last_played_at = now
            history_entry = TrackPlayHistoryModel(
                id=str(uuid.uuid4()),
                track_id=track_id,
                played_at=now,
            )
            self._session.add(history_entry)
            self._session.flush()

    def get_top_played(self, limit: int = 50) -> list[Track]:
        stmt = (
            select(TrackModel)
            .where(TrackModel.status == DownloadStatus.COMPLETADA.value)
            .where(TrackModel.play_count > 0)
            .order_by(TrackModel.play_count.desc(), TrackModel.last_played_at.desc())
            .limit(limit)
        )
        models = self._session.execute(stmt).scalars().all()
        return [m.to_domain() for m in models]

    def get_on_repeat(self, days: int = 30, min_repeats: int = 2, limit: int = 30) -> list[Track]:
        cutoff = utc_now() - timedelta(days=days)
        stmt = (
            select(TrackPlayHistoryModel.track_id, func.count(TrackPlayHistoryModel.id).label("repeat_count"))
            .where(TrackPlayHistoryModel.played_at >= cutoff)
            .group_by(TrackPlayHistoryModel.track_id)
            .having(func.count(TrackPlayHistoryModel.id) >= min_repeats)
            .order_by(func.count(TrackPlayHistoryModel.id).desc())
            .limit(limit)
        )
        rows = self._session.execute(stmt).all()
        if not rows:
            return []

        track_ids = [r[0] for r in rows]
        tracks_stmt = select(TrackModel).where(
            TrackModel.id.in_(track_ids),
            TrackModel.status == DownloadStatus.COMPLETADA.value,
        )
        track_models = {m.id: m.to_domain() for m in self._session.execute(tracks_stmt).scalars().all()}
        return [track_models[tid] for tid in track_ids if tid in track_models]


class SqlAlchemyPlaylistRepository(IPlaylistRepository):
    """SQLAlchemy implementation of IPlaylistRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, playlist: Playlist) -> Playlist:
        model = PlaylistModel(
            id=playlist.id,
            name=playlist.name,
            description=playlist.description,
            is_smart=playlist.is_smart,
            playlist_type=playlist.playlist_type,
            filter_query=playlist.filter_query,
            cover_url=playlist.cover_url,
            created_at=playlist.created_at,
            updated_at=playlist.updated_at,
        )
        if playlist.tracks:
            track_ids = [t.id for t in playlist.tracks]
            models = self._session.execute(select(TrackModel).where(TrackModel.id.in_(track_ids))).scalars().all()
            model.tracks = list(models)

        self._session.add(model)
        self._session.flush()
        return model.to_domain()

    def get_by_id(self, playlist_id: str) -> Optional[Playlist]:
        model = self._session.get(PlaylistModel, playlist_id)
        return model.to_domain() if model else None

    def list_all(self) -> list[Playlist]:
        stmt = select(PlaylistModel).order_by(PlaylistModel.name.asc())
        models = self._session.execute(stmt).scalars().all()
        return [m.to_domain() for m in models]

    def list_by_type(self, playlist_type: str) -> list[Playlist]:
        stmt = (
            select(PlaylistModel)
            .where(PlaylistModel.playlist_type == playlist_type)
            .order_by(PlaylistModel.name.asc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [m.to_domain() for m in models]

    def get_by_filter(self, playlist_type: str, filter_query: str) -> Optional[Playlist]:
        stmt = (
            select(PlaylistModel)
            .where(PlaylistModel.playlist_type == playlist_type)
            .where(PlaylistModel.filter_query == filter_query)
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return model.to_domain() if model else None

    def update(self, playlist: Playlist) -> Playlist:
        model = self._session.get(PlaylistModel, playlist.id)
        if not model:
            return self.add(playlist)

        model.name = playlist.name
        model.description = playlist.description
        model.is_smart = playlist.is_smart
        model.playlist_type = playlist.playlist_type
        model.filter_query = playlist.filter_query
        model.cover_url = playlist.cover_url
        model.updated_at = playlist.updated_at

        if playlist.tracks is not None:
            track_ids = [t.id for t in playlist.tracks]
            models = self._session.execute(select(TrackModel).where(TrackModel.id.in_(track_ids))).scalars().all()
            model.tracks = list(models)

        self._session.flush()
        return model.to_domain()

    def delete(self, playlist_id: str) -> bool:
        model = self._session.get(PlaylistModel, playlist_id)
        if model:
            self._session.delete(model)
            self._session.flush()
            return True
        return False


class SqlAlchemySettingsRepository(ISettingsRepository):
    """SQLAlchemy implementation of ISettingsRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> AppSettings:
        model = self._session.get(SettingsModel, "default_settings")
        if not model:
            default_settings = AppSettings()
            model = SettingsModel.from_domain(default_settings)
            self._session.add(model)
            self._session.flush()
        return model.to_domain()

    def update(self, settings: AppSettings) -> AppSettings:
        model = self._session.get(SettingsModel, "default_settings")
        if not model:
            model = SettingsModel.from_domain(settings)
            model.id = "default_settings"
            self._session.add(model)
        else:
            model.music_download_directory = settings.music_download_directory
            model.default_audio_quality = settings.default_audio_quality.value
            model.normalize_audio_lufs = settings.normalize_audio_lufs
            model.auto_tag_metadata = settings.auto_tag_metadata
            model.updated_at = settings.updated_at

        self._session.flush()
        return model.to_domain()
