"""Unit tests for infrastructure persistence and title cleaner."""

import pytest
from src.domain.entities import AppSettings, DownloadStatus, Track, TrackMetadata
from src.infrastructure.metadata.regex_cleaner import RegexTitleCleaner
from src.infrastructure.persistence.database import DatabaseManager
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def test_regex_title_cleaner():
    cleaner = RegexTitleCleaner()

    artist, title = cleaner.clean("Daft Punk - One More Time [Official Video]")
    assert artist == "Daft Punk"
    assert title == "One More Time"

    artist2, title2 = cleaner.clean("Coldplay - Yellow (Official 4K Video)")
    assert artist2 == "Coldplay"
    assert title2 == "Yellow"

    artist3, title3 = cleaner.clean("Alone Song")
    assert artist3 == ""
    assert title3 == "Alone Song"


def test_sqlite_unit_of_work_persistence():
    db = DatabaseManager(db_path=":memory:")
    db.init_database()

    uow = SqlAlchemyUnitOfWork(db)
    with uow:
        track = Track(
            youtube_id="yt_test_1",
            url="https://youtube.com/watch?v=yt_test_1",
            original_title="Artist - Song",
        )
        uow.tracks.add(track)

    with uow:
        retrieved = uow.tracks.get_by_youtube_id("yt_test_1")
        assert retrieved is not None
        assert retrieved.original_title == "Artist - Song"

        # Update
        retrieved.mark_downloading()
        uow.tracks.update(retrieved)

    with uow:
        updated = uow.tracks.get_by_youtube_id("yt_test_1")
        assert updated is not None
        assert updated.status == DownloadStatus.DESCARGANDO


def test_sqlite_settings_persistence():
    db = DatabaseManager(db_path=":memory:")
    db.init_database()

    uow = SqlAlchemyUnitOfWork(db)
    with uow:
        settings = uow.settings.get()
        assert settings is not None
        settings.normalize_audio_lufs = -16.0
        uow.settings.update(settings)

    with uow:
        updated = uow.settings.get()
        assert updated.normalize_audio_lufs == -16.0
