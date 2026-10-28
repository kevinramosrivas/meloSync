"""iTunes Search API metadata provider implementation."""

from __future__ import annotations

import logging
import re
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

    @staticmethod
    def _extract_primary_artist(artist_name: str) -> str:
        """Extracts the primary artist name from collaborative or featured strings."""
        cleaned = re.sub(r'\(.*?\)|\[.*?\]', '', artist_name).strip()
        parts = re.split(r'\s+(?:&|feat\.?|ft\.?|vs\.?|x|with)\s+|,|\/', cleaned, flags=re.IGNORECASE)
        if parts and parts[0].strip():
            return parts[0].strip()
        return cleaned

    def lookup_artist_artwork(self, artist_name: str) -> Optional[str]:
        """Looks up real official artist portrait/photo from Deezer API with Apple iTunes fallback.
        
        Uses intelligent candidate ranking (matching exact name & highest nb_fan popularity),
        detects collaborations, and filters out broken/empty placeholder images.
        """
        if not artist_name or not artist_name.strip():
            return None

        artist_key = artist_name.strip().lower()
        if hasattr(self, "_artist_cache") and artist_key in self._artist_cache:
            return self._artist_cache[artist_key]

        if not hasattr(self, "_artist_cache"):
            self._artist_cache: dict[str, Optional[str]] = {}

        clean_q = artist_name.strip()
        primary = self._extract_primary_artist(clean_q)

        # Direct search first; if differed from primary artist, prepare fallback to primary
        queries_to_try = [clean_q]
        if primary.lower() != clean_q.lower():
            queries_to_try.append(primary)

        # 1. Primary: Search Deezer for genuine artist profile pictures / portraits (1000x1000)
        for q in queries_to_try:
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    deezer_resp = client.get(
                        "https://api.deezer.com/search/artist",
                        params={"q": q, "limit": 20},
                    )
                    if deezer_resp.status_code == 200:
                        data = deezer_resp.json()
                        items = data.get("data", [])
                        valid_items = [
                            i for i in items
                            if i.get("picture_xl")
                            and "/artist//" not in i.get("picture_xl")
                            and not i.get("picture_xl").endswith("/default")
                        ]
                        if not valid_items:
                            continue

                        # Tier 1: Exact match (case-insensitive) -> pick candidate with maximum fans
                        exact = [i for i in valid_items if i.get("name", "").strip().lower() == q.lower()]
                        if exact:
                            best = max(exact, key=lambda x: x.get("nb_fan", 0))
                            pic = best.get("picture_xl") or best.get("picture_big") or best.get("picture_medium")
                            if pic:
                                self._artist_cache[artist_key] = pic
                                return pic

                        # Tier 2: Normalized alphanumeric match -> pick candidate with maximum fans
                        norm_q = re.sub(r'[^a-zA-Z0-9]', '', q).lower()
                        norm = [
                            i for i in valid_items
                            if re.sub(r'[^a-zA-Z0-9]', '', i.get("name", "")).lower() == norm_q
                        ]
                        if norm:
                            best = max(norm, key=lambda x: x.get("nb_fan", 0))
                            pic = best.get("picture_xl") or best.get("picture_big") or best.get("picture_medium")
                            if pic:
                                self._artist_cache[artist_key] = pic
                                return pic

                        # Tier 3: Substring / Contains match with substantial following (> 100 fans)
                        contains = [
                            i for i in valid_items
                            if (q.lower() in i.get("name", "").lower() or i.get("name", "").lower() in q.lower())
                            and i.get("nb_fan", 0) > 100
                        ]
                        if contains:
                            best = max(contains, key=lambda x: x.get("nb_fan", 0))
                            pic = best.get("picture_xl") or best.get("picture_big") or best.get("picture_medium")
                            if pic:
                                self._artist_cache[artist_key] = pic
                                return pic

                        # Tier 4: Most popular valid item
                        best = max(valid_items, key=lambda x: x.get("nb_fan", 0))
                        pic = best.get("picture_xl") or best.get("picture_big") or best.get("picture_medium")
                        if pic:
                            self._artist_cache[artist_key] = pic
                            return pic

            except Exception as e:
                logger.debug("Deezer artist photo lookup failed for '%s': %s", q, e)

        # 2. Secondary fallback: Apple iTunes
        for q in queries_to_try:
            params = {
                "term": q,
                "media": "music",
                "entity": "song",
                "limit": 1,
            }
            try:
                with httpx.Client(timeout=self._timeout) as client:
                    resp = client.get(self._SEARCH_URL, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("results", [])
                        if results:
                            raw_art = results[0].get("artworkUrl100") or results[0].get("artworkUrl60") or ""
                            if raw_art:
                                art_url = raw_art.replace("100x100bb", "1000x1000bb").replace("60x60bb", "1000x1000bb")
                                self._artist_cache[artist_key] = art_url
                                return art_url
            except Exception as e:
                logger.debug("Failed iTunes artist lookup for '%s': %s", q, e)

        self._artist_cache[artist_key] = None
        return None

    def lookup_genre_artwork(self, genre_name: str) -> Optional[str]:
        """Looks up representative artwork URL for a genre."""
        if not genre_name or not genre_name.strip():
            return None

        genre_key = genre_name.strip().lower()
        if hasattr(self, "_genre_cache") and genre_key in self._genre_cache:
            return self._genre_cache[genre_key]

        if not hasattr(self, "_genre_cache"):
            self._genre_cache: dict[str, Optional[str]] = {}

        params = {
            "term": f"{genre_name.strip()} hits",
            "media": "music",
            "entity": "album",
            "limit": 1,
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(self._SEARCH_URL, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("results", [])
                    if results:
                        raw_art = results[0].get("artworkUrl100") or results[0].get("artworkUrl60") or ""
                        if raw_art:
                            art_url = raw_art.replace("100x100bb", "1000x1000bb").replace("60x60bb", "1000x1000bb")
                            self._genre_cache[genre_key] = art_url
                            return art_url
        except Exception as e:
            logger.debug("Failed genre lookup for '%s': %s", genre_name, e)

        self._genre_cache[genre_key] = None
        return None

    _MUSIC_KEYWORDS = (
        "cantante", "cantautor", "singer", "songwriter", "música", "music", "musical",
        "grupo", "band", "banda", "rapero", "rapera", "rapper", "boy band", "girl group",
        "k-pop", "reggaeton", "pop", "álbum", "album", "canción", "song",
        "discográfica", "vocalista", "compositor", "composer", "hip hop",
        "rock", "r&b", "solista", "discografía", "productor discográfico",
        "record producer", "dupla", "dúo", "boyband", "idols", "idol", "trapero",
    )

    def lookup_artist_bio(self, artist_name: str) -> Optional[str]:
        """Looks up a concise artist biography from Wikipedia REST API.

        Prefers Spanish and falls back to English. Verifies that the returned
        article is genuinely about a musician or band. Caches the result in memory.
        """
        if not artist_name or not artist_name.strip():
            return None

        artist_key = artist_name.strip().lower()
        if not hasattr(self, "_artist_bio_cache"):
            self._artist_bio_cache: dict[str, Optional[str]] = {}

        if artist_key in self._artist_bio_cache:
            return self._artist_bio_cache[artist_key]

        clean = re.sub(r'\(.*?\)|\[.*?\]', '', artist_name).strip()
        name_variants = list(dict.fromkeys([clean, clean.title(), clean.capitalize()]))

        headers = {"User-Agent": "MeloSync/1.0 (personal music player; info@melosync.app)"}

        def _fetch_summary(title: str, lang: str, client: httpx.Client) -> Optional[str]:
            import urllib.parse
            url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
            try:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("type") == "disambiguation":
                        return None
                    extract = data.get("extract", "").strip()
                    desc = (data.get("description") or "").lower()
                    if not extract:
                        return None
                    combined = f"{desc} {extract[:350]}".lower()
                    if any(kw in combined for kw in self._MUSIC_KEYWORDS):
                        # Clean bracket citations like [1] or [nota 1]
                        cleaned_extract = re.sub(r'\[.*?\]', '', extract).strip()
                        return cleaned_extract
            except Exception:
                pass
            return None

        try:
            with httpx.Client(timeout=3.0) as client:
                # 1. Fast path: Try bare name in Spanish and English
                for variant in name_variants:
                    for lang in ("es", "en"):
                        bio = _fetch_summary(variant, lang, client)
                        if bio:
                            self._artist_bio_cache[artist_key] = bio
                            return bio

                # 2. Musical disambiguation suffixes
                for variant in name_variants:
                    candidates = [
                        f"{variant} (cantante)",
                        f"{variant} (grupo musical)",
                        f"{variant} (banda)",
                        f"{variant} (rapero)",
                        f"{variant} (rapera)",
                        f"{variant} (cantante surcoreana)",
                        f"{variant} (cantante surcoreano)",
                        f"{variant} (singer)",
                        f"{variant} (band)",
                        f"{variant} (musician)",
                        f"{variant} (rapper)",
                    ]
                    for c in candidates:
                        for lang in ("es", "en"):
                            bio = _fetch_summary(c, lang, client)
                            if bio:
                                self._artist_bio_cache[artist_key] = bio
                                return bio
        except Exception as e:
            logger.debug("Failed Wikipedia artist bio lookup for '%s': %s", artist_name, e)

        self._artist_bio_cache[artist_key] = None
        return None
