"""Use Cases: Manage Playlists."""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from ...domain.entities import Playlist
from ...domain.exceptions import PlaylistNotFoundException, TrackNotFoundException
from ...domain.repositories import IUnitOfWork


class CreatePlaylistUseCase:
    """Creates a new playlist."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, name: str, description: str = "") -> Playlist:
        playlist = Playlist(name=name, description=description)
        with self._uow_factory() as uow:
            return uow.playlists.add(playlist)


class GetPlaylistsUseCase:
    """Retrieves all playlists."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self) -> list[Playlist]:
        with self._uow_factory() as uow:
            return uow.playlists.list_all()


class AddTrackToPlaylistUseCase:
    """Adds a track to a playlist."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, playlist_id: str, track_id: str) -> Playlist:
        with self._uow_factory() as uow:
            playlist = uow.playlists.get_by_id(playlist_id)
            if not playlist:
                raise PlaylistNotFoundException(playlist_id)
            track = uow.tracks.get_by_id(track_id)
            if not track:
                raise TrackNotFoundException(track_id)

            playlist.add_track(track)
            return uow.playlists.update(playlist)
