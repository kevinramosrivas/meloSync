"""Domain repository and Unit of Work interfaces (Abstract Base Classes)."""

from abc import ABC, abstractmethod
from typing import Optional

from .entities import AppSettings, DownloadStatus, Playlist, Track


class ITrackRepository(ABC):
    """Abstract contract for Track persistence operations."""

    @abstractmethod
    def add(self, track: Track) -> Track:
        """Persists a new Track entity."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, track_id: str) -> Optional[Track]:
        """Retrieves a Track by its domain ID."""
        raise NotImplementedError

    @abstractmethod
    def get_by_youtube_id(self, youtube_id: str) -> Optional[Track]:
        """Retrieves a Track by its YouTube video ID."""
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[Track]:
        """Retrieves all tracks ordered by creation date desc."""
        raise NotImplementedError

    @abstractmethod
    def list_by_status(self, status: DownloadStatus) -> list[Track]:
        """Retrieves all tracks currently in a specific download status."""
        raise NotImplementedError

    @abstractmethod
    def update(self, track: Track) -> Track:
        """Updates an existing Track entity."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, track_id: str) -> bool:
        """Deletes a track record by its domain ID. Returns True if deleted."""
        raise NotImplementedError

    @abstractmethod
    def record_play(self, track_id: str) -> None:
        """Records a playback event, incrementing play_count and logging play history."""
        raise NotImplementedError

    @abstractmethod
    def get_top_played(self, limit: int = 50) -> list[Track]:
        """Returns completed tracks ordered by play count descending."""
        raise NotImplementedError

    @abstractmethod
    def get_on_repeat(self, days: int = 30, min_repeats: int = 2, limit: int = 30) -> list[Track]:
        """Returns completed tracks frequently repeated in recent history window."""
        raise NotImplementedError


class IPlaylistRepository(ABC):
    """Abstract contract for Playlist persistence operations."""

    @abstractmethod
    def add(self, playlist: Playlist) -> Playlist:
        """Persists a new Playlist."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, playlist_id: str) -> Optional[Playlist]:
        """Retrieves a Playlist by its domain ID."""
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[Playlist]:
        """Retrieves all playlists."""
        raise NotImplementedError

    @abstractmethod
    def list_by_type(self, playlist_type: str) -> list[Playlist]:
        """Retrieves all playlists of a specific type."""
        raise NotImplementedError

    @abstractmethod
    def get_by_filter(self, playlist_type: str, filter_query: str) -> Optional[Playlist]:
        """Retrieves a smart playlist matching type and filter query."""
        raise NotImplementedError

    @abstractmethod
    def update(self, playlist: Playlist) -> Playlist:
        """Updates an existing Playlist."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, playlist_id: str) -> bool:
        """Deletes a playlist record by its domain ID."""
        raise NotImplementedError


class ISettingsRepository(ABC):
    """Abstract contract for AppSettings persistence."""

    @abstractmethod
    def get(self) -> AppSettings:
        """Retrieves current application settings, creating defaults if not set."""
        raise NotImplementedError

    @abstractmethod
    def update(self, settings: AppSettings) -> AppSettings:
        """Saves/updates application settings."""
        raise NotImplementedError


class IUnitOfWork(ABC):
    """Unit of Work interface to guarantee atomic transactions and scoped thread-safety."""

    tracks: ITrackRepository
    playlists: IPlaylistRepository
    settings: ISettingsRepository

    @abstractmethod
    def __enter__(self) -> "IUnitOfWork":
        """Enters transaction context."""
        raise NotImplementedError

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exits transaction context, rolling back if an unhandled exception occurred."""
        raise NotImplementedError

    @abstractmethod
    def commit(self) -> None:
        """Flushes and commits the current transaction."""
        raise NotImplementedError

    @abstractmethod
    def rollback(self) -> None:
        """Rolls back changes in current transaction."""
        raise NotImplementedError
