"""iTunes Search API client for retrieving official metadata and high-resolution (1000x1000) album artwork."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

import httpx

from src.domain.entities import TrackMetadata
from src.domain.services import IMetadataProviderService

logger = logging.getLogger(__name__)


def _to_hd_cover_url(url: str, size: int = 1000) -> str:
    """Replaces Apple CDN thumbnail dimensions with higher resolution."""
    if not url:
        return url
    return re.sub(r"/\d+x\d+bb\.", f"/{size}x{size}bb.", url)


class ITunesMetadataProvider(IMetadataProviderService):
    """Fetches official song metadata and 1000x1000 cover art from Apple's iTunes Search API."""

    BASE_URL = "https://itunes.apple.com/search"

    def __init__(self, timeout_seconds: float = 8.0) -> None:
        self.timeout = timeout_seconds

    def _parse_track_metadata(self, item: dict[str, Any], load_cover_bytes: bool = False) -> TrackMetadata:
        """Transforms an iTunes result JSON dictionary into a pure TrackMetadata entity."""
        title = item.get("trackName") or "Unknown Title"
        artist_name = item.get("artistName") or "Unknown Artist"
        album_name = item.get("collectionName") or "Single"

        # Parse release year
        year: Optional[int] = None
        release_date = item.get("releaseDate")
        if release_date:
            match_year = re.search(r"(\d{4})", release_date)
            if match_year:
                year = int(match_year.group(1))

        genre = item.get("primaryGenreName")
        track_number = item.get("trackNumber")
        disc_number = item.get("discNumber")

        # Cover Art URLs
        raw_cover = item.get("artworkUrl100") or item.get("artworkUrl60")
        cover_url = _to_hd_cover_url(raw_cover, 1000) if raw_cover else None

        cover_bytes: Optional[bytes] = None
        if load_cover_bytes and cover_url:
            cover_bytes = self.download_cover_bytes(cover_url)

        return TrackMetadata(
            title=title,
            artist=artist_name,
            album=album_name,
            year=year,
            genre=genre,
            track_number=track_number,
            disc_number=disc_number,
            cover_url=cover_url,
            cover_bytes=cover_bytes,
        )

    def download_cover_bytes(self, cover_url: str) -> Optional[bytes]:
        """Downloads artwork bytes from given Apple CDN URL, falling back if needed."""
        if not cover_url:
            return None
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(cover_url)
                if res.status_code == 200:
                    return res.content

                # Fallback to lower resolution if 1000x1000 fails
                fallback_url = _to_hd_cover_url(cover_url, 600)
                if fallback_url != cover_url:
                    res_fallback = client.get(fallback_url)
                    if res_fallback.status_code == 200:
                        return res_fallback.content

                orig_url = _to_hd_cover_url(cover_url, 100)
                if orig_url != cover_url:
                    res_orig = client.get(orig_url)
                    if res_orig.status_code == 200:
                        return res_orig.content
        except Exception as exc:
            logger.warning("Failed to download cover bytes from '%s': %s", cover_url, exc)
        return None

    def search_candidates(self, query: str, limit: int = 15) -> list[TrackMetadata]:
        """Searches Apple Music / iTunes and returns a list of candidate matching songs."""
        term = query.strip()
        if not term:
            return []

        params = {
            "term": term,
            "media": "music",
            "entity": "song",
            "limit": max(1, min(limit, 50)),
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.BASE_URL, params=params)
                if response.status_code != 200:
                    logger.warning("iTunes API returned status %d for query '%s'", response.status_code, term)
                    return []

                data: dict[str, Any] = response.json()
                results = data.get("results", [])
                candidates: list[TrackMetadata] = []
                for item in results:
                    candidates.append(self._parse_track_metadata(item, load_cover_bytes=False))
                return candidates
        except Exception as exc:
            logger.warning("iTunes candidate search failed for '%s': %s", term, exc)
            return []

    def lookup(self, query: str, artist: Optional[str] = None) -> Optional[TrackMetadata]:
        """Queries iTunes Search API and retrieves the highest match with cover bytes."""
        if artist and artist.lower() not in query.lower():
            term = f"{artist} {query}".strip()
        else:
            term = query.strip()
        if not term:
            return None

        params = {
            "term": term,
            "media": "music",
            "entity": "song",
            "limit": 5,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(self.BASE_URL, params=params)
                if response.status_code != 200:
                    logger.warning("iTunes API returned status %d for query '%s'", response.status_code, term)
                    return None

                data: dict[str, Any] = response.json()
                results = data.get("results", [])
                if not results:
                    logger.info("No iTunes results found for '%s'", term)
                    return None

                # Choose best result (first item or one matching artist if specified)
                match = results[0]
                if artist:
                    artist_lower = artist.lower()
                    for r in results:
                        if artist_lower in r.get("artistName", "").lower():
                            match = r
                            break

                meta = self._parse_track_metadata(match, load_cover_bytes=False)
                if meta.cover_url:
                    meta.cover_bytes = self.download_cover_bytes(meta.cover_url)

                return meta

        except Exception as exc:
            logger.warning("iTunes metadata lookup failed for '%s': %s", term, exc)
            return None
