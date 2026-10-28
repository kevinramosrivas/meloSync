"""SQLAlchemy ORM models and database connection management with WAL mode."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    scoped_session,
    sessionmaker,
)

from ...domain.entities import (
    AppSettings,
    AudioQuality,
    DownloadStatus,
    Playlist,
    Track,
    TrackMetadata,
    get_default_music_dir,
    utc_now,
)

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy models."""
    pass


# Association table for Many-to-Many between Playlist and Track
playlist_tracks = Table(
    "playlist_tracks",
    Base.metadata,
    Column("playlist_id", String(36), ForeignKey("playlists.id", ondelete="CASCADE"), primary_key=True),
    Column("track_id", String(36), ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
)


class TrackModel(Base):
    """SQLAlchemy model for persisting Track entity."""
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    youtube_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    original_title: Mapped[str] = mapped_column(String(512), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    channel_name: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default=DownloadStatus.PENDIENTE.value, index=True)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata columns
    meta_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    meta_artist: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    meta_album: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    meta_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    meta_genre: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    meta_track_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    meta_disc_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    meta_cover_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    meta_cover_bytes: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    meta_lyrics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Play metrics
    play_count: Mapped[int] = mapped_column(Integer, default=0)
    last_played_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    playlists: Mapped[list[PlaylistModel]] = relationship(
        "PlaylistModel",
        secondary=playlist_tracks,
        back_populates="tracks",
    )

    def to_domain(self) -> Track:
        """Converts DB model to domain entity."""
        metadata = None
        if self.meta_title or self.meta_artist or self.meta_cover_url or self.meta_cover_bytes:
            metadata = TrackMetadata(
                title=self.meta_title or self.original_title,
                artist=self.meta_artist or self.channel_name or "Unknown Artist",
                album=self.meta_album or "Unknown Album",
                year=self.meta_year,
                genre=self.meta_genre,
                track_number=self.meta_track_number,
                disc_number=self.meta_disc_number,
                cover_url=self.meta_cover_url,
                cover_bytes=self.meta_cover_bytes,
                lyrics=self.meta_lyrics,
            )

        status_enum = DownloadStatus(self.status) if self.status in DownloadStatus._value2member_map_ else DownloadStatus.PENDIENTE

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
            play_count=self.play_count or 0,
            last_played_at=self.last_played_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, track: Track) -> TrackModel:
        """Creates DB model from domain entity."""
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
            play_count=track.play_count,
            last_played_at=track.last_played_at,
            created_at=track.created_at,
            updated_at=track.updated_at,
        )
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
        return model


class TrackPlayHistoryModel(Base):
    """SQLAlchemy model for recording individual track playback events."""
    __tablename__ = "track_play_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    track_id: Mapped[str] = mapped_column(String(36), ForeignKey("tracks.id", ondelete="CASCADE"), index=True, nullable=False)
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class PlaylistModel(Base):
    """SQLAlchemy model for Playlist entity."""
    __tablename__ = "playlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(String(1024), default="")
    is_smart: Mapped[bool] = mapped_column(Boolean, default=False)
    playlist_type: Mapped[str] = mapped_column(String(32), default="custom", index=True)
    filter_query: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    cover_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tracks: Mapped[list[TrackModel]] = relationship(
        "TrackModel",
        secondary=playlist_tracks,
        back_populates="playlists",
    )

    def to_domain(self) -> Playlist:
        """Converts model to domain entity."""
        return Playlist(
            id=self.id,
            name=self.name,
            description=self.description,
            is_smart=self.is_smart,
            playlist_type=self.playlist_type,
            filter_query=self.filter_query,
            cover_url=self.cover_url,
            tracks=[t.to_domain() for t in self.tracks],
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, p: Playlist) -> PlaylistModel:
        """Creates model from domain entity."""
        return cls(
            id=p.id,
            name=p.name,
            description=p.description,
            is_smart=p.is_smart,
            playlist_type=p.playlist_type,
            filter_query=p.filter_query,
            cover_url=p.cover_url,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )


class SettingsModel(Base):
    """SQLAlchemy model for global AppSettings."""
    __tablename__ = "settings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default="default_settings")
    music_download_directory: Mapped[str] = mapped_column(String(1024), nullable=False)
    default_audio_quality: Mapped[str] = mapped_column(String(32), default=AudioQuality.BEST.value)
    normalize_audio_lufs: Mapped[float] = mapped_column(Float, default=-14.0)
    auto_tag_metadata: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def to_domain(self) -> AppSettings:
        quality = AudioQuality(self.default_audio_quality) if self.default_audio_quality in AudioQuality._value2member_map_ else AudioQuality.BEST
        return AppSettings(
            id=self.id,
            music_download_directory=self.music_download_directory,
            default_audio_quality=quality,
            normalize_audio_lufs=self.normalize_audio_lufs,
            auto_tag_metadata=self.auto_tag_metadata,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, s: AppSettings) -> SettingsModel:
        return cls(
            id=s.id,
            music_download_directory=s.music_download_directory,
            default_audio_quality=s.default_audio_quality.value,
            normalize_audio_lufs=s.normalize_audio_lufs,
            auto_tag_metadata=s.auto_tag_metadata,
            updated_at=s.updated_at,
        )


class DatabaseManager:
    """Manages SQLite engine with WAL mode and thread-safe scoped sessions."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{db_path}"
        else:
            db_url = "sqlite:///:memory:"

        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )

        # Enable SQLite WAL mode and foreign keys
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        self.scoped_session = scoped_session(self.session_factory)

    def init_database(self) -> None:
        """Creates all database tables and runs lightweight column migrations if needed."""
        Base.metadata.create_all(self.engine)

        # Automatic column migration for existing SQLite databases
        with self.engine.connect() as conn:
            cursor = conn.connection.cursor()

            # 1. Migrate tracks table columns
            cursor.execute("PRAGMA table_info(tracks)")
            existing_track_cols = {row[1] for row in cursor.fetchall()}

            track_cols_to_add = {
                "meta_track_number": "INTEGER",
                "meta_disc_number": "INTEGER",
                "meta_cover_bytes": "BLOB",
                "meta_lyrics": "TEXT",
                "play_count": "INTEGER DEFAULT 0",
                "last_played_at": "DATETIME",
            }

            for col_name, col_type in track_cols_to_add.items():
                if col_name not in existing_track_cols and existing_track_cols:
                    try:
                        cursor.execute(f"ALTER TABLE tracks ADD COLUMN {col_name} {col_type}")
                        logger.info("Migrated column '%s' into 'tracks' table", col_name)
                    except Exception as e:
                        logger.warning("Could not add column %s to tracks: %s", col_name, e)

            # 2. Migrate playlists table columns
            cursor.execute("PRAGMA table_info(playlists)")
            existing_playlist_cols = {row[1] for row in cursor.fetchall()}

            playlist_cols_to_add = {
                "is_smart": "BOOLEAN DEFAULT 0",
                "playlist_type": "VARCHAR(32) DEFAULT 'custom'",
                "filter_query": "VARCHAR(256)",
                "cover_url": "VARCHAR(1024)",
            }

            for col_name, col_type in playlist_cols_to_add.items():
                if col_name not in existing_playlist_cols and existing_playlist_cols:
                    try:
                        cursor.execute(f"ALTER TABLE playlists ADD COLUMN {col_name} {col_type}")
                        logger.info("Migrated column '%s' into 'playlists' table", col_name)
                    except Exception as e:
                        logger.warning("Could not add column %s to playlists: %s", col_name, e)

            conn.connection.commit()

            # Automatic path self-healing for tracks pointing to unlocalized/stale paths
            cursor.execute("SELECT id, file_path FROM tracks WHERE file_path IS NOT NULL AND status = 'COMPLETADA'")
            tracks_to_check = cursor.fetchall()
            fixed_count = 0
            for t_id, f_path in tracks_to_check:
                if f_path and not Path(f_path).exists():
                    p_name = Path(f_path).name
                    candidates = [
                        Path.home() / "Música" / "meloSync" / p_name,
                        Path.home() / "Music" / "meloSync" / p_name,
                        Path.home() / "meloSync_Music" / p_name,
                    ]
                    for cand in candidates:
                        if cand.is_file():
                            cursor.execute("UPDATE tracks SET file_path = ? WHERE id = ?", (str(cand.resolve()), t_id))
                            fixed_count += 1
                            logger.info("Startup migration self-healed track path '%s' -> '%s'", t_id, cand)
                            break

            if fixed_count > 0:
                conn.connection.commit()
                logger.info("Startup migration self-healed %d stale track path(s)", fixed_count)

            cursor.close()

        logger.info("Database initialized successfully at '%s'", self._db_path)

    def get_session(self):
        """Returns a new session."""
        return self.scoped_session()
