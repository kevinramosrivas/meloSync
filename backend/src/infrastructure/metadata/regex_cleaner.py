"""Regex-based YouTube video title cleaner."""

from __future__ import annotations

import re

from ...domain.services import ITitleCleanerService


class RegexTitleCleaner(ITitleCleanerService):
    """Cleans YouTube video titles to extract clean Artist and Track Title."""

    # Patterns to strip from title strings
    _NOISE_PATTERNS = [
        r"\[.*?\]",  # [Official Video], [Lyrics], etc.
        r"\(.*?official.*?\)",  # (Official Music Video), (Official Audio)
        r"\(.*?lyric.*?\)",  # (Lyric Video)
        r"\(.*?video.*?\)",  # (Music Video)
        r"\(.*?4k.*?\)",  # (4K)
        r"\(.*?hd.*?\)",  # (HD)
        r"\(.*?remastered.*?\)",  # (Remastered)
        r"\(.*?audio.*?\)",  # (Audio)
        r"\(.*?visualizer.*?\)",  # (Visualizer)
        r"\(.*?explicit.*?\)",  # (Explicit)
        r"\(.*?prod\..*?\)",  # (Prod. by ...)
        r"\bft\.?\s+.*?(?=[-(]|$)",  # ft. / feat.
        r"\bfeat\.?\s+.*?(?=[-(]|$)",
        r"#\w+",  # Hashtags
    ]

    def clean(self, raw_title: str) -> tuple[str, str]:
        """Extracts (artist, clean_title). If no separator found, artist is empty."""
        title = raw_title.strip()

        # Strip known noise
        for pattern in self._NOISE_PATTERNS:
            title = re.sub(pattern, "", title, flags=re.IGNORECASE)

        # Standardize separators
        title = re.sub(r"\s+", " ", title).strip()

        # Split on standard artist - title separators: " - ", " – ", " — ", " | ", ":"
        separators = [" - ", " – ", " — ", " | ", ": "]
        for sep in separators:
            if sep in title:
                parts = title.split(sep, 1)
                artist = parts[0].strip()
                track_title = parts[1].strip()
                # Remove stray trailing or leading parentheses/quotes
                track_title = track_title.strip(" \"'()")
                artist = artist.strip(" \"'()")
                return (artist, track_title)

        return ("", title.strip(" \"'()"))
