"""Unit tests for Library and Playlists batch operations."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.dependencies import get_container
from src.domain.entities import Playlist, Track, DownloadStatus


@pytest.fixture
def app_client(tmp_path):
    music_dir = tmp_path / "music"
    music_dir.mkdir()

    container = get_container()
    app = create_app()
    client = TestClient(app)

    return client, container, music_dir


def test_batch_delete_tracks(app_client):
    client, container, music_dir = app_client

    # Create dummy tracks and dummy audio files
    file1 = music_dir / "song1.mp3"
    file1.write_text("dummy audio 1")
    file2 = music_dir / "song2.mp3"
    file2.write_text("dummy audio 2")

    with container.uow_factory() as uow:
        t1 = Track(
            youtube_id="yt_batch_1",
            url="https://youtube.com/watch?v=yt_batch_1",
            original_title="Batch Song 1",
            status=DownloadStatus.COMPLETADA,
            file_path=str(file1),
        )
        t2 = Track(
            youtube_id="yt_batch_2",
            url="https://youtube.com/watch?v=yt_batch_2",
            original_title="Batch Song 2",
            status=DownloadStatus.COMPLETADA,
            file_path=str(file2),
        )
        t3 = Track(
            youtube_id="yt_batch_3",
            url="https://youtube.com/watch?v=yt_batch_3",
            original_title="Batch Song 3 (Keep)",
            status=DownloadStatus.COMPLETADA,
        )
        uow.tracks.add(t1)
        uow.tracks.add(t2)
        uow.tracks.add(t3)
        uow.commit()

        t1_id = t1.id
        t2_id = t2.id
        t3_id = t3.id

    # Call batch delete endpoint
    response = client.post(
        "/api/v1/library/batch-delete",
        json={"track_ids": [t1_id, t2_id, "non_existent_id"], "delete_files": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["deleted_count"] == 2
    assert "non_existent_id" in data["failed_ids"]
    assert not file1.exists()
    assert not file2.exists()

    # Verify database state
    with container.uow_factory() as uow:
        assert uow.tracks.get_by_id(t1_id) is None
        assert uow.tracks.get_by_id(t2_id) is None
        assert uow.tracks.get_by_id(t3_id) is not None

        # Clean up t3
        uow.tracks.delete(t3_id)
        uow.commit()


def test_batch_add_tracks_to_playlist(app_client):
    client, container, _ = app_client

    with container.uow_factory() as uow:
        t1 = Track(youtube_id="p_t1", url="https://youtube.com/watch?v=p_t1", original_title="P Track 1")
        t2 = Track(youtube_id="p_t2", url="https://youtube.com/watch?v=p_t2", original_title="P Track 2")
        uow.tracks.add(t1)
        uow.tracks.add(t2)

        p = Playlist(name="Rock Classics", is_smart=False, playlist_type="custom")
        uow.playlists.add(p)
        uow.commit()

        p_id = p.id
        t1_id = t1.id
        t2_id = t2.id

    # Add tracks in bulk
    response = client.post(
        f"/api/v1/playlists/{p_id}/batch-tracks",
        json={"track_ids": [t1_id, t2_id]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == p_id
    assert len(data["tracks"]) == 2
    track_ids = [t["id"] for t in data["tracks"]]
    assert t1_id in track_ids
    assert t2_id in track_ids

    # Clean up
    with container.uow_factory() as uow:
        uow.playlists.delete(p_id)
        uow.tracks.delete(t1_id)
        uow.tracks.delete(t2_id)
        uow.commit()
