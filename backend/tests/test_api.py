"""Integration tests for FastAPI REST API endpoints."""

from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pytest

from src.api.dependencies import get_container
from src.api.main import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_and_update_settings(client):
    # GET settings
    get_res = client.get("/api/v1/settings")
    assert get_res.status_code == 200
    original_data = get_res.json()
    assert "music_download_directory" in original_data
    assert "default_audio_quality" in original_data

    try:
        # PUT settings
        put_res = client.put(
            "/api/v1/settings",
            json={
                "music_download_directory": original_data["music_download_directory"],
                "default_audio_quality": "320k",
                "normalize_audio_lufs": -15.0,
                "auto_tag_metadata": True,
            },
        )
        assert put_res.status_code == 200
        updated_data = put_res.json()
        assert updated_data["default_audio_quality"] == "320k"
        assert updated_data["normalize_audio_lufs"] == -15.0
    finally:
        # Restore original settings
        client.put("/api/v1/settings", json=original_data)


def test_get_library_empty_initially(client):
    response = client.get("/api/v1/library")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_download_cancel_and_delete_endpoints(client, monkeypatch):
    container = get_container()
    monkeypatch.setattr(container.task_executor, "submit_download", MagicMock())

    # 1. Enqueue a download
    req_body = {
        "youtube_id": "test_cancel_1",
        "url": "https://www.youtube.com/watch?v=test_cancel_1",
        "original_title": "Test Cancel Track",
        "duration_seconds": 180,
        "channel_name": "Test Artist",
        "quality": "best",
    }
    start_res = client.post("/api/v1/downloads", json=req_body)
    assert start_res.status_code == 200
    track_id = start_res.json()["track_id"]
    assert track_id is not None

    # 2. Cancel the download
    cancel_res = client.post(f"/api/v1/downloads/{track_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELADA"

    # Verify status in active downloads list
    list_res = client.get("/api/v1/downloads")
    assert list_res.status_code == 200
    active_tracks = list_res.json()
    cancelled_track = next((t for t in active_tracks if t["id"] == track_id), None)
    assert cancelled_track is not None
    assert cancelled_track["status"] == "CANCELADA"

    # 3. Delete the download
    del_res = client.delete(f"/api/v1/downloads/{track_id}")
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Descarga eliminada correctamente."

    # Verify track is no longer in active downloads
    list_res2 = client.get("/api/v1/downloads")
    active_tracks2 = list_res2.json()
    assert not any(t["id"] == track_id for t in active_tracks2)


def test_clear_failed_and_cancelled_downloads(client, monkeypatch):
    container = get_container()
    monkeypatch.setattr(container.task_executor, "submit_download", MagicMock())

    # Create two downloads and cancel them
    for yid in ["test_clear_1", "test_clear_2"]:
        body = {
            "youtube_id": yid,
            "url": f"https://www.youtube.com/watch?v={yid}",
            "original_title": f"Track {yid}",
            "duration_seconds": 120,
            "channel_name": "Artist",
            "quality": "best",
        }
        res = client.post("/api/v1/downloads", json=body)
        tid = res.json()["track_id"]
        client.post(f"/api/v1/downloads/{tid}/cancel")

    # Clear failed and cancelled
    clear_res = client.delete("/api/v1/downloads")
    assert clear_res.status_code == 200
    data = clear_res.json()
    assert data["deleted_count"] >= 2


