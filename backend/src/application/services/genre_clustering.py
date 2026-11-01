import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Optional, Any
from ...domain.entities import Track

CANONICAL_GENRES: dict[str, str] = {
    "kpop": "K-Pop",
    "koreanpop": "K-Pop",
    "jpop": "J-Pop",
    "japanesepop": "J-Pop",
    "cpop": "C-Pop",
    "chinesepop": "C-Pop",
    "hiphop": "Hip-Hop",
    "rap": "Hip-Hop",
    "rnb": "R&B",
    "rb": "R&B",
    "rhythmandblues": "R&B",
    "edm": "EDM",
    "electronic": "Electronic",
    "electronica": "Electronic",
    "electro": "Electronic",
    "dance": "Dance",
    "dancemusic": "Dance",
    "soundtrack": "Soundtrack",
    "soundtracks": "Soundtrack",
    "ost": "Soundtrack",
    "score": "Soundtrack",
    "originalsoundtrack": "Soundtrack",
    "latinrap": "Latin Rap",
    "latinurban": "Latin Urban",
    "reggaeton": "Reggaeton",
    "regueton": "Reggaeton",
    "lofi": "Lo-Fi",
    "chillhop": "Lo-Fi",
    "rock": "Rock",
    "pop": "Pop",
    "indierock": "Indie Rock",
    "indiepop": "Indie Pop",
    "indie": "Indie",
    "alternativerock": "Alternative Rock",
    "alternative": "Alternative",
    "metal": "Metal",
    "heavymetal": "Heavy Metal",
    "jazz": "Jazz",
    "classical": "Classical",
    "blues": "Blues",
    "soul": "Soul",
    "funk": "Funk",
    "disco": "Disco",
    "country": "Country",
    "folk": "Folk",
    "acoustic": "Acoustic",
    "ambient": "Ambient",
    "synthwave": "Synthwave",
    "trap": "Trap",
    "house": "House",
    "techno": "Techno",
}

class GenreClusterer:
    """Intelligently cleans, splits, normalizes, and clusters music genres with proximity matching."""

    @staticmethod
    def extract_genres(raw_genre: Optional[str]) -> list[str]:
        """Extracts individual genre tags from potentially delimited or multi-genre strings."""
        if not raw_genre or not raw_genre.strip():
            return []

        cleaned = raw_genre.strip()

        # Handle specific common acronyms with spaces or ampersands like "R & B" or "R&B"
        if re.match(r'^(?:r\s*&\s*b|rnb)$', cleaned, re.IGNORECASE):
            return ["R&B"]

        # Split on commas, semicolons, pipes, slashes, or standalone " & " / " and "
        parts = re.split(r'[,;|/]|\s+(?:&|and)\s+', cleaned)
        results: list[str] = []

        for p in parts:
            token = p.strip().strip('"\'()[]{}')
            if not token:
                continue
            lower_token = token.lower()
            if lower_token in ("unknown", "other", "genre", "various", "music", "none", "desconocido", ""):
                continue
            results.append(token)

        return results

    @staticmethod
    def slugify(text: str) -> str:
        """Generates a simplified alphanumeric slug for robust fuzzy and proximity matching."""
        if not text:
            return ""

        # Normalize special cases like R&B -> rnb
        if re.match(r'^(?:r\s*&\s*b|rnb)$', text, re.IGNORECASE):
            return "rnb"

        decomposed = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        slug = re.sub(r'[^a-z0-9]', '', decomposed.lower())

        # Basic plural normalization for words > 4 characters (soundtracks -> soundtrack)
        if len(slug) > 4 and slug.endswith('s') and not slug.endswith(('ss', 'us', 'is', 'es', 'as')):
            slug = slug[:-1]

        return slug

    @classmethod
    def get_canonical_name(cls, raw_genre: str) -> str:
        """Returns the canonical display title for a genre, applying known standards or smart title-casing."""
        slug = cls.slugify(raw_genre)
        if slug in CANONICAL_GENRES:
            return CANONICAL_GENRES[slug]

        # Preserve hyphens while title-casing individual tokens (e.g. post-punk -> Post-Punk)
        tokens = re.split(r'(\s+|-)', raw_genre.strip())
        capitalized = "".join(
            t.capitalize() if re.match(r'^[a-zA-Z0-9]+$', t) else t
            for t in tokens
        )
        return capitalized

    @classmethod
    def cluster_tracks(cls, tracks: list[Track]) -> dict[str, list[Track]]:
        """
        Clusters completed tracks by canonical genre using slug normalization and proximity matching.
        Returns a mapping of {canonical_genre_name: list_of_unique_tracks}.
        """
        # cluster_slug -> {"canonical": str, "tracks": list[Track], "variants": list[str]}
        clusters: dict[str, dict[str, Any]] = {}

        for track in tracks:
            raw_genre_field = track.metadata.genre if track.metadata and track.metadata.genre else None
            extracted_genres = cls.extract_genres(raw_genre_field)

            for raw in extracted_genres:
                slug = cls.slugify(raw)
                if not slug:
                    continue

                matched_slug = None

                # 1. Exact canonical dictionary match
                if slug in CANONICAL_GENRES:
                    canonical_name = CANONICAL_GENRES[slug]
                    matched_slug = cls.slugify(canonical_name)
                # 2. Existing exact cluster slug match
                elif slug in clusters:
                    matched_slug = slug
                else:
                    # 3. Fuzzy proximity search across established clusters
                    for existing_slug in clusters.keys():
                        ratio = SequenceMatcher(None, slug, existing_slug).ratio()
                        # High confidence proximity match (e.g. electronica ~ electronic)
                        if ratio >= 0.88 or (len(slug) >= 6 and abs(len(slug) - len(existing_slug)) <= 1 and ratio >= 0.84):
                            matched_slug = existing_slug
                            break

                target_slug = matched_slug or slug
                if target_slug not in clusters:
                    canonical = CANONICAL_GENRES.get(target_slug) or cls.get_canonical_name(raw)
                    clusters[target_slug] = {
                        "canonical": canonical,
                        "tracks": [],
                        "variants": [],
                    }

                cluster = clusters[target_slug]
                cluster["variants"].append(raw)
                # Deduplicate track within this genre
                if not any(existing.id == track.id for existing in cluster["tracks"]):
                    cluster["tracks"].append(track)

        return {info["canonical"]: info["tracks"] for info in clusters.values()}
