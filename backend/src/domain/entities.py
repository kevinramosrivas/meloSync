"""Domain entities, value objects, and enums for meloSync."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
import uuid

from .exceptions import InvalidStateTransitionException


def utc_now() -> datetime:
    """Returns current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def get_default_music_dir() -> str:
    """Returns the default music directory path for the current OS."""
    candidates = [
        Path.home() / "Music" / "meloSync",
        Path.home() / "Música" / "meloSync",
        Path.home() / "meloSync_Music",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return str(candidate)
        except Exception:
            continue
    fallback = Path.home() / "meloSync_Music"
    fallback.mkdir(parents=True, exist_ok=True)
    return str(fallback)


class DownloadStatus(str, Enum):
    """Execution state machine for a track's lifecycle."""
    PENDIENTE = "PENDIENTE"
    DESCARGANDO = "DESCARGANDO"
    PROCESANDO_AUDIO = "PROCESANDO_AUDIO"
    OBTENIENDO_METADATOS = "OBTENIENDO_METADATOS"
    COMPLETADA = "COMPLETADA"
    ERROR = "ERROR"
    CANCELADA = "CANCELADA"


class AudioQuality(str, Enum):
    """Audio quality targets for extraction."""
    BEST = "best"
    HIGH_320K = "320k"
    MID_256K = "256k"
    LOW_128K = "128k"


@dataclass(slots=True)
class TrackMetadata:
    """Enriched track metadata from external providers (e.g. iTunes)."""
    title: str
    artist: str
    album: str = "Unknown Album"
    year: Optional[int] = None
    genre: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None
    cover_url: Optional[str] = None
    cover_bytes: Optional[bytes] = None
    lyrics: Optional[str] = None

    def __post_init__(self) -> None:
        self.title = self.title.strip() if self.title else "Unknown Title"
        self.artist = self.artist.strip() if self.artist else "Unknown Artist"
        self.album = self.album.strip() if self.album else "Unknown Album"


@dataclass(slots=True)
class SearchResult:
    """YouTube search result item with metadata and duration."""
    youtube_id: str
    title: str
    duration_seconds: int
    channel_name: str
    thumbnail_url: str
    url: str

    @property
    def duration_formatted(self) -> str:
        """Returns human-readable duration (MM:SS or HH:MM:SS)."""
        minutes, seconds = divmod(self.duration_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


# Permitted transition graph for the state machine
_ALLOWED_TRANSITIONS: dict[DownloadStatus, set[DownloadStatus]] = {
    DownloadStatus.PENDIENTE: {
        DownloadStatus.DESCARGANDO,
        DownloadStatus.ERROR,
        DownloadStatus.CANCELADA,
    },
    DownloadStatus.DESCARGANDO: {
        DownloadStatus.PROCESANDO_AUDIO,
        DownloadStatus.ERROR,
        DownloadStatus.CANCELADA,
    },
    DownloadStatus.PROCESANDO_AUDIO: {
        DownloadStatus.OBTENIENDO_METADATOS,
        DownloadStatus.ERROR,
        DownloadStatus.CANCELADA,
    },
    DownloadStatus.OBTENIENDO_METADATOS: {
        DownloadStatus.COMPLETADA,
        DownloadStatus.ERROR,
        DownloadStatus.CANCELADA,
    },
    DownloadStatus.COMPLETADA: {
        DownloadStatus.PENDIENTE,  # Permite re-descarga voluntaria
    },
    DownloadStatus.ERROR: {
        DownloadStatus.PENDIENTE,  # Permite reintento
    },
    DownloadStatus.CANCELADA: {
        DownloadStatus.PENDIENTE,  # Permite reintento
    },
}


@dataclass
class Track:
    """Aggregate Root representing a music track and its downloading pipeline state."""
    youtube_id: str
    url: str
    original_title: str
    duration_seconds: int = 0
    channel_name: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: DownloadStatus = DownloadStatus.PENDIENTE
    progress_percent: float = 0.0
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[TrackMetadata] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def display_title(self) -> str:
        """Returns enriched title if available, otherwise original YouTube title."""
        if self.metadata and self.metadata.title:
            return self.metadata.title
        return self.original_title

    @property
    def display_artist(self) -> str:
        """Returns enriched artist if available, otherwise channel name."""
        if self.metadata and self.metadata.artist:
            return self.metadata.artist
        return self.channel_name or "Desconocido"

    @property
    def display_album(self) -> str:
        """Returns enriched album or default label."""
        if self.metadata and self.metadata.album:
            return self.metadata.album
        return "Sencillo"

    @property
    def duration_formatted(self) -> str:
        """Formatted duration string (MM:SS)."""
        minutes, seconds = divmod(self.duration_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def transition_to(self, target_status: DownloadStatus, reason: str = "") -> None:
        """Transitions track state validating the state machine rules."""
        if target_status == self.status:
            return

        allowed = _ALLOWED_TRANSITIONS.get(self.status, set())
        if target_status not in allowed:
            raise InvalidStateTransitionException(
                current_state=self.status.value,
                target_state=target_status.value,
                reason=reason or f"Transición no permitida desde {self.status.value} a {target_status.value}"
            )

        self.status = target_status
        self.updated_at = utc_now()

    def update_progress(self, percent: float) -> None:
        """Updates download/processing percentage (clamped between 0.0 and 100.0)."""
        self.progress_percent = max(0.0, min(100.0, round(percent, 2)))
        self.updated_at = utc_now()

    def mark_downloading(self) -> None:
        """Enters downloading stage."""
        self.transition_to(DownloadStatus.DESCARGANDO)
        self.error_message = None

    def mark_processing_audio(self) -> None:
        """Enters audio processing stage (ffmpeg loudnorm & silence trim)."""
        self.transition_to(DownloadStatus.PROCESANDO_AUDIO)

    def mark_fetching_metadata(self) -> None:
        """Enters metadata enrichment stage (iTunes API)."""
        self.transition_to(DownloadStatus.OBTENIENDO_METADATOS)

    def mark_completed(self, final_file_path: str, metadata: Optional[TrackMetadata] = None) -> None:
        """Marks track as successfully processed, tagged and saved."""
        self.transition_to(DownloadStatus.COMPLETADA)
        self.file_path = final_file_path
        if metadata:
            self.metadata = metadata
        self.progress_percent = 100.0
        self.error_message = None

    def mark_error(self, message: str) -> None:
        """Records error and transitions state to ERROR."""
        self.error_message = message
        self.status = DownloadStatus.ERROR
        self.updated_at = utc_now()

    def mark_cancelled(self) -> None:
        """Cancels download pipeline."""
        self.transition_to(DownloadStatus.CANCELADA)


@dataclass
class Playlist:
    """Represents a collection of tracks."""
    name: str
    description: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tracks: list[Track] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def add_track(self, track: Track) -> None:
        """Adds a track if not already in playlist."""
        if any(t.id == track.id for t in self.tracks):
            return
        self.tracks.append(track)
        self.updated_at = utc_now()

    def remove_track(self, track_id: str) -> None:
        """Removes a track from the playlist by ID."""
        self.tracks = [t for t in self.tracks if t.id != track_id]
        self.updated_at = utc_now()


@dataclass
class AppSettings:
    """Configurable global application settings."""
    music_download_directory: str = field(default_factory=get_default_music_dir)
    default_audio_quality: AudioQuality = AudioQuality.BEST
    normalize_audio_lufs: float = -14.0
    auto_tag_metadata: bool = True
    id: str = "default_settings"
    updated_at: datetime = field(default_factory=utc_now)
