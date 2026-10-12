"""Use Case: Synchronize and Reconcile Library.

Reconciles outdated/moved file paths using the Smart Path Resolver,
and discovers untracked audio files in the music folder to import them.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Callable, Optional
import uuid

from mutagen import File as MutagenFile

from ..services.path_resolver import TrackFileResolver
from ...domain.entities import DownloadStatus, Track, TrackMetadata
from ...domain.repositories import IUnitOfWork

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".m4a", ".flac", ".ogg", ".wav", ".opus"}


@dataclass(slots=True)
class SyncReportDTO:
    """Outcome report for a library synchronization operation."""
    repaired_count: int
    imported_count: int
    missing_count: int
    total_tracks: int
    message: str


class SyncLibraryUseCase:
    """Reconciles physical file paths and imports unindexed audio files."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, custom_music_dir: Optional[str] = None) -> SyncReportDTO:
        repaired_count = 0
        imported_count = 0
        missing_count = 0

        with self._uow_factory() as uow:
            settings = uow.settings.get()
            target_dir_str = custom_music_dir or settings.music_download_directory
            target_dir = Path(target_dir_str) if target_dir_str else Path.home() / "Música" / "meloSync"

            all_tracks = uow.tracks.list_all()

            # ---------------------------------------------------------
            # PHASE 1: Reconcile & Self-Heal Existing Database Records
            # ---------------------------------------------------------
            for track in all_tracks:
                if track.status != DownloadStatus.COMPLETADA:
                    continue

                old_path = track.file_path
                resolved = TrackFileResolver.resolve(
                    track=track,
                    active_music_dir=str(target_dir),
                    uow=uow,
                )

                if resolved:
                    if old_path != str(resolved):
                        repaired_count += 1
                else:
                    missing_count += 1

            # ---------------------------------------------------------
            # PHASE 2: Discover and Import Untracked Local Audio Files
            # ---------------------------------------------------------
            if target_dir.exists() and target_dir.is_dir():
                # Re-fetch or build existing canonical path index
                tracked_names = {
                    Path(t.file_path).name.lower()
                    for t in all_tracks
                    if t.file_path
                }

                try:
                    for file_path in target_dir.iterdir():
                        if not file_path.is_file():
                            continue

                        ext = file_path.suffix.lower()
                        if ext not in SUPPORTED_AUDIO_EXTENSIONS:
                            continue

                        # If filename already tracked in DB, skip
                        if file_path.name.lower() in tracked_names:
                            continue

                        # New unindexed file found: parse tags
                        new_track = self._create_track_from_file(file_path)
                        if new_track:
                            uow.tracks.add(new_track)
                            tracked_names.add(file_path.name.lower())
                            imported_count += 1
                            logger.info(
                                "Imported untracked audio file to library: '%s'",
                                file_path.name,
                            )
                except Exception as e:
                    logger.error("Error scanning music directory %s for imports: %s", target_dir, e)

            total_count = len(all_tracks) + imported_count

        msg = (
            f"Sincronización completada: {repaired_count} pistas reparadas, "
            f"{imported_count} nuevas pistas importadas, {missing_count} pendientes de ubicar."
        )

        return SyncReportDTO(
            repaired_count=repaired_count,
            imported_count=imported_count,
            missing_count=missing_count,
            total_tracks=total_count,
            message=msg,
        )

    def _create_track_from_file(self, file_path: Path) -> Optional[Track]:
        """Reads metadata from file and constructs a new completed Track entity."""
        try:
            stem = file_path.stem
            # Parse fallback artist and title from standard "Artist - Title" filename format
            default_artist = "Desconocido"
            default_title = stem
            if " - " in stem:
                parts = stem.split(" - ", 1)
                default_artist = parts[0].strip()
                default_title = parts[1].strip()

            title = default_title
            artist = default_artist
            album = "Álbum Desconocido"
            year = None
            genre = None
            track_num = None
            duration_secs = 0
            cover_bytes = None

            # Attempt tag extraction with mutagen
            try:
                audio = MutagenFile(str(file_path))
                if audio is not None:
                    if hasattr(audio.info, "length"):
                        duration_secs = int(audio.info.length)

                    # ID3 / MP3 tags
                    if hasattr(audio, "tags") and audio.tags:
                        tags = audio.tags
                        if "TIT2" in tags:
                            title = str(tags["TIT2"])
                        if "TPE1" in tags:
                            artist = str(tags["TPE1"])
                        if "TALB" in tags:
                            album = str(tags["TALB"])
                        if "TDRC" in tags:
                            try:
                                year = int(str(tags["TDRC"])[:4])
                            except Exception:
                                pass
                        if "TCON" in tags:
                            genre = str(tags["TCON"])
                        if "TRCK" in tags:
                            try:
                                track_num = int(str(tags["TRCK"]).split("/")[0])
                            except Exception:
                                pass

                        # Check APIC front cover
                        for k, v in tags.items():
                            if k.startswith("APIC"):
                                cover_bytes = getattr(v, "data", None)
                                break
            except Exception as tag_err:
                logger.debug("Could not read deep tags for %s: %s", file_path.name, tag_err)

            metadata = TrackMetadata(
                title=title,
                artist=artist,
                album=album,
                year=year,
                genre=genre,
                track_number=track_num,
                cover_bytes=cover_bytes,
            )

            track_id = str(uuid.uuid4())
            file_abs = str(file_path.resolve())

            return Track(
                id=track_id,
                youtube_id=f"local_{track_id[:8]}",
                url=f"local://{file_path.name}",
                original_title=stem,
                duration_seconds=duration_secs,
                channel_name=artist,
                status=DownloadStatus.COMPLETADA,
                progress_percent=100.0,
                file_path=file_abs,
                metadata=metadata,
            )
        except Exception as e:
            logger.error("Failed to construct track from file %s: %s", file_path, e)
            return None
