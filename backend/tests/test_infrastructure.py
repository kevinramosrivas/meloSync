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
        assert settings.skip_non_music_sections is True
        assert settings.trim_silence is True
        settings.normalize_audio_lufs = -16.0
        settings.skip_non_music_sections = False
        settings.trim_silence = False
        uow.settings.update(settings)

    with uow:
        updated = uow.settings.get()
        assert updated.normalize_audio_lufs == -16.0
        assert updated.skip_non_music_sections is False
        assert updated.trim_silence is False


def test_ffmpeg_processor_codec_args():
    from src.domain.entities import AudioQuality
    from src.infrastructure.audio.ffmpeg_processor import FFmpegAudioProcessor

    best_args = FFmpegAudioProcessor._build_codec_args(AudioQuality.BEST)
    assert "-b:a" in best_args and "320k" in best_args

    mid_args = FFmpegAudioProcessor._build_codec_args(AudioQuality.MID_256K)
    assert "-b:a" in mid_args and "256k" in mid_args

    low_args = FFmpegAudioProcessor._build_codec_args(AudioQuality.LOW_128K)
    assert "-b:a" in low_args and "128k" in low_args


def test_ytdlp_downloader_opts():
    import shutil
    from src.infrastructure.downloader.ytdlp_downloader import YtDlpAudioDownloader

    opts = YtDlpAudioDownloader._build_ydl_opts()
    assert "remote_components" in opts
    if shutil.which("node") or shutil.which("deno"):
        assert "js_runtimes" in opts
        runtime_key = list(opts["js_runtimes"].keys())[0]
        assert "path" in opts["js_runtimes"][runtime_key]
