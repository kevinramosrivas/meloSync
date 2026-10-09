"""Use Cases: Manage local music library (query, search local, delete)."""

from __future__ import annotations

from collections.abc import Callable
import logging
import os
from typing import Optional

from src.application.dto import TrackDTO
from src.domain.entities import DownloadStatus
from src.domain.repositories import IUnitOfWork

logger = logging.getLogger(__name__)


class GetLibraryTracksUseCase:
    """Retrieves tracks stored in the local music library."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, status: Optional[DownloadStatus] = None, search_query: str = "") -> list[TrackDTO]:
        """Returns library tracks filtered optionally by status or keyword."""
        with self._uow_factory() as uow:
            if status:
                tracks = uow.tracks.list_by_status(status)
            else:
                tracks = uow.tracks.list_all()

            if search_query:
                q = search_query.lower().strip()
                tracks = [
                    t for t in tracks
                    if q in t.display_title.lower()
                    or q in t.display_artist.lower()
                    or q in t.display_album.lower()
                ]

            return [TrackDTO.from_entity(t) for t in tracks]


class DeleteTrackUseCase:
    """Deletes a track from the library database and removes the audio file from disk."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, track_id: str, delete_file: bool = True) -> bool:
        """Deletes track record and optionally deletes physical file."""
        with self._uow_factory() as uow:
            track = uow.tracks.get_by_id(track_id)
            if not track:
                logger.warning("Attempted to delete non-existent track: %s", track_id)
                return False

            if delete_file and track.file_path and os.path.exists(track.file_path):
                try:
                    os.remove(track.file_path)
                    logger.info("Deleted audio file from disk: %s", track.file_path)
                except OSError as e:
                    logger.warning("Could not delete audio file '%s': %s", track.file_path, e)

            success = uow.tracks.delete(track_id)
            uow.commit()
            return success


class GetTrackByIdUseCase:
    """Retrieves a single track by its domain ID."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, track_id: str) -> Optional[TrackDTO]:
        """Returns TrackDTO if found, None otherwise."""
        with self._uow_factory() as uow:
            track = uow.tracks.get_by_id(track_id)
            if not track:
                return None
            return TrackDTO.from_entity(track)
