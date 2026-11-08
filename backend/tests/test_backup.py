"""Unit and Integration tests for Backup Export and Import functionality."""

import pytest
from unittest.mock import MagicMock

from src.application.dto import (
    ImportBackupOptionsDTO,
)
from src.application.use_cases.export_data import (
    BACKUP_FORMAT_IDENTIFIER,
    BACKUP_SCHEMA_VERSION,
    ExportBackupUseCase,
)
from src.application.use_cases.import_data import ImportBackupUseCase
from src.domain.entities import (
    AppSettings,
    AudioQuality,
    DownloadStatus,
    Playlist,
    Track,
    TrackMetadata,
)
from src.infrastructure.persistence.database import DatabaseManager
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
def in_memory_uow_factory():
    """Provides an isolated SQLite in-memory Unit of Work factory for tests."""
    db_manager = DatabaseManager(db_path=":memory:")
    db_manager.init_database()

    def _factory():
        return SqlAlchemyUnitOfWork(db_manager)

    return _factory


def test_export_backup_bundle(in_memory_uow_factory):
    """Verifies that ExportBackupUseCase correctly packages settings, tracks and custom playlists."""
    with in_memory_uow_factory() as uow:
        # Seed settings
        settings = AppSettings(
            music_download_directory="C:/TestMusic",
            default_audio_quality=AudioQuality.HIGH_320K,
            normalize_audio_lufs=-16.0,
            auto_tag_metadata=True,
        )
        uow.settings.update(settings)

        # Seed tracks
        meta = TrackMetadata(
            title="Bohemian Rhapsody",
            artist="Queen",
            album="A Night at the Opera",
            year=1975,
            genre="Rock",
            track_number=4,
            disc_number=1,
            cover_url="https://example.com/queen.jpg",
        )
        track = Track(
            youtube_id="fJ9rUzIMcZQ",
            url="https://youtube.com/watch?v=fJ9rUzIMcZQ",
            original_title="Queen - Bohemian Rhapsody (Official Video)",
            duration_seconds=359,
            channel_name="Queen Official",
            status=DownloadStatus.COMPLETADA,
            metadata=meta,
            play_count=42,
        )
        saved_track = uow.tracks.add(track)

        # Seed custom playlist
        playlist = Playlist(
            name="Classic Rock Hits",
            description="Legendary rock tunes",
            playlist_type="custom",
        )
        playlist.add_track(saved_track)
        uow.playlists.add(playlist)

        # Seed smart playlist (should NOT be exported as custom)
        smart_p = Playlist(
            name="Top Played",
            playlist_type="top_played",
            is_smart=True,
        )
        uow.playlists.add(smart_p)
        uow.commit()

    export_uc = ExportBackupUseCase(uow_factory=in_memory_uow_factory)
    exported = export_uc.execute(
        user_preferences={"libraryViewMode": "grid", "repeatMode": "all"},
        app_version="2.1.0",
    )

    assert exported.format == BACKUP_FORMAT_IDENTIFIER
    assert exported.version == BACKUP_SCHEMA_VERSION
    assert exported.app_version == "2.1.0"

    # Settings
    assert exported.settings.default_audio_quality == "320k"
    assert exported.settings.normalize_audio_lufs == -16.0
    assert exported.settings.auto_tag_metadata is True
    assert exported.settings.user_preferences == {"libraryViewMode": "grid", "repeatMode": "all"}

    # Tracks
    assert len(exported.tracks) == 1
    t = exported.tracks[0]
    assert t.youtube_id == "fJ9rUzIMcZQ"
    assert t.metadata is not None
    assert t.metadata.title == "Bohemian Rhapsody"
    assert t.metadata.artist == "Queen"
    assert t.play_count == 42

    # Playlists (only custom)
    assert len(exported.playlists) == 1
    p = exported.playlists[0]
    assert p.name == "Classic Rock Hits"
    assert p.track_youtube_ids == ["fJ9rUzIMcZQ"]


def test_import_backup_validation_failure(in_memory_uow_factory):
    """Rejects malformed backup bundles or unsupported schema versions."""
    import_uc = ImportBackupUseCase(uow_factory=in_memory_uow_factory)

    with pytest.raises(ValueError, match="Formato de archivo de respaldo no válido"):
        import_uc.execute({"format": "unknown-format", "version": 1})

    with pytest.raises(ValueError, match="Versión de respaldo '999' no soportada"):
        import_uc.execute({"format": BACKUP_FORMAT_IDENTIFIER, "version": 999})


def test_import_backup_restores_data_and_enqueues_downloads(in_memory_uow_factory):
    """Verifies that ImportBackupUseCase restores settings, creates tracks, links playlists, and queues downloads."""
    sample_backup = {
        "format": "melosync-backup",
        "version": 1,
        "exported_at_iso": "2026-11-07T12:00:00Z",
        "app_version": "2.1.0",
        "settings": {
            "default_audio_quality": "256k",
            "normalize_audio_lufs": -14.5,
            "auto_tag_metadata": True,
            "user_preferences": {
                "libraryViewMode": "grid",
                "shuffleEnabled": True,
            },
        },
        "tracks": [
            {
                "youtube_id": "yt_track_1",
                "url": "https://youtube.com/watch?v=yt_track_1",
                "original_title": "Track One",
                "duration_seconds": 180,
                "channel_name": "Channel One",
                "metadata": {
                    "title": "Title One",
                    "artist": "Artist One",
                    "album": "Album One",
                    "year": 2024,
                    "genre": "Electronic",
                    "cover_url": "https://example.com/cover1.jpg",
                },
                "play_count": 5,
            },
            {
                "youtube_id": "yt_track_2",
                "url": "https://youtube.com/watch?v=yt_track_2",
                "original_title": "Track Two",
                "duration_seconds": 240,
                "channel_name": "Channel Two",
                "metadata": {
                    "title": "Title Two",
                    "artist": "Artist Two",
                },
                "play_count": 10,
            },
        ],
        "playlists": [
            {
                "name": "My Roadtrip",
                "description": "Songs for the road",
                "track_youtube_ids": ["yt_track_1", "yt_track_2"],
            }
        ],
    }

    mock_executor = MagicMock()
    mock_download_uc = MagicMock()
    mock_loop = MagicMock()
    mock_ws = MagicMock()

    import_uc = ImportBackupUseCase(uow_factory=in_memory_uow_factory)
    result = import_uc.execute(
        backup_dict=sample_backup,
        options=ImportBackupOptionsDTO(download_missing_audio=True),
        task_executor=mock_executor,
        download_use_case=mock_download_uc,
        loop=mock_loop,
        event_publisher=mock_ws,
    )

    assert result.status == "success"
    assert result.tracks_imported == 2
    assert result.tracks_queued_for_download == 2
    assert result.playlists_imported == 1
    assert result.settings_restored is True
    assert result.user_preferences == {"libraryViewMode": "grid", "shuffleEnabled": True}

    # Verify task executor submitted downloads for the missing tracks
    assert mock_executor.submit_download.call_count == 2
    mock_ws.publish_library_updated.assert_called_once()

    # Verify database persistence
    with in_memory_uow_factory() as uow:
        # Settings restored
        saved_settings = uow.settings.get()
        assert saved_settings.default_audio_quality == AudioQuality.MID_256K
        assert saved_settings.normalize_audio_lufs == -14.5

        # Tracks registered with PENDIENTE status and preserved metadata
        tracks = uow.tracks.list_all()
        assert len(tracks) == 2
        t1 = uow.tracks.get_by_youtube_id("yt_track_1")
        assert t1 is not None
        assert t1.status == DownloadStatus.PENDIENTE
        assert t1.metadata is not None
        assert t1.metadata.title == "Title One"
        assert t1.metadata.artist == "Artist One"
        assert t1.play_count == 5

        # Playlist created and linked
        playlists = [p for p in uow.playlists.list_all() if p.name == "My Roadtrip"]
        assert len(playlists) == 1
        p = playlists[0]
        assert len(p.tracks) == 2
        assert set(t.youtube_id for t in p.tracks) == {"yt_track_1", "yt_track_2"}


def test_backup_router_handlers(in_memory_uow_factory):
    """Verifies that backup router endpoints respond correctly."""
    from src.api.routers.backup_router import export_backup_get, export_backup_post
    from src.api.dependencies import Container

    container = Container()
    # Override uow_factory with in_memory
    container.uow_factory = in_memory_uow_factory

    # Test GET export
    exported = export_backup_get(preferences_json='{"theme": "dark"}', container=container)
    assert exported.format == "melosync-backup"
    assert exported.settings.user_preferences == {"theme": "dark"}

    # Test POST export
    exported_post = export_backup_post(body={"user_preferences": {"sidebarCollapsed": True}}, container=container)
    assert exported_post.format == "melosync-backup"
    assert exported_post.settings.user_preferences == {"sidebarCollapsed": True}


def test_import_backup_skips_downloading_local_tracks(in_memory_uow_factory):
    """Verifies that imported tracks with 'local://' schemes are not enqueued for YouTube download."""
    payload = {
        "format": "melosync-backup",
        "version": 1,
        "app_version": "2.1.0",
        "settings": {
            "default_audio_quality": "best",
            "normalize_audio_lufs": -14.0,
            "auto_tag_metadata": True,
        },
        "tracks": [
            {
                "youtube_id": "dQw4w9WgXcQ",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "original_title": "Rick Astley - Never Gonna Give You Up",
                "duration_seconds": 213,
                "channel_name": "RickAstleyVEVO",
            },
            {
                "youtube_id": "local_12345678",
                "url": "local://MyLocalSong.mp3",
                "original_title": "My Local Song",
                "duration_seconds": 180,
                "channel_name": "Local Artist",
            },
        ],
        "playlists": [],
    }

    mock_executor = MagicMock()
    mock_download_uc = MagicMock()
    mock_loop = MagicMock()
    mock_ws = MagicMock()

    import_uc = ImportBackupUseCase(uow_factory=in_memory_uow_factory)
    result = import_uc.execute(
        backup_dict=payload,
        options=ImportBackupOptionsDTO(
            restore_settings=True,
            download_missing_audio=True,
        ),
        task_executor=mock_executor,
        download_use_case=mock_download_uc,
        loop=mock_loop,
        event_publisher=mock_ws,
    )

    assert result.status == "success"
    assert result.tracks_imported == 2
    # Only the YouTube track is queued for download, NOT the local track
    assert result.tracks_queued_for_download == 1
    assert mock_executor.submit_download.call_count == 1

    queued_cmd = mock_executor.submit_download.call_args[0][1]
    assert queued_cmd.youtube_id == "dQw4w9WgXcQ"
    assert not queued_cmd.url.startswith("local://")

