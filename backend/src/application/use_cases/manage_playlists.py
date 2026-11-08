"""Use Cases: Manage Playlists and Smart Suggestions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
import concurrent.futures
import logging
import re
import threading
from typing import Any, Optional
import uuid

from ...domain.entities import DownloadStatus, Playlist, Track, utc_now
from ...domain.exceptions import PlaylistNotFoundException, TrackNotFoundException
from ...domain.repositories import IUnitOfWork
from ...infrastructure.metadata.itunes_provider import ITunesMetadataProvider
from ..services.genre_clustering import GenreClusterer

logger = logging.getLogger(__name__)

# System Constants for Playlist Types
PLAYLIST_TYPE_CUSTOM = "custom"
PLAYLIST_TYPE_TOP_PLAYED = "top_played"
PLAYLIST_TYPE_ON_REPEAT = "on_repeat"
PLAYLIST_TYPE_ARTIST = "artist"
PLAYLIST_TYPE_GENRE = "genre"

SMART_ID_TOP_PLAYED = "smart_top_played"
SMART_ID_ON_REPEAT = "smart_on_repeat"


class CreatePlaylistUseCase:
    """Creates a user-defined custom playlist."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, name: str, description: str = "") -> Playlist:
        clean_name = name.strip() if name else "Mi Lista"
        playlist = Playlist(
            name=clean_name,
            description=description.strip(),
            is_smart=False,
            playlist_type=PLAYLIST_TYPE_CUSTOM,
        )
        with self._uow_factory() as uow:
            created = uow.playlists.add(playlist)
            uow.commit()
            return created


class GetPlaylistsUseCase:
    """Retrieves all playlists."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self) -> list[Playlist]:
        with self._uow_factory() as uow:
            return uow.playlists.list_all()


class GetPlaylistsGroupedUseCase:
    """Retrieves all playlists structured into 4 tiered sections."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self) -> dict[str, list[Playlist]]:
        with self._uow_factory() as uow:
            all_playlists = uow.playlists.list_all()

            user_playlists: list[Playlist] = []
            for_you_playlists: list[Playlist] = []
            artist_playlists: list[Playlist] = []
            genre_playlists: list[Playlist] = []

            for p in all_playlists:
                if p.playlist_type == PLAYLIST_TYPE_CUSTOM:
                    user_playlists.append(p)
                elif p.playlist_type in (PLAYLIST_TYPE_TOP_PLAYED, PLAYLIST_TYPE_ON_REPEAT):
                    # For summary count, dynamically populate tracks count
                    if p.playlist_type == PLAYLIST_TYPE_TOP_PLAYED:
                        p.tracks = uow.tracks.get_top_played(limit=50)
                    elif p.playlist_type == PLAYLIST_TYPE_ON_REPEAT:
                        p.tracks = uow.tracks.get_on_repeat(days=30, min_repeats=2, limit=30)
                    for_you_playlists.append(p)
                elif p.playlist_type == PLAYLIST_TYPE_ARTIST:
                    artist_playlists.append(p)
                elif p.playlist_type == PLAYLIST_TYPE_GENRE:
                    genre_playlists.append(p)

            # Sort for_you so Top Played is first, then On Repeat
            for_you_playlists.sort(key=lambda p: 0 if p.playlist_type == PLAYLIST_TYPE_TOP_PLAYED else 1)

            return {
                "user_playlists": user_playlists,
                "for_you_playlists": for_you_playlists,
                "artist_playlists": artist_playlists,
                "genre_playlists": genre_playlists,
            }


class GetPlaylistByIdUseCase:
    """Retrieves playlist detail by ID, calculating dynamic tracks for algorithmic playlists."""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        itunes_provider: Optional[ITunesMetadataProvider] = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._itunes = itunes_provider or ITunesMetadataProvider()

    def execute(self, playlist_id: str) -> Playlist:
        with self._uow_factory() as uow:
            playlist = uow.playlists.get_by_id(playlist_id)
            if not playlist:
                raise PlaylistNotFoundException(playlist_id)

            # Algorithmic dynamic playlists resolve their tracks on read
            if playlist.playlist_type == PLAYLIST_TYPE_TOP_PLAYED:
                playlist.tracks = uow.tracks.get_top_played(limit=50)
            elif playlist.playlist_type == PLAYLIST_TYPE_ON_REPEAT:
                playlist.tracks = uow.tracks.get_on_repeat(days=30, min_repeats=2, limit=30)
            elif playlist.playlist_type == PLAYLIST_TYPE_ARTIST:
                # If artist mix has placeholder or empty description, check persistent cache without blocking HTTP
                if not playlist.description or playlist.description.startswith("Todas tus canciones"):
                    artist_name = playlist.filter_query or (
                        playlist.name.replace("Mix de ", "").strip()
                        if playlist.name.startswith("Mix de ")
                        else playlist.name
                    )
                    cached = uow.playlists.get_artist_cache(artist_name)
                    if cached and cached[1]:
                        playlist.description = cached[1]
                        uow.playlists.update(playlist)
                        uow.commit()

            return playlist


class UpdatePlaylistUseCase:
    """Updates name or description of a custom playlist."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, playlist_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Playlist:
        with self._uow_factory() as uow:
            playlist = uow.playlists.get_by_id(playlist_id)
            if not playlist:
                raise PlaylistNotFoundException(playlist_id)

            if playlist.is_smart:
                raise ValueError("No se pueden renombrar listas inteligentes automáticas.")

            if name is not None and name.strip():
                playlist.name = name.strip()
            if description is not None:
                playlist.description = description.strip()

            playlist.updated_at = utc_now()
            updated = uow.playlists.update(playlist)
            uow.commit()
            return updated


class DeletePlaylistUseCase:
    """Deletes a custom playlist."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, playlist_id: str) -> bool:
        with self._uow_factory() as uow:
            playlist = uow.playlists.get_by_id(playlist_id)
            if not playlist:
                raise PlaylistNotFoundException(playlist_id)

            if playlist.is_smart:
                raise ValueError("No se pueden eliminar las listas inteligentes automáticas del sistema.")

            deleted = uow.playlists.delete(playlist_id)
            uow.commit()
            return deleted


class AddTrackToPlaylistUseCase:
    """Adds a track to a custom playlist."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, playlist_id: str, track_id: str) -> Playlist:
        with self._uow_factory() as uow:
            playlist = uow.playlists.get_by_id(playlist_id)
            if not playlist:
                raise PlaylistNotFoundException(playlist_id)

            if playlist.is_smart:
                raise ValueError("No se pueden añadir canciones manualmente a una lista automática.")

            track = uow.tracks.get_by_id(track_id)
            if not track:
                raise TrackNotFoundException(track_id)

            playlist.add_track(track)
            updated = uow.playlists.update(playlist)
            uow.commit()
            return updated


class AddTracksBatchToPlaylistUseCase:
    """Adds multiple tracks to a custom playlist in a single atomic transaction."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, playlist_id: str, track_ids: list[str]) -> Playlist:
        with self._uow_factory() as uow:
            playlist = uow.playlists.get_by_id(playlist_id)
            if not playlist:
                raise PlaylistNotFoundException(playlist_id)

            if playlist.is_smart:
                raise ValueError("No se pueden añadir canciones manualmente a una lista automática.")

            for track_id in track_ids:
                track = uow.tracks.get_by_id(track_id)
                if track:
                    playlist.add_track(track)

            updated = uow.playlists.update(playlist)
            uow.commit()
            return updated


class RemoveTrackFromPlaylistUseCase:
    """Removes a track from a custom playlist."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, playlist_id: str, track_id: str) -> Playlist:
        with self._uow_factory() as uow:
            playlist = uow.playlists.get_by_id(playlist_id)
            if not playlist:
                raise PlaylistNotFoundException(playlist_id)

            if playlist.is_smart:
                raise ValueError("No se pueden quitar canciones manualmente de una lista automática.")

            playlist.remove_track(track_id)
            updated = uow.playlists.update(playlist)
            uow.commit()
            return updated


class RecordTrackPlayUseCase:
    """Records a playback event for a track."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, track_id: str) -> None:
        with self._uow_factory() as uow:
            uow.tracks.record_play(track_id)
            uow.commit()


class SyncSmartPlaylistsUseCase:
    """Synchronizes smart system playlists (Top Played, On Repeat, Artists, Genres) with sub-second local latency."""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        itunes_provider: Optional[ITunesMetadataProvider] = None,
        event_publisher: Optional[Any] = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._itunes = itunes_provider or ITunesMetadataProvider()
        self._event_publisher = event_publisher

    @staticmethod
    def _extract_individual_artists(raw_artist: str) -> list[str]:
        """Splits multi-artist collaborations into individual distinct artists."""
        cleaned = re.sub(r'\(.*?\)|\[.*?\]', '', raw_artist).strip()
        parts = re.split(r'\s+(?:&|feat\.?|ft\.?|vs\.?|x|with)\s+|,|\/', cleaned, flags=re.IGNORECASE)
        results: list[str] = []
        for p in parts:
            item = p.strip()
            if item and item.lower() not in ("desconocido", "unknown artist", "various artists", ""):
                results.append(item)
        return results if results else ([raw_artist.strip()] if raw_artist.strip() else [])

    def execute(self, background_enrich: bool = True) -> dict[str, Any]:
        """Executes instant local clustering and synchronization (<25ms) without blocking on external network calls.
        
        If `background_enrich` is True and there are artists or genres without cached portraits/bios,
        a non-blocking background daemon thread is dispatched to enrich them in parallel.
        """
        logger.info("Starting instant smart playlists synchronization...")

        pending_artists_for_enrichment: list[str] = []
        pending_genres_for_enrichment: list[str] = []

        with self._uow_factory() as uow:
            # -----------------------------------------------------------------
            # PHASE 1: Baseline Initialization & Completed Tracks Read (<5ms)
            # -----------------------------------------------------------------
            top_played = uow.playlists.get_by_id(SMART_ID_TOP_PLAYED)
            if not top_played:
                uow.playlists.add(
                    Playlist(
                        id=SMART_ID_TOP_PLAYED,
                        name="Más Escuchadas",
                        description="Tus canciones más reproducidas de todos los tiempos",
                        is_smart=True,
                        playlist_type=PLAYLIST_TYPE_TOP_PLAYED,
                    )
                )

            on_repeat = uow.playlists.get_by_id(SMART_ID_ON_REPEAT)
            if not on_repeat:
                uow.playlists.add(
                    Playlist(
                        id=SMART_ID_ON_REPEAT,
                        name="En Bucle",
                        description="Las canciones que no paras de escuchar en el último mes",
                        is_smart=True,
                        playlist_type=PLAYLIST_TYPE_ON_REPEAT,
                    )
                )

            completed_tracks = uow.tracks.list_by_status(DownloadStatus.COMPLETADA)
            existing_playlists = uow.playlists.list_all()

            # -----------------------------------------------------------------
            # PHASE 2: In-Memory Clustering (<5ms)
            # -----------------------------------------------------------------
            artist_groups: dict[str, list[Track]] = defaultdict(list)
            for t in completed_tracks:
                artist_raw = (t.metadata.artist if t.metadata and t.metadata.artist else t.display_artist).strip()
                if artist_raw:
                    individual_artists = self._extract_individual_artists(artist_raw)
                    for art in individual_artists:
                        if not any(existing.id == t.id for existing in artist_groups[art]):
                            artist_groups[art].append(t)

            genre_groups = GenreClusterer.cluster_tracks(completed_tracks)
            active_genre_groups = {genre: tracks for genre, tracks in genre_groups.items() if len(tracks) >= 2}
            active_canonical_genres = set(active_genre_groups.keys())
            active_slug_to_canonical = {GenreClusterer.slugify(g): g for g in active_canonical_genres}

            active_artists = set(artist_groups.keys())

            # -----------------------------------------------------------------
            # PHASE 3: Fast Atomic Persistence & Track Linking (<15ms)
            # -----------------------------------------------------------------
            # 1. Synchronize Artist Mixes and cleanup obsolete playlists
            current_artist_playlists = [p for p in existing_playlists if p.playlist_type == PLAYLIST_TYPE_ARTIST]
            artist_playlists_by_query: dict[str, list[Playlist]] = defaultdict(list)
            for p in current_artist_playlists:
                if p.filter_query and p.filter_query not in active_artists:
                    uow.playlists.delete(p.id)
                elif p.filter_query:
                    artist_playlists_by_query[p.filter_query].append(p)

            for artist, tracks in artist_groups.items():
                existing_list = artist_playlists_by_query.get(artist, [])
                existing = existing_list[0] if existing_list else None
                for dup in existing_list[1:]:
                    uow.playlists.delete(dup.id)

                cached = uow.playlists.get_artist_cache(artist)

                # Find first local track cover to serve as instant visual fallback
                local_cover = next((t.metadata.cover_url for t in tracks if t.metadata and t.metadata.cover_url), None)

                cached_portrait = cached[0] if cached else None
                cached_bio = cached[1] if cached else None

                # Cover precedence: Cached official portrait > Existing cover > Local track cover
                cover_url = cached_portrait or (existing.cover_url if existing else None) or local_cover

                # Bio precedence: Cached official bio > Existing custom bio > Default label
                if cached_bio:
                    bio = cached_bio
                elif existing and existing.description and not existing.description.startswith("Todas tus canciones"):
                    bio = existing.description
                else:
                    bio = f"Todas tus canciones guardadas de {artist}"

                # Mark for background enrichment if official metadata is missing
                if not cached_portrait or not cached_bio:
                    pending_artists_for_enrichment.append(artist)

                if existing:
                    existing.tracks = tracks
                    existing.name = f"Mix de {artist}"
                    existing.description = bio
                    existing.cover_url = cover_url or existing.cover_url
                    existing.updated_at = utc_now()
                    uow.playlists.update(existing)
                else:
                    new_p = Playlist(
                        name=f"Mix de {artist}",
                        description=bio,
                        is_smart=True,
                        playlist_type=PLAYLIST_TYPE_ARTIST,
                        filter_query=artist,
                        cover_url=cover_url,
                        tracks=tracks,
                    )
                    uow.playlists.add(new_p)

            # 2. Synchronize Genre Mixes and cleanup obsolete / duplicate playlists
            current_genre_playlists = [p for p in existing_playlists if p.playlist_type == PLAYLIST_TYPE_GENRE]
            playlists_by_slug: dict[str, list[Playlist]] = defaultdict(list)
            for p in current_genre_playlists:
                raw_ref = p.filter_query or p.name.replace("Mix ", "")
                slug = GenreClusterer.slugify(raw_ref)
                playlists_by_slug[slug].append(p)

            # Delete obsolete genre playlists
            for slug, plist_group in playlists_by_slug.items():
                if slug not in active_slug_to_canonical:
                    for old_p in plist_group:
                        uow.playlists.delete(old_p.id)

            # Update or create active canonical genre playlists, purging duplicates
            for slug, canonical_genre in active_slug_to_canonical.items():
                tracks = active_genre_groups[canonical_genre]
                matching_playlists = playlists_by_slug.get(slug, [])

                cached_artwork = uow.playlists.get_genre_cache(canonical_genre)
                local_cover = next((t.metadata.cover_url for t in tracks if t.metadata and t.metadata.cover_url), None)

                if not cached_artwork:
                    pending_genres_for_enrichment.append(canonical_genre)

                if matching_playlists:
                    primary_p = next(
                        (p for p in matching_playlists if p.filter_query == canonical_genre),
                        matching_playlists[0],
                    )

                    for dup_p in matching_playlists:
                        if dup_p.id != primary_p.id:
                            uow.playlists.delete(dup_p.id)

                    cover_url = cached_artwork or primary_p.cover_url or local_cover
                    primary_p.name = f"Mix {canonical_genre}"
                    primary_p.description = f"Lo mejor del género {canonical_genre} en tu biblioteca"
                    primary_p.filter_query = canonical_genre
                    primary_p.tracks = tracks
                    primary_p.cover_url = cover_url or primary_p.cover_url
                    primary_p.updated_at = utc_now()
                    uow.playlists.update(primary_p)
                else:
                    cover_url = cached_artwork or local_cover
                    new_p = Playlist(
                        name=f"Mix {canonical_genre}",
                        description=f"Lo mejor del género {canonical_genre} en tu biblioteca",
                        is_smart=True,
                        playlist_type=PLAYLIST_TYPE_GENRE,
                        filter_query=canonical_genre,
                        cover_url=cover_url,
                        tracks=tracks,
                    )
                    uow.playlists.add(new_p)

            uow.commit()

        logger.info(
            "Local smart playlists sync completed: %d artists, %d genres. Pending enrichment: %d artists, %d genres.",
            len(artist_groups),
            len(active_canonical_genres),
            len(pending_artists_for_enrichment),
            len(pending_genres_for_enrichment),
        )

        # ---------------------------------------------------------------------
        # PHASE 4: Non-blocking Background Enrichment
        # ---------------------------------------------------------------------
        if background_enrich and (pending_artists_for_enrichment or pending_genres_for_enrichment):
            threading.Thread(
                target=self._run_background_enrichment,
                args=(list(dict.fromkeys(pending_artists_for_enrichment)), list(dict.fromkeys(pending_genres_for_enrichment))),
                daemon=True,
                name="SmartPlaylistsEnrichmentWorker",
            ).start()

        return {
            "synced": True,
            "artist_count": len(artist_groups),
            "genre_count": len(active_canonical_genres),
            "pending_artists": len(pending_artists_for_enrichment),
            "pending_genres": len(pending_genres_for_enrichment),
        }

    def _run_background_enrichment(self, pending_artists: list[str], pending_genres: list[str]) -> None:
        """Asynchronously enriches artist portraits, biographies and genre artworks in the background."""
        logger.info(
            "Background enrichment worker started for %d artists and %d genres...",
            len(pending_artists),
            len(pending_genres),
        )
        updated_anything = False

        def _enrich_artist(artist_name: str) -> tuple[str, Optional[str], Optional[str]]:
            try:
                portrait = self._itunes.lookup_artist_artwork(artist_name)
                bio = self._itunes.lookup_artist_bio(artist_name)
                return (artist_name, portrait, bio)
            except Exception as e:
                logger.debug("Error enriching artist %s: %s", artist_name, e)
                return (artist_name, None, None)

        def _enrich_genre(genre_name: str) -> tuple[str, Optional[str]]:
            try:
                artwork = self._itunes.lookup_genre_artwork(genre_name)
                return (genre_name, artwork)
            except Exception as e:
                logger.debug("Error enriching genre %s: %s", genre_name, e)
                return (genre_name, None)

        # Limit to 4 concurrent worker threads to be gentle with external APIs and avoid rate limits
        enriched_artists: list[tuple[str, Optional[str], Optional[str]]] = []
        enriched_genres: list[tuple[str, Optional[str]]] = []

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        try:
            artist_futures = [pool.submit(_enrich_artist, a) for a in pending_artists]
            genre_futures = [pool.submit(_enrich_genre, g) for g in pending_genres]

            for f in concurrent.futures.as_completed(artist_futures):
                try:
                    enriched_artists.append(f.result())
                except Exception as e:
                    logger.debug("Artist future error: %s", e)

            for f in concurrent.futures.as_completed(genre_futures):
                try:
                    enriched_genres.append(f.result())
                except Exception as e:
                    logger.debug("Genre future error: %s", e)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        # Persist enriched cache and update playlists in SQLite
        with self._uow_factory() as uow:
            for artist_name, portrait, bio in enriched_artists:
                if portrait or bio:
                    uow.playlists.save_artist_cache(
                        artist_key=artist_name,
                        artist_name=artist_name,
                        portrait_url=portrait,
                        bio=bio,
                    )
                    playlist = uow.playlists.get_by_filter(PLAYLIST_TYPE_ARTIST, artist_name)
                    if playlist:
                        changed = False
                        if portrait and playlist.cover_url != portrait:
                            playlist.cover_url = portrait
                            changed = True
                        if bio and (not playlist.description or playlist.description.startswith("Todas tus canciones")):
                            playlist.description = bio
                            changed = True
                        if changed:
                            playlist.updated_at = utc_now()
                            uow.playlists.update(playlist)
                            updated_anything = True

            for genre_name, artwork in enriched_genres:
                if artwork:
                    uow.playlists.save_genre_cache(
                        genre_key=genre_name,
                        genre_name=genre_name,
                        artwork_url=artwork,
                    )
                    playlist = uow.playlists.get_by_filter(PLAYLIST_TYPE_GENRE, genre_name)
                    if playlist and playlist.cover_url != artwork:
                        playlist.cover_url = artwork
                        playlist.updated_at = utc_now()
                        uow.playlists.update(playlist)
                        updated_anything = True

            uow.commit()

        if updated_anything and self._event_publisher:
            try:
                self._event_publisher.publish_library_updated()
            except Exception as e:
                logger.debug("Could not publish library_updated after background enrichment: %s", e)

        logger.info("Background enrichment finished. Updated playlists: %s", updated_anything)
