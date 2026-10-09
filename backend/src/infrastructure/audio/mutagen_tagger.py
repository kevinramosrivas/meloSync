"""Mutagen audio tagging service for ID3 / MP4 tags and cover art embedding."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from mutagen.id3 import (
    APIC,
    ID3,
    ID3NoHeaderError,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TRCK,
    USLT,
)
from mutagen.mp3 import MP3

from ...domain.entities import TrackMetadata
from ...domain.exceptions import TaggingException
from ...domain.services import ITaggingService

logger = logging.getLogger(__name__)


class MutagenTaggingService(ITaggingService):
    """Embeds ID3v2.4 tags and high-resolution album cover artwork into MP3 files."""

    def apply_tags(self, audio_file_path: str, metadata: TrackMetadata) -> None:
        """Writes metadata tags (ID3v2.4) and APIC cover art to the target audio file."""
        file_path = Path(audio_file_path)
        if not file_path.exists():
            raise TaggingException(f"Archivo no encontrado para etiquetar: {audio_file_path}")

        try:
            try:
                tags = ID3(str(file_path))
            except ID3NoHeaderError:
                tags = ID3()

            # Set text frames
            if metadata.title:
                tags["TIT2"] = TIT2(encoding=3, text=metadata.title)
            if metadata.artist:
                tags["TPE1"] = TPE1(encoding=3, text=metadata.artist)
            if metadata.album:
                tags["TALB"] = TALB(encoding=3, text=metadata.album)
            if metadata.year:
                tags["TDRC"] = TDRC(encoding=3, text=str(metadata.year))
            if metadata.genre:
                tags["TCON"] = TCON(encoding=3, text=metadata.genre)
            if metadata.track_number:
                tags["TRCK"] = TRCK(encoding=3, text=str(metadata.track_number))
            if metadata.lyrics:
                tags["USLT"] = USLT(encoding=3, lang="eng", desc="", text=metadata.lyrics)

            # Embed cover art (APIC)
            if metadata.cover_bytes:
                # Detect mime type
                mime = "image/jpeg"
                if metadata.cover_bytes.startswith(b"\x89PNG"):
                    mime = "image/png"

                tags["APIC"] = APIC(
                    encoding=3,
                    mime=mime,
                    type=3,  # 3 is front cover
                    desc="Cover",
                    data=metadata.cover_bytes,
                )

            tags.save(str(file_path), v2_version=4)
            logger.info("Successfully tagged ID3v2.4 metadata to '%s'", file_path.name)

        except Exception as e:
            logger.error("Failed to tag audio file %s: %s", audio_file_path, e)
            raise TaggingException(f"Error al escribir etiquetas ID3: {e}") from e
