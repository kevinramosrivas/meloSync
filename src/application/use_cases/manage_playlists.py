"""Use Cases: Manage playlists."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Optional

from src.domain.entities import Playlist
from src.domain.repositories import IUnitOfWork

logger = logging.getLogger(__name__)


class CreatePlaylistUseCase:
    """Creates a new user playlist."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, name: str, description: str = "") -> Playlist:
        """Persists and returns a newly created playlist."""
        with self._uow_factory() as uow:
            playlist = Playlist(name=name.strip(), description=description.strip())
            uow.playlists.add(playlist)
            uow.commit()
            return playlist


class AddTrackToPlaylistUseCase:
    """Adds a library track into an existing playlist."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, playlist_id: str, track_id: str) -> bool:
        """Adds track to playlist. Returns True on success."""
        with self._uow_factory() as uow:
            playlist = uow.playlists.get_by_id(playlist_id)
            track = uow.tracks.get_by_id(track_id)
            if not playlist or not track:
                return False

            playlist.add_track(track)
            uow.playlists.update(playlist)
            uow.commit()
            return True


class GetPlaylistsUseCase:
    """Retrieves all stored playlists."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self) -> list[Playlist]:
        """Returns all playlists."""
        with self._uow_factory() as uow:
            return uow.playlists.list_all()
