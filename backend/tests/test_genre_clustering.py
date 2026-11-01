import pytest
from src.application.services.genre_clustering import GenreClusterer
from src.application.use_cases.manage_playlists import SyncSmartPlaylistsUseCase, PLAYLIST_TYPE_GENRE
from src.domain.entities import DownloadStatus, Playlist, Track, TrackMetadata
from src.infrastructure.persistence import DatabaseManager, SqlAlchemyUnitOfWork


class TestGenreClusterer:
    def test_extract_genres_single(self):
        assert GenreClusterer.extract_genres("K-Pop") == ["K-Pop"]
        assert GenreClusterer.extract_genres("Dance") == ["Dance"]

    def test_extract_genres_delimiters(self):
        assert GenreClusterer.extract_genres("K-Pop, Dance") == ["K-Pop", "Dance"]
        assert GenreClusterer.extract_genres("Hip-Hop / Rap") == ["Hip-Hop", "Rap"]
        assert GenreClusterer.extract_genres("Pop; Electronic | Synthwave") == ["Pop", "Electronic", "Synthwave"]
        assert GenreClusterer.extract_genres("Pop & Rock") == ["Pop", "Rock"]

    def test_extract_genres_acronyms_preserved(self):
        assert GenreClusterer.extract_genres("R&B") == ["R&B"]
        assert GenreClusterer.extract_genres("R & B") == ["R&B"]
        assert GenreClusterer.extract_genres("RnB") == ["R&B"]

    def test_extract_genres_cleans_noise(self):
        assert GenreClusterer.extract_genres("") == []
        assert GenreClusterer.extract_genres(None) == []
        assert GenreClusterer.extract_genres("Unknown") == []
        assert GenreClusterer.extract_genres("Other, none, Pop") == ["Pop"]

    def test_slugify_unification(self):
        # K-Pop variants
        assert GenreClusterer.slugify("K-Pop") == "kpop"
        assert GenreClusterer.slugify("K-pop") == "kpop"
        assert GenreClusterer.slugify("k-pop") == "kpop"
        assert GenreClusterer.slugify("KPop") == "kpop"
        assert GenreClusterer.slugify("K Pop") == "kpop"

        # Hip-Hop variants
        assert GenreClusterer.slugify("Hip-Hop") == "hiphop"
        assert GenreClusterer.slugify("Hip Hop") == "hiphop"
        assert GenreClusterer.slugify("hip-hop") == "hiphop"

        # Plural normalization
        assert GenreClusterer.slugify("Soundtracks") == "soundtrack"
        assert GenreClusterer.slugify("Soundtrack") == "soundtrack"

    def test_get_canonical_name(self):
        assert GenreClusterer.get_canonical_name("k-pop") == "K-Pop"
        assert GenreClusterer.get_canonical_name("K-pop") == "K-Pop"
        assert GenreClusterer.get_canonical_name("kpop") == "K-Pop"
        assert GenreClusterer.get_canonical_name("rnb") == "R&B"
        assert GenreClusterer.get_canonical_name("soundtracks") == "Soundtrack"
        assert GenreClusterer.get_canonical_name("ost") == "Soundtrack"
        assert GenreClusterer.get_canonical_name("post-punk") == "Post-Punk"

    def test_cluster_tracks_merges_kpop_variants(self):
        t1 = Track(
            id="t1",
            youtube_id="y1",
            url="u1",
            original_title="Song 1",
            status=DownloadStatus.COMPLETADA,
            metadata=TrackMetadata(title="Song 1", artist="BIBI", genre="K-Pop"),
        )
        t2 = Track(
            id="t2",
            youtube_id="y2",
            url="u2",
            original_title="Song 2",
            status=DownloadStatus.COMPLETADA,
            metadata=TrackMetadata(title="Song 2", artist="BIBI", genre="K-pop"),
        )
        t3 = Track(
            id="t3",
            youtube_id="y3",
            url="u3",
            original_title="Song 3",
            status=DownloadStatus.COMPLETADA,
            metadata=TrackMetadata(title="Song 3", artist="IU", genre="k-pop"),
        )
        t4 = Track(
            id="t4",
            youtube_id="y4",
            url="u4",
            original_title="Song 4",
            status=DownloadStatus.COMPLETADA,
            metadata=TrackMetadata(title="Song 4", artist="Dua Lipa", genre="Pop, Dance"),
        )

        clusters = GenreClusterer.cluster_tracks([t1, t2, t3, t4])

        assert "K-Pop" in clusters
        assert len(clusters["K-Pop"]) == 3
        assert {t.id for t in clusters["K-Pop"]} == {"t1", "t2", "t3"}

        assert "Pop" in clusters
        assert any(t.id == "t4" for t in clusters["Pop"])

        assert "Dance" in clusters
        assert any(t.id == "t4" for t in clusters["Dance"])


def test_sync_smart_playlists_deduplicates_and_cleans_genre_playlists():
    db = DatabaseManager(":memory:")
    db.init_database()
    uow_factory = lambda: SqlAlchemyUnitOfWork(db)

    with uow_factory() as uow:
        # Seed 4 tracks: 2 K-Pop with different casing, 1 with both K-Pop and Dance, 1 Dance
        t1 = Track(
            id="t-1",
            youtube_id="yt-1",
            url="url-1",
            original_title="Track 1",
            status=DownloadStatus.COMPLETADA,
            metadata=TrackMetadata(title="Title 1", artist="Artist 1", genre="K-Pop"),
        )
        t2 = Track(
            id="t-2",
            youtube_id="yt-2",
            url="url-2",
            original_title="Track 2",
            status=DownloadStatus.COMPLETADA,
            metadata=TrackMetadata(title="Title 2", artist="Artist 2", genre="K-pop"),
        )
        t3 = Track(
            id="t-3",
            youtube_id="yt-3",
            url="url-3",
            original_title="Track 3",
            status=DownloadStatus.COMPLETADA,
            metadata=TrackMetadata(title="Title 3", artist="Artist 3", genre="k-pop, Dance"),
        )
        t4 = Track(
            id="t-4",
            youtube_id="yt-4",
            url="url-4",
            original_title="Track 4",
            status=DownloadStatus.COMPLETADA,
            metadata=TrackMetadata(title="Title 4", artist="Artist 4", genre="Dance"),
        )
        uow.tracks.add(t1)
        uow.tracks.add(t2)
        uow.tracks.add(t3)
        uow.tracks.add(t4)

        # Pre-seed duplicate playlists (simulating the bug where Mix K-Pop and Mix K-pop both existed)
        p_kpop_1 = Playlist(
            id="p-kpop-1",
            name="Mix K-Pop",
            description="Old K-Pop",
            is_smart=True,
            playlist_type=PLAYLIST_TYPE_GENRE,
            filter_query="K-Pop",
            tracks=[t1],
        )
        p_kpop_2 = Playlist(
            id="p-kpop-2",
            name="Mix K-pop",
            description="Old K-pop lowercase",
            is_smart=True,
            playlist_type=PLAYLIST_TYPE_GENRE,
            filter_query="K-pop",
            tracks=[t2],
        )
        p_obsolete = Playlist(
            id="p-obsolete",
            name="Mix Obsolete",
            description="Has 0 tracks now",
            is_smart=True,
            playlist_type=PLAYLIST_TYPE_GENRE,
            filter_query="Obsolete",
            tracks=[],
        )
        uow.playlists.add(p_kpop_1)
        uow.playlists.add(p_kpop_2)
        uow.playlists.add(p_obsolete)
        uow.commit()

    # Execute synchronization
    class DummyItunes:
        def lookup_artist_artwork(self, a): return None
        def lookup_artist_bio(self, a): return None
        def lookup_genre_artwork(self, g): return None

    sync_case = SyncSmartPlaylistsUseCase(uow_factory=uow_factory, itunes_provider=DummyItunes())
    sync_case.execute()

    with uow_factory() as uow:
        genre_playlists = [p for p in uow.playlists.list_all() if p.playlist_type == PLAYLIST_TYPE_GENRE]

        # 1. Obsolete playlist must be purged
        assert not any(p.id == "p-obsolete" for p in genre_playlists)

        # 2. Duplicate 'Mix K-pop' must be purged
        kpop_playlists = [p for p in genre_playlists if "kpop" in GenreClusterer.slugify(p.filter_query)]
        assert len(kpop_playlists) == 1, f"Expected 1 K-Pop playlist, found {len(kpop_playlists)}"

        kpop_p = kpop_playlists[0]
        assert kpop_p.name == "Mix K-Pop"
        assert kpop_p.filter_query == "K-Pop"
        # Must contain all 3 tracks (t-1, t-2, and t-3 which had 'k-pop, Dance')
        assert len(kpop_p.tracks) == 3
        assert {t.id for t in kpop_p.tracks} == {"t-1", "t-2", "t-3"}

        # 3. Dance playlist must exist and contain 2 tracks (t-3 and t-4)
        dance_playlists = [p for p in genre_playlists if "dance" in GenreClusterer.slugify(p.filter_query)]
        assert len(dance_playlists) == 1
        assert len(dance_playlists[0].tracks) == 2
        assert {t.id for t in dance_playlists[0].tracks} == {"t-3", "t-4"}

