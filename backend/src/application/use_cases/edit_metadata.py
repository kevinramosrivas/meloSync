"""Use Cases: Edit and update track metadata."""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
from typing import Optional

from ..dto import (
    TrackDTO,
    TrackMetadataDTO,
    UpdateTrackMetadataCommand,
)
from ...domain.entities import TrackMetadata
from ...domain.exceptions import TrackNotFoundException
from ...domain.repositories import IUnitOfWork
from ...domain.services import IMetadataProviderService, ITaggingService

logger = logging.getLogger(__name__)


class SearchMetadataCandidatesUseCase:
    """Queries external provider for alternative metadata candidates."""

    def __init__(self, metadata_provider: IMetadataProviderService) -> None:
        self._provider = metadata_provider

    def execute(self, query: str, limit: int = 15) -> list[TrackMetadataDTO]:
        candidates = self._provider.search_candidates(query, limit=limit)
        results: list[TrackMetadataDTO] = []
        for c in candidates:
            dto = TrackMetadataDTO.from_domain(c)
            if dto is not None:
                results.append(dto)
        return results


class UpdateTrackMetadataUseCase:
    """Updates a track's metadata, embeds new ID3 tags and cover art, and persists to DB."""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        metadata_provider: IMetadataProviderService,
        tagging_service: ITaggingService,
    ) -> None:
        self._uow_factory = uow_factory
        self._provider = metadata_provider
        self._tagger = tagging_service

    def execute(self, command: UpdateTrackMetadataCommand) -> TrackDTO:
        with self._uow_factory() as uow:
            track = uow.tracks.get_by_id(command.track_id)
            if not track:
                raise TrackNotFoundException(command.track_id)

            cover_bytes = command.cover_bytes
            if not cover_bytes and command.cover_url:
                cover_bytes = self._provider.download_cover_bytes(command.cover_url)

            # Build updated domain metadata
            new_metadata = TrackMetadata(
                title=command.title,
                artist=command.artist,
                album=command.album,
                year=command.year,
                genre=command.genre,
                track_number=command.track_number,
                cover_url=command.cover_url,
                cover_bytes=cover_bytes,
            )

            # Apply tags to physical file if it exists
            if track.file_path and Path(track.file_path).exists():
                try:
                    self._tagger.apply_tags(track.file_path, new_metadata)
                except Exception as e:
                    logger.warning("Could not update ID3 tags in file %s: %s", track.file_path, e)

            track.metadata = new_metadata
            updated = uow.tracks.update(track)
            return TrackDTO.from_domain(updated)
