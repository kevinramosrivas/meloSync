"""Unit tests for application use cases."""

from unittest.mock import MagicMock
import pytest

from src.application.dto import DownloadTrackCommand, UpdateSettingsCommand
from src.application.use_cases import (
    DeleteTrackUseCase,
    DownloadAndProcessTrackUseCase,
    GetLibraryTracksUseCase,
    GetSettingsUseCase,
    SearchYouTubeUseCase,
    UpdateSettingsUseCase,
)
from src.domain.entities import AppSettings, DownloadStatus, SearchResult, Track
from src.infrastructure.persistence.database import DatabaseManager
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def test_search_use_case():
    search_service_mock = MagicMock()
    search_service_mock.search.return_value = [
        SearchResult(
            youtube_id="vid123",
            title="Cool Song",
            duration_seconds=180,
            channel_name="Cool Artist",
            thumbnail_url="http://thumb.jpg",
            url="http://youtube.com/watch?v=vid123",
        )
    ]

    uc = SearchYouTubeUseCase(search_service=search_service_mock)
    results = uc.execute("Cool Song")
    assert len(results) == 1
    assert results[0].youtube_id == "vid123"
    assert results[0].duration_formatted == "3:00"


def test_settings_use_cases():
    db = DatabaseManager(db_path=":memory:")
    db.init_database()

    def uow_factory():
        return SqlAlchemyUnitOfWork(db)

    get_uc = GetSettingsUseCase(uow_factory=uow_factory)
    update_uc = UpdateSettingsUseCase(uow_factory=uow_factory)

    initial = get_uc.execute()
    assert initial.normalize_audio_lufs == -14.0

    update_cmd = UpdateSettingsCommand(
        music_download_directory="C:/CustomMusic",
        normalize_audio_lufs=-12.0,
    )
    updated = update_uc.execute(update_cmd)
    assert updated.normalize_audio_lufs == -12.0
    assert "CustomMusic" in updated.music_download_directory


def test_library_use_cases():
    db = DatabaseManager(db_path=":memory:")
    db.init_database()

    def uow_factory():
        return SqlAlchemyUnitOfWork(db)

    with uow_factory() as uow:
        track = Track(
            youtube_id="test_yt_id",
            url="https://youtube.com/watch?v=test_yt_id",
            original_title="Sample Title",
            status=DownloadStatus.COMPLETADA,
        )
        uow.tracks.add(track)

    get_lib_uc = GetLibraryTracksUseCase(uow_factory=uow_factory)
    tracks = get_lib_uc.execute()
    assert len(tracks) == 1
    assert tracks[0].original_title == "Sample Title"

    delete_uc = DeleteTrackUseCase(uow_factory=uow_factory)
    success = delete_uc.execute(track.id, delete_file=False)
    assert success is True
    assert len(get_lib_uc.execute()) == 0
