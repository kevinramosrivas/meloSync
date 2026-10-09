"""iTunes Search API metadata provider implementation."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from ...domain.entities import TrackMetadata
from ...domain.services import IMetadataProviderService

logger = logging.getLogger(__name__)


class ITunesMetadataProvider(IMetadataProviderService):
    """Fetches high-quality official metadata and 1000x1000 album artwork from Apple iTunes API."""

    _SEARCH_URL = "https://itunes.apple.com/search"

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self._timeout = timeout_seconds

    def _parse_entry(self, entry: dict[str, Any]) -> TrackMetadata:
        """Transforms an iTunes JSON entry into TrackMetadata domain entity."""
        title = entry.get("trackName") or entry.get("collectionName") or "Unknown Title"
        artist = entry.get("artistName") or "Unknown Artist"
        album = entry.get("collectionName") or "Unknown Album"
        genre = entry.get("primaryGenreName")
        track_number = entry.get("trackNumber")
        disc_number = entry.get("discNumber")

        # Extract release year
        year: Optional[int] = None
        release_date = entry.get("releaseDate")
        if release_date and len(release_date) >= 4:
            try:
                year = int(release_date[:4])
            except ValueError:
                pass

        # Upgrade artwork URL to 1000x1000 resolution
        raw_art = entry.get("artworkUrl100") or entry.get("artworkUrl60") or ""
        cover_url: Optional[str] = None
        if raw_art:
            cover_url = raw_art.replace("100x100bb", "1000x1000bb").replace("60x60bb", "1000x1000bb")

        return TrackMetadata(
            title=title,
            artist=artist,
            album=album,
            year=year,
            genre=genre,
            track_number=track_number,
            disc_number=disc_number,
            cover_url=cover_url,
        )

    def lookup(self, query: str, artist: Optional[str] = None) -> Optional[TrackMetadata]:
        """Performs search and returns top candidate with cover image bytes."""
        search_term = query
        if artist:
            search_term = f"{artist} {query}"

        candidates = self.search_candidates(search_term, limit=5)
        if not candidates:
            return None

        best_match = candidates[0]

        # Download high-res cover bytes
        if best_match.cover_url:
            best_match.cover_bytes = self.download_cover_bytes(best_match.cover_url)

        return best_match

    def search_candidates(self, query: str, limit: int = 15) -> list[TrackMetadata]:
        """Queries iTunes Search API and returns ranked candidates."""
        if not query or not query.strip():
            return []

        params = {
            "term": query.strip(),
            "media": "music",
            "entity": "song",
            "limit": limit,
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(self._SEARCH_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("iTunes API returned HTTP %d for query '%s'", resp.status_code, query)
                    return []

                data = resp.json()
                results = data.get("results", [])
                return [self._parse_entry(entry) for entry in results]

        except Exception as e:
            logger.warning("iTunes search exception for '%s': %s", query, e)
            return []

    def download_cover_bytes(self, cover_url: str) -> Optional[bytes]:
        """Downloads cover art image bytes."""
        if not cover_url:
            return None

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(cover_url)
                if resp.status_code == 200 and resp.content:
                    return resp.content
        except Exception as e:
            logger.warning("Failed to download cover from %s: %s", cover_url, e)

        return None
