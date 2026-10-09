"""Regex-based YouTube title cleaner for separating artist and track title and stripping noise."""

from __future__ import annotations

import re

from src.domain.services import ITitleCleanerService

# Noise keywords commonly found in YouTube titles within parentheses or brackets
_KEYWORD_PATTERN = (
    r"official\s+video|music\s+video|official\s+music\s+video|video\s+oficial|"
    r"official\s+audio|audio\s+oficial|official|audio|video|"
    r"lyric\s+video|lyrics?|visualizer|remaster(?:ed)?(?:\s+\d{4})?|"
    r"en\s+vivo|live(?:\s+at\s+[\w\s]+)?|4k(?:\s+60fps)?|hd|hq|explicit"
)

# Pattern matching entire ( ... ) or [ ... ] containing noise keywords
_BRACKET_NOISE_REGEX = re.compile(
    r"[\(\[\{][^\(\)\[\]\{\}]*(?:" + _KEYWORD_PATTERN + r")[^\(\)\[\]\{\}]*[\)\]\}]",
    flags=re.IGNORECASE,
)

# Trailing pipe patterns like "| Official Video"
_TRAILING_PIPE_REGEX = re.compile(
    r"\|\s*(?:" + _KEYWORD_PATTERN + r").*$",
    flags=re.IGNORECASE,
)


class RegexTitleCleaner(ITitleCleanerService):
    """Cleans YouTube noise and extracts clean (Artist, Title) tuple."""

    def clean(self, raw_title: str) -> tuple[str, str]:
        """Strips tags, brackets, and splits into artist and title if delimiter exists."""
        text = raw_title.strip()

        # 1. Strip pipe trailers
        text = _TRAILING_PIPE_REGEX.sub("", text)

        # 2. Iteratively strip bracketed noise patterns
        prev = None
        while prev != text:
            prev = text
            text = _BRACKET_NOISE_REGEX.sub("", text)

        # 3. Clean leading/trailing quotes, parentheses and excess whitespace
        text = re.sub(r'["“”«»]', "", text)
        text = re.sub(r"\s+", " ", text).strip()

        # 4. Detect split delimiters: " - ", " – ", " — ", " : "
        delimiters = [" - ", " – ", " — ", " : "]
        for delim in delimiters:
            if delim in text:
                parts = text.split(delim, 1)
                artist = parts[0].strip()
                title = parts[1].strip()
                # Clean any lingering trailing punctuation
                artist = re.sub(r"^[^\w]+|[^\w]+$", "", artist).strip()
                title = re.sub(r"^[^\w]+|[^\w]+$", "", title).strip()
                return artist, title

        # If no delimiter, return empty artist and cleaned text as title
        cleaned_title = re.sub(r"^[^\w]+|[^\w]+$", "", text).strip()
        return "", cleaned_title or raw_title
