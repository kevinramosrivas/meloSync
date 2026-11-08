"""Use Case: Consolidate and Migrate Library Track Audio Files.

Moves or copies track files from multiple or legacy directories into the
active music download directory and updates physical file paths in persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import shutil
from typing import Callable, Optional

from ..services.path_resolver import TrackFileResolver
from ...domain.entities import DownloadStatus
from ...domain.repositories import IUnitOfWork

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class ConsolidateReportDTO:
    """Outcome report for a library consolidation operation."""
    moved_count: int
    already_there_count: int
    missing_count: int
    total_tracks: int
    target_directory: str
    message: str


class ConsolidateLibraryUseCase:
    """Consolidates audio files into the target/active music directory."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(
        self,
        target_directory: Optional[str] = None,
        move_files: bool = True,
    ) -> ConsolidateReportDTO:
        moved_count = 0
        already_there_count = 0
        missing_count = 0

        with self._uow_factory() as uow:
            settings = uow.settings.get()
            target_str = target_directory or settings.music_download_directory
            target_dir = Path(target_str).resolve()
            target_dir.mkdir(parents=True, exist_ok=True)

            tracks = uow.tracks.list_by_status(DownloadStatus.COMPLETADA)
            total_tracks = len(tracks)

            for track in tracks:
                # 1. Resolve current physical file on disk
                resolved = TrackFileResolver.resolve(
                    track=track,
                    active_music_dir=str(target_dir),
                    uow=uow,
                )

                if not resolved or not resolved.exists():
                    missing_count += 1
                    continue

                resolved = resolved.resolve()

                # 2. Check if file is already inside target directory
                try:
                    if resolved.parent == target_dir or resolved.is_relative_to(target_dir):
                        already_there_count += 1
                        # Normalize path if changed
                        if track.file_path != str(resolved):
                            track.file_path = str(resolved)
                            uow.tracks.update(track)
                        continue
                except Exception:
                    pass

                # 3. Destination file path in target directory
                dest_filename = resolved.name
                dest_path = target_dir / dest_filename

                # Avoid collision if destination file exists
                counter = 1
                while dest_path.exists() and dest_path != resolved:
                    dest_path = target_dir / f"{resolved.stem}_{counter}{resolved.suffix}"
                    counter += 1

                # 4. Move or Copy
                try:
                    if move_files:
                        shutil.move(str(resolved), str(dest_path))
                    else:
                        shutil.copy2(str(resolved), str(dest_path))

                    track.file_path = str(dest_path)
                    uow.tracks.update(track)
                    moved_count += 1
                    logger.info("%s track %s: %s -> %s", "Moved" if move_files else "Copied", track.id, resolved, dest_path)
                except Exception as e:
                    logger.error("Failed to relocate file for track %s: %s", track.id, e)

            uow.commit()

        action_word = "movieron" if move_files else "copiaron"
        msg = f"Se {action_word} {moved_count} canciones a {target_dir}. {already_there_count} ya estaban allí."
        if missing_count > 0:
            msg += f" {missing_count} pistas no se encontraron en el disco."

        return ConsolidateReportDTO(
            moved_count=moved_count,
            already_there_count=already_there_count,
            missing_count=missing_count,
            total_tracks=total_tracks,
            target_directory=str(target_dir),
            message=msg,
        )

