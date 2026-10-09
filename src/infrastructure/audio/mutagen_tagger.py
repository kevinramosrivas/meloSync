"""Audio tagging service embedding ID3/MP4 metadata and cover artwork using Mutagen."""

from __future__ import annotations

import logging
from pathlib import Path

from mutagen.id3 import (
    APIC,
    ID3,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TRCK,
    TYER,
    ID3NoHeaderError,
)
from mutagen.mp4 import MP4, MP4Cover

from src.domain.entities import TrackMetadata
from src.domain.exceptions import TaggingException
from src.domain.services import ITaggingService

logger = logging.getLogger(__name__)


class MutagenTaggingService(ITaggingService):
    """Embeds ID3 and MP4 tags into audio files using Mutagen."""

    def apply_tags(self, audio_file_path: str, metadata: TrackMetadata) -> None:
        """Embeds metadata and optional cover artwork based on file extension."""
        path = Path(audio_file_path)
        if not path.exists():
            raise TaggingException(audio_file_path, "El archivo a etiquetar no existe.")

        ext = path.suffix.lower()
        try:
            if ext == ".mp3":
                self._apply_mp3_tags(path, metadata)
            elif ext in [".m4a", ".mp4", ".aac"]:
                self._apply_mp4_tags(path, metadata)
            else:
                logger.info("Unsupported audio format for metadata tagging: %s", ext)
        except Exception as e:
            if isinstance(e, TaggingException):
                raise
            raise TaggingException(audio_file_path, str(e)) from e

    def _apply_mp3_tags(self, path: Path, metadata: TrackMetadata) -> None:
        """Applies ID3v2.4 tags to MP3 file."""
        try:
            tags = ID3(str(path))
        except ID3NoHeaderError:
            tags = ID3()

        # Title, Artist, Album
        tags.add(TIT2(encoding=3, text=metadata.title))
        tags.add(TPE1(encoding=3, text=metadata.artist))
        tags.add(TALB(encoding=3, text=metadata.album))

        # Year / Date
        if metadata.year:
            tags.add(TDRC(encoding=3, text=str(metadata.year)))
            tags.add(TYER(encoding=3, text=str(metadata.year)))

        # Genre
        if metadata.genre:
            tags.add(TCON(encoding=3, text=metadata.genre))

        # Track number
        if metadata.track_number:
            tags.add(TRCK(encoding=3, text=str(metadata.track_number)))

        # Cover Art
        if metadata.cover_bytes:
            tags.delall("APIC")
            mime = "image/png" if metadata.cover_bytes.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"
            tags.add(
                APIC(
                    encoding=3,
                    mime=mime,
                    type=3,  # 3 is front cover
                    desc="Cover",
                    data=metadata.cover_bytes,
                )
            )

        tags.save(str(path), v2_version=4)
        logger.info("ID3 tags applied successfully to: %s", path.name)

    def _apply_mp4_tags(self, path: Path, metadata: TrackMetadata) -> None:
        """Applies MP4 atoms to M4A/MP4 container."""
        mp4 = MP4(str(path))
        if mp4.tags is None:
            mp4.add_tags()

        mp4.tags["\xa9nam"] = [metadata.title]
        mp4.tags["\xa9ART"] = [metadata.artist]
        mp4.tags["\xa9alb"] = [metadata.album]

        if metadata.year:
            mp4.tags["\xa9day"] = [str(metadata.year)]
        if metadata.genre:
            mp4.tags["\xa9gen"] = [metadata.genre]
        if metadata.track_number:
            mp4.tags["trkn"] = [(metadata.track_number, 0)]

        if metadata.cover_bytes:
            img_format = (
                MP4Cover.FORMAT_PNG
                if metadata.cover_bytes.startswith(b"\x89PNG\r\n\x1a\n")
                else MP4Cover.FORMAT_JPEG
            )
            mp4.tags["covr"] = [
                MP4Cover(metadata.cover_bytes, imageformat=img_format)
            ]

        mp4.save()
        logger.info("MP4 tags applied successfully to: %s", path.name)
