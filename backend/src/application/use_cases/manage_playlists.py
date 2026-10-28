"""Use Cases: Manage Playlists and Smart Suggestions."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
import logging
import re
from typing import Optional
import uuid

from ...domain.entities import DownloadStatus, Playlist, Track, utc_now
from ...domain.exceptions import PlaylistNotFoundException, TrackNotFoundException
from ...domain.repositories import IUnitOfWork
from ...infrastructure.metadata.itunes_provider import ITunesMetadataProvider

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
                # If artist mix has placeholder or empty description, retrieve and persist artist biography
                if not playlist.description or playlist.description.startswith("Todas tus canciones"):
                    artist_name = playlist.filter_query or (
                        playlist.name.replace("Mix de ", "").strip()
                        if playlist.name.startswith("Mix de ")
                        else playlist.name
                    )
                    bio = self._itunes.lookup_artist_bio(artist_name)
                    if bio:
                        playlist.description = bio
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
    """Synchronizes smart system playlists (Top Played, On Repeat, Artists, Genres)."""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        itunes_provider: Optional[ITunesMetadataProvider] = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._itunes = itunes_provider or ITunesMetadataProvider()

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

    def execute(self) -> None:
        logger.info("Starting smart playlists background synchronization...")
        with self._uow_factory() as uow:
            # 1. Ensure 'Top Played' and 'On Repeat' exist
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

            # 2. Group completed tracks by individual artists and genre
            completed_tracks = uow.tracks.list_by_status(DownloadStatus.COMPLETADA)
            artist_groups: dict[str, list[Track]] = defaultdict(list)
            genre_groups: dict[str, list[Track]] = defaultdict(list)

            for t in completed_tracks:
                artist_raw = (t.metadata.artist if t.metadata and t.metadata.artist else t.display_artist).strip()
                if artist_raw:
                    individual_artists = self._extract_individual_artists(artist_raw)
                    for art in individual_artists:
                        if not any(existing.id == t.id for existing in artist_groups[art]):
                            artist_groups[art].append(t)

                genre = t.metadata.genre.strip() if t.metadata and t.metadata.genre else None
                if genre and genre.lower() not in ("unknown", "other", ""):
                    genre_groups[genre].append(t)

            # 3. Synchronize Artist Mixes and cleanup obsolete composite artist playlists
            active_artists = set(artist_groups.keys())
            existing_artist_playlists = [p for p in uow.playlists.list_all() if p.playlist_type == PLAYLIST_TYPE_ARTIST]
            for old_p in existing_artist_playlists:
                if old_p.filter_query and old_p.filter_query not in active_artists:
                    uow.playlists.delete(old_p.id)

            for artist, tracks in artist_groups.items():
                existing = uow.playlists.get_by_filter(PLAYLIST_TYPE_ARTIST, artist)
                cover_url = self._itunes.lookup_artist_artwork(artist)

                if existing:
                    existing.tracks = tracks
                    existing.name = f"Mix de {artist}"
                    # Preserve existing rich biography if present; otherwise fetch or keep placeholder
                    if not existing.description or existing.description.startswith("Todas tus canciones"):
                        bio = self._itunes.lookup_artist_bio(artist)
                        if bio:
                            existing.description = bio
                        elif not existing.description:
                            existing.description = f"Todas tus canciones guardadas de {artist}"
                    existing.cover_url = cover_url or existing.cover_url
                    existing.updated_at = utc_now()
                    uow.playlists.update(existing)
                else:
                    bio = self._itunes.lookup_artist_bio(artist)
                    new_p = Playlist(
                        name=f"Mix de {artist}",
                        description=bio or f"Todas tus canciones guardadas de {artist}",
                        is_smart=True,
                        playlist_type=PLAYLIST_TYPE_ARTIST,
                        filter_query=artist,
                        cover_url=cover_url,
                        tracks=tracks,
                    )
                    uow.playlists.add(new_p)

            # 4. Synchronize Genre Mixes (for genres with at least 2 tracks)
            for genre, tracks in genre_groups.items():
                if len(tracks) < 2:
                    continue
                existing = uow.playlists.get_by_filter(PLAYLIST_TYPE_GENRE, genre)
                cover_url = None
                if existing and existing.cover_url:
                    cover_url = existing.cover_url
                else:
                    cover_url = self._itunes.lookup_genre_artwork(genre)

                if existing:
                    existing.tracks = tracks
                    existing.cover_url = cover_url or existing.cover_url
                    existing.updated_at = utc_now()
                    uow.playlists.update(existing)
                else:
                    new_p = Playlist(
                        name=f"Mix {genre}",
                        description=f"Lo mejor del género {genre} en tu biblioteca",
                        is_smart=True,
                        playlist_type=PLAYLIST_TYPE_GENRE,
                        filter_query=genre,
                        cover_url=cover_url,
                        tracks=tracks,
                    )
                    uow.playlists.add(new_p)

            uow.commit()
            logger.info("Smart playlists synchronization completed successfully.")
