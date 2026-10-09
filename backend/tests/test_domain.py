"""Unit tests for domain entities and state machine."""

import pytest
from src.domain.entities import (
    AppSettings,
    AudioQuality,
    DownloadStatus,
    Playlist,
    SearchResult,
    Track,
    TrackMetadata,
)
from src.domain.exceptions import InvalidStateTransitionException


def test_track_initial_state():
    track = Track(
        youtube_id="abc12345",
        url="https://youtube.com/watch?v=abc12345",
        original_title="Test Artist - Test Song",
    )
    assert track.status == DownloadStatus.PENDIENTE
    assert track.progress_percent == 0.0
    assert track.display_title == "Test Artist - Test Song"


def test_track_valid_state_machine_transitions():
    track = Track(
        youtube_id="abc12345",
        url="https://youtube.com/watch?v=abc12345",
        original_title="Test Artist - Test Song",
    )
    track.mark_downloading()
    assert track.status == DownloadStatus.DESCARGANDO

    track.mark_processing_audio()
    assert track.status == DownloadStatus.PROCESANDO_AUDIO

    track.mark_fetching_metadata()
    assert track.status == DownloadStatus.OBTENIENDO_METADATOS

    track.mark_completed(final_file_path="C:/music/test.mp3")
    assert track.status == DownloadStatus.COMPLETADA
    assert track.progress_percent == 100.0


def test_track_invalid_state_machine_transition():
    track = Track(
        youtube_id="abc12345",
        url="https://youtube.com/watch?v=abc12345",
        original_title="Test Artist - Test Song",
    )
    # Cannot jump directly from PENDIENTE to COMPLETADA
    with pytest.raises(InvalidStateTransitionException):
        track.mark_completed("C:/music/test.mp3")


def test_playlist_add_remove():
    playlist = Playlist(name="Rock Hits")
    track = Track(
        youtube_id="abc12345",
        url="https://youtube.com/watch?v=abc12345",
        original_title="Queen - Bohemian Rhapsody",
    )
    playlist.add_track(track)
    assert len(playlist.tracks) == 1
    # Adding same track again is ignored
    playlist.add_track(track)
    assert len(playlist.tracks) == 1

    playlist.remove_track(track.id)
    assert len(playlist.tracks) == 0


def test_app_settings_entity():
    settings = AppSettings()
    assert settings.music_download_directory != ""
    assert settings.default_audio_quality == AudioQuality.BEST
    assert settings.normalize_audio_lufs == -14.0
