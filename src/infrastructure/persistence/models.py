"""SQLAlchemy 2.0 Declarative ORM models for Tracks and Playlists."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.entities import DownloadStatus, Playlist, Track, TrackMetadata
from src.infrastructure.persistence.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


playlist_tracks = Table(
    "playlist_tracks",
    Base.metadata,
    Column("playlist_id", String(36), ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True),
    Column("track_id", String(36), ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
)


class TrackModel(Base):
    """Database representation of a music track."""
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    youtube_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    original_title: Mapped[str] = mapped_column(String(512), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    channel_name: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default=DownloadStatus.PENDIENTE.value)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Enriched metadata fields
    meta_title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    meta_artist: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    meta_album: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    meta_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    meta_genre: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    meta_cover_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    def to_entity(self) -> Track:
        """Converts ORM model to pure Domain entity."""
        metadata: Optional[TrackMetadata] = None
        if self.meta_title or self.meta_artist:
            metadata = TrackMetadata(
                title=self.meta_title or self.original_title,
                artist=self.meta_artist or self.channel_name,
                album=self.meta_album or "Unknown Album",
                year=self.meta_year,
                genre=self.meta_genre,
                cover_url=self.meta_cover_url,
            )

        status_enum = DownloadStatus(self.status) if self.status in [s.value for s in DownloadStatus] else DownloadStatus.ERROR

        return Track(
            id=self.id,
            youtube_id=self.youtube_id,
            url=self.url,
            original_title=self.original_title,
            duration_seconds=self.duration_seconds,
            channel_name=self.channel_name,
            status=status_enum,
            progress_percent=self.progress_percent,
            file_path=self.file_path,
            error_message=self.error_message,
            metadata=metadata,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, track: Track) -> TrackModel:
        """Constructs ORM model from pure Domain entity."""
        model = cls(
            id=track.id,
            youtube_id=track.youtube_id,
            url=track.url,
            original_title=track.original_title,
            duration_seconds=track.duration_seconds,
            channel_name=track.channel_name,
            status=track.status.value,
            progress_percent=track.progress_percent,
            file_path=track.file_path,
            error_message=track.error_message,
            created_at=track.created_at,
            updated_at=track.updated_at,
        )
        if track.metadata:
            model.meta_title = track.metadata.title
            model.meta_artist = track.metadata.artist
            model.meta_album = track.metadata.album
            model.meta_year = track.metadata.year
            model.meta_genre = track.metadata.genre
            model.meta_cover_url = track.metadata.cover_url
        return model


class PlaylistModel(Base):
    """Database representation of a playlist."""
    __tablename__ = "playlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    tracks: Mapped[list[TrackModel]] = relationship(
        secondary=playlist_tracks,
        lazy="selectin",
    )

    def to_entity(self) -> Playlist:
        """Converts ORM model to pure Domain entity."""
        return Playlist(
            id=self.id,
            name=self.name,
            description=self.description,
            tracks=[t.to_entity() for t in self.tracks],
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, playlist: Playlist) -> PlaylistModel:
        """Constructs ORM model from pure Domain entity."""
        return cls(
            id=playlist.id,
            name=playlist.name,
            description=playlist.description,
            created_at=playlist.created_at,
            updated_at=playlist.updated_at,
        )
