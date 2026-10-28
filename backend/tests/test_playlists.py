"""Unit tests for Playlists, Play Tracking, and Smart Mixes."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.dependencies import Container, get_container
from src.domain.entities import DownloadStatus, Playlist, Track, TrackMetadata
from src.infrastructure.persistence import DatabaseManager, SqlAlchemyUnitOfWork
from src.application.use_cases.manage_playlists import (
    PLAYLIST_TYPE_CUSTOM,
    PLAYLIST_TYPE_TOP_PLAYED,
    PLAYLIST_TYPE_ON_REPEAT,
    SMART_ID_TOP_PLAYED,
    SMART_ID_ON_REPEAT,
    SyncSmartPlaylistsUseCase,
)


@pytest.fixture
def memory_db():
    db = DatabaseManager(":memory:")
    db.init_database()
    return db


@pytest.fixture
def uow_factory(memory_db):
    return lambda: SqlAlchemyUnitOfWork(memory_db)


def test_custom_playlist_lifecycle(uow_factory):
    with uow_factory() as uow:
        # Create
        playlist = Playlist(name="Rock Classics", description="My favorite 70s and 80s rock")
        created = uow.playlists.add(playlist)
        assert created.id is not None
        assert created.name == "Rock Classics"
        assert created.playlist_type == PLAYLIST_TYPE_CUSTOM

        # Add Track
        track = Track(
            youtube_id="yt-123",
            url="https://youtube.com/watch?v=123",
            original_title="Bohemian Rhapsody",
            status=DownloadStatus.COMPLETADA,
            metadata=TrackMetadata(title="Bohemian Rhapsody", artist="Queen", album="A Night at the Opera", genre="Rock"),
        )
        saved_track = uow.tracks.add(track)

        created.add_track(saved_track)
        updated = uow.playlists.update(created)
        assert len(updated.tracks) == 1
        assert updated.tracks[0].display_title == "Bohemian Rhapsody"

        # Remove Track
        updated.remove_track(saved_track.id)
        updated2 = uow.playlists.update(updated)
        assert len(updated2.tracks) == 0

        # Delete
        deleted = uow.playlists.delete(created.id)
        assert deleted is True
        assert uow.playlists.get_by_id(created.id) is None


def test_play_tracking_and_metrics(uow_factory):
    with uow_factory() as uow:
        track1 = Track(
            youtube_id="yt-a",
            url="https://youtube.com/watch?v=a",
            original_title="Track A",
            status=DownloadStatus.COMPLETADA,
            metadata=TrackMetadata(title="Track A", artist="Artist Alpha"),
        )
        track2 = Track(
            youtube_id="yt-b",
            url="https://youtube.com/watch?v=b",
            original_title="Track B",
            status=DownloadStatus.COMPLETADA,
            metadata=TrackMetadata(title="Track B", artist="Artist Beta"),
        )
        t1 = uow.tracks.add(track1)
        t2 = uow.tracks.add(track2)

        # Initially zero plays
        assert t1.play_count == 0
        assert uow.tracks.get_top_played() == []
        assert uow.tracks.get_on_repeat() == []

        # Record plays: t1 played 3 times, t2 played 1 time
        uow.tracks.record_play(t1.id)
        uow.tracks.record_play(t1.id)
        uow.tracks.record_play(t1.id)
        uow.tracks.record_play(t2.id)

        top_played = uow.tracks.get_top_played()
        assert len(top_played) == 2
        assert top_played[0].id == t1.id
        assert top_played[0].play_count == 3
        assert top_played[1].id == t2.id
        assert top_played[1].play_count == 1

        # On Repeat query requires at least 2 repeats in recent window
        on_repeat = uow.tracks.get_on_repeat(days=30, min_repeats=2)
        assert len(on_repeat) == 1
        assert on_repeat[0].id == t1.id


def test_smart_playlists_sync(uow_factory):
    with uow_factory() as uow:
        # Seed 3 tracks: Queen (2 tracks in Rock), Daft Punk (1 track in Electronic)
        uow.tracks.add(
            Track(
                youtube_id="yt-q1",
                url="https://youtube.com/watch?v=q1",
                original_title="Song 1",
                status=DownloadStatus.COMPLETADA,
                metadata=TrackMetadata(title="Radio Ga Ga", artist="Queen", genre="Rock"),
            )
        )
        uow.tracks.add(
            Track(
                youtube_id="yt-q2",
                url="https://youtube.com/watch?v=q2",
                original_title="Song 2",
                status=DownloadStatus.COMPLETADA,
                metadata=TrackMetadata(title="Under Pressure", artist="Queen", genre="Rock"),
            )
        )
        uow.tracks.add(
            Track(
                youtube_id="yt-dp",
                url="https://youtube.com/watch?v=dp",
                original_title="Song 3",
                status=DownloadStatus.COMPLETADA,
                metadata=TrackMetadata(title="One More Time", artist="Daft Punk", genre="Electronic"),
            )
        )
        uow.commit()

    sync_case = SyncSmartPlaylistsUseCase(uow_factory=uow_factory)
    sync_case.execute()

    with uow_factory() as uow:
        # Check Top Played & On Repeat existence
        top = uow.playlists.get_by_id(SMART_ID_TOP_PLAYED)
        assert top is not None
        assert top.name == "Más Escuchadas"
        assert top.is_smart is True

        rep = uow.playlists.get_by_id(SMART_ID_ON_REPEAT)
        assert rep is not None
        assert rep.name == "En Bucle"
        assert rep.is_smart is True

        # Check Artist playlists
        queen_p = uow.playlists.get_by_filter("artist", "Queen")
        assert queen_p is not None
        assert queen_p.name == "Mix de Queen"
        assert len(queen_p.tracks) == 2

        dp_p = uow.playlists.get_by_filter("artist", "Daft Punk")
        assert dp_p is not None
        assert dp_p.name == "Mix de Daft Punk"
        assert len(dp_p.tracks) == 1

        # Check Genre playlists (Rock has 2 tracks so it is generated)
        rock_p = uow.playlists.get_by_filter("genre", "Rock")
        assert rock_p is not None
        assert len(rock_p.tracks) == 2


def test_api_playlists_endpoints():
    client = TestClient(app)

    # 1. Get Grouped Playlists
    resp = client.get("/api/v1/playlists")
    assert resp.status_code == 200
    data = resp.json()
    assert "user_playlists" in data
    assert "for_you_playlists" in data
    assert "artist_playlists" in data
    assert "genre_playlists" in data

    # 2. Create User Playlist
    create_resp = client.post("/api/v1/playlists", json={"name": "Fiesta 2026", "description": "Hits para bailar"})
    assert create_resp.status_code == 200
    p_data = create_resp.json()
    assert p_data["name"] == "Fiesta 2026"
    assert p_data["playlist_type"] == "custom"
    playlist_id = p_data["id"]

    # 3. Update Playlist
    update_resp = client.put(f"/api/v1/playlists/{playlist_id}", json={"name": "Fiesta 2026 - Renovada"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Fiesta 2026 - Renovada"

    # 4. Delete Playlist
    del_resp = client.delete(f"/api/v1/playlists/{playlist_id}")
    assert del_resp.status_code == 200

    # 5. Verify 404
    assert client.get(f"/api/v1/playlists/{playlist_id}").status_code == 404
