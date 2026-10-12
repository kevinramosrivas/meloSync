"""Smart Path Resolver & Auto-Healing Service for Track Audio Files.

Under industry standards, audio paths are dynamically reconciled across directory
moves, OS localized shell folders (Music vs Música), and custom storage settings.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from ...domain.entities import Track
from ...domain.repositories import IUnitOfWork

logger = logging.getLogger(__name__)


class TrackFileResolver:
    """Resolves physical audio files on disk and self-heals stale database paths."""

    @staticmethod
    def resolve(
        track: Track,
        active_music_dir: Optional[str] = None,
        uow: Optional[IUnitOfWork] = None,
    ) -> Optional[Path]:
        """Resolves the physical file path for a track.
        
        If the stored path is invalid but the file exists in the active music
        directory or a localized sibling folder, updates the database and returns the valid path.
        """
        # 1. Direct path check
        if track.file_path:
            direct_path = Path(track.file_path)
            try:
                if direct_path.is_file():
                    return direct_path
            except Exception:
                pass

        # 2. Extract target filename
        filename = Path(track.file_path).name if track.file_path else None
        if not filename and track.original_title:
            filename = f"{track.original_title}.mp3"

        if not filename:
            return None

        # 3. Build search directories list (ordered by priority)
        search_dirs: list[Path] = []
        if active_music_dir:
            search_dirs.append(Path(active_music_dir))

        # Check localized alternatives for Windows (Music <-> Música)
        if track.file_path:
            path_str = track.file_path
            if "\\Music\\" in path_str or "/Music/" in path_str:
                alt = path_str.replace("\\Music\\", "\\Música\\").replace("/Music/", "/Música/")
                search_dirs.append(Path(alt).parent)
            elif "\\Música\\" in path_str or "/Música/" in path_str:
                alt = path_str.replace("\\Música\\", "\\Music\\").replace("/Música/", "/Music/")
                search_dirs.append(Path(alt).parent)

        # Standard OS music directory candidates
        home = Path.home()
        search_dirs.extend([
            home / "Música" / "meloSync",
            home / "Music" / "meloSync",
            home / "meloSync_Music",
        ])

        # 4. Search for exact filename in candidate directories
        for directory in search_dirs:
            if not directory.exists() or not directory.is_dir():
                continue

            target = directory / filename
            try:
                if target.is_file():
                    return TrackFileResolver._auto_heal(track, target, uow)
            except Exception:
                continue

        # 5. Fuzzy / Case-insensitive match in active directories
        for directory in search_dirs:
            if not directory.exists() or not directory.is_dir():
                continue

            try:
                for entry in directory.iterdir():
                    if not entry.is_file():
                        continue
                    # Case-insensitive filename match
                    if entry.name.lower() == filename.lower():
                        return TrackFileResolver._auto_heal(track, entry, uow)
            except Exception as e:
                logger.debug("Error iterating %s during track resolution: %s", directory, e)

        logger.warning(
            "Could not resolve physical file for track '%s' (stored path: '%s')",
            track.id,
            track.file_path,
        )
        return None

    @staticmethod
    def _auto_heal(track: Track, new_path: Path, uow: Optional[IUnitOfWork] = None) -> Path:
        """Updates track in database with the newly confirmed valid path."""
        resolved_str = str(new_path.resolve())
        old_str = track.file_path
        track.file_path = resolved_str

        logger.info(
            "Auto-healed path for track '%s' (%s): '%s' -> '%s'",
            track.id,
            track.display_title,
            old_str,
            resolved_str,
        )

        if uow:
            try:
                uow.tracks.update(track)
            except Exception as e:
                logger.warning("Could not persist auto-healed path for track %s: %s", track.id, e)

        return new_path
