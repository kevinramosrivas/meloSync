"""Use Cases: Search Apple Music metadata candidates and update track metadata."""

from __future__ import annotations

from collections.abc import Callable
import logging
import os
from pathlib import Path
import re
from typing import Optional

from src.application.dto import MetadataCandidateDTO, TrackDTO, UpdateTrackMetadataCommand
from src.domain.entities import TrackMetadata
from src.domain.repositories import IUnitOfWork
from src.domain.services import IMetadataProviderService, ITaggingService

logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    """Removes invalid filesystem characters for Windows/POSIX."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    return clean.strip() or "track"


class SearchMetadataCandidatesUseCase:
    """Queries Apple Music / iTunes for multiple candidate tracks matching the search term."""

    def __init__(self, metadata_provider: IMetadataProviderService) -> None:
        self._metadata_provider = metadata_provider

    def execute(self, query: str, limit: int = 15) -> list[MetadataCandidateDTO]:
        """Returns candidate metadata entries from Apple Music."""
        if not query or not query.strip():
            return []

        candidates = self._metadata_provider.search_candidates(query=query.strip(), limit=limit)
        results: list[MetadataCandidateDTO] = []
        for c in candidates:
            thumb_url = None
            if c.cover_url:
                thumb_url = re.sub(r"/\d+x\d+bb\.", "/200x200bb.", c.cover_url)

            results.append(
                MetadataCandidateDTO(
                    title=c.title,
                    artist=c.artist,
                    album=c.album,
                    year=c.year,
                    genre=c.genre,
                    track_number=c.track_number,
                    disc_number=c.disc_number,
                    cover_url=c.cover_url,
                    thumbnail_url=thumb_url,
                )
            )
        return results


class UpdateTrackMetadataUseCase:
    """Updates track metadata, embeds ID3/MP4 tags into physical audio file, and updates database."""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        metadata_provider: IMetadataProviderService,
        tagging_service: ITaggingService,
    ) -> None:
        self._uow_factory = uow_factory
        self._metadata_provider = metadata_provider
        self._tagging_service = tagging_service

    def execute(self, command: UpdateTrackMetadataCommand) -> TrackDTO:
        """Executes metadata update, tag injection, file renaming, and persistence."""
        with self._uow_factory() as uow:
            track = uow.tracks.get_by_id(command.track_id)
            if not track:
                raise ValueError(f"Track with ID '{command.track_id}' not found.")

            cover_bytes = command.cover_bytes
            # Download cover bytes if not already provided in memory but URL is set
            if not cover_bytes and command.cover_url:
                try:
                    cover_bytes = self._metadata_provider.download_cover_bytes(command.cover_url)
                except Exception as e:
                    logger.warning("Failed to download cover bytes for update: %s", e)

            # If still no cover_bytes, check if track already had cover bytes or we keep existing
            updated_metadata = TrackMetadata(
                title=command.title.strip() or track.original_title,
                artist=command.artist.strip() or track.channel_name or "Unknown Artist",
                album=command.album.strip() or "Unknown Album",
                year=command.year,
                genre=command.genre.strip() if command.genre else None,
                track_number=command.track_number,
                cover_url=command.cover_url or (track.metadata.cover_url if track.metadata else None),
                cover_bytes=cover_bytes,
            )

            # 1. Apply tags to physical file if it exists
            if track.file_path and os.path.exists(track.file_path):
                try:
                    self._tagging_service.apply_tags(track.file_path, updated_metadata)
                    logger.info("Successfully tagged audio file at '%s'", track.file_path)
                except Exception as tag_err:
                    logger.warning("Could not apply tags to audio file '%s': %s", track.file_path, tag_err)

                # 2. Rename file to standard format if requested
                if command.rename_file:
                    current_path = Path(track.file_path)
                    parent_dir = current_path.parent
                    ext = current_path.suffix
                    safe_artist = _sanitize_filename(updated_metadata.artist)
                    safe_title = _sanitize_filename(updated_metadata.title)
                    new_filename = f"{safe_artist} - {safe_title}{ext}"
                    new_path = parent_dir / new_filename

                    # Avoid collision with other files
                    if new_path.resolve() != current_path.resolve():
                        counter = 1
                        while new_path.exists() and new_path.resolve() != current_path.resolve():
                            new_path = parent_dir / f"{safe_artist} - {safe_title} ({counter}){ext}"
                            counter += 1

                        try:
                            os.replace(current_path, new_path)
                            track.file_path = str(new_path)
                            logger.info("Renamed audio file to '%s'", track.file_path)
                        except OSError as ren_err:
                            logger.warning("Could not rename file '%s' to '%s': %s", current_path, new_path, ren_err)

            # 3. Update domain entity and persist to DB
            track.metadata = updated_metadata
            uow.tracks.update(track)
            uow.commit()

            logger.info("Track metadata updated successfully for ID '%s': %s", track.id, track.display_title)
            return TrackDTO.from_entity(track)
