"""Use Cases: Manage Library tracks."""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
from typing import Optional

from ..dto import TrackDTO
from ...domain.entities import DownloadStatus
from ...domain.exceptions import TrackNotFoundException
from ...domain.repositories import IUnitOfWork

logger = logging.getLogger(__name__)


class GetLibraryTracksUseCase:
    """Retrieves tracks from the persistence store."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, status: Optional[DownloadStatus] = None) -> list[TrackDTO]:
        """Returns all tracks, optionally filtered by status."""
        with self._uow_factory() as uow:
            if status:
                tracks = uow.tracks.list_by_status(status)
            else:
                tracks = uow.tracks.list_all()
            return [TrackDTO.from_domain(t) for t in tracks]


class GetTrackByIdUseCase:
    """Retrieves a single track by its domain ID."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, track_id: str) -> Optional[TrackDTO]:
        with self._uow_factory() as uow:
            track = uow.tracks.get_by_id(track_id)
            if not track:
                return None
            return TrackDTO.from_domain(track)


class DeleteTrackUseCase:
    """Deletes a track record and optionally its downloaded audio file."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, track_id: str, delete_file: bool = True) -> bool:
        with self._uow_factory() as uow:
            track = uow.tracks.get_by_id(track_id)
            if not track:
                raise TrackNotFoundException(track_id)

            if delete_file and track.file_path:
                file = Path(track.file_path)
                if file.exists():
                    try:
                        file.unlink()
                        logger.info("Deleted audio file from disk: %s", file)
                    except Exception as e:
                        logger.warning("Could not delete file %s: %s", file, e)

            success = uow.tracks.delete(track_id)
            return success
