"""Integration tests for FastAPI REST API endpoints."""

from fastapi.testclient import TestClient
import pytest

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
