"""Unit tests for storage migration, consolidation, and path statistics."""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pytest

from src.api.main import create_app
from src.application.use_cases.consolidate_library import ConsolidateLibraryUseCase
from src.domain.entities import AppSettings, DownloadStatus, Track
from src.infrastructure.persistence.database import DatabaseManager
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
def temp_dirs():
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        yield Path(d1), Path(d2)


def test_consolidate_library_use_case_moves_files(temp_dirs):
    old_dir, new_dir = temp_dirs

    # Create dummy audio files in old_dir
    f1 = old_dir / "song1.mp3"
    f1.write_text("dummy audio 1")
    f2 = old_dir / "song2.mp3"
    f2.write_text("dummy audio 2")

    # Use isolated in-memory DB
    db = DatabaseManager(db_path=":memory:")
    db.init_database()
    uow_factory = lambda: SqlAlchemyUnitOfWork(db)

    with uow_factory() as uow:
        # Settings
        uow.settings.update(AppSettings(music_download_directory=str(new_dir)))

        # Create tracks pointing to old_dir
        t1 = Track(
            youtube_id="mig_1",
            url="https://youtube.com/watch?v=mig_1",
            original_title="Song 1",
            status=DownloadStatus.COMPLETADA,
            file_path=str(f1),
        )
        t2 = Track(
            youtube_id="mig_2",
            url="https://youtube.com/watch?v=mig_2",
            original_title="Song 2",
            status=DownloadStatus.COMPLETADA,
            file_path=str(f2),
        )
        # Track with non-existent file
        t3 = Track(
            youtube_id="mig_3",
            url="https://youtube.com/watch?v=mig_3",
            original_title="Song 3 Missing",
            status=DownloadStatus.COMPLETADA,
            file_path=str(old_dir / "missing.mp3"),
        )
        uow.tracks.add(t1)
        uow.tracks.add(t2)
        uow.tracks.add(t3)
        uow.commit()

        t1_id = t1.id
        t2_id = t2.id
        t3_id = t3.id

    uc = ConsolidateLibraryUseCase(uow_factory=uow_factory)
    report = uc.execute(target_directory=str(new_dir), move_files=True)

    assert report.moved_count == 2
    assert report.missing_count == 1
    assert (new_dir / "song1.mp3").exists()
    assert (new_dir / "song2.mp3").exists()
    assert not f1.exists()  # Was moved
    assert not f2.exists()

    # Verify DB paths were updated
    with uow_factory() as uow:
        t1_saved = uow.tracks.get_by_id(t1_id)
        t2_saved = uow.tracks.get_by_id(t2_id)
        assert t1_saved.file_path == str(new_dir / "song1.mp3")
        assert t2_saved.file_path == str(new_dir / "song2.mp3")


def test_storage_stats_and_consolidate_api(monkeypatch, temp_dirs):
    old_dir, new_dir = temp_dirs

    # Mock subprocess.run for browse-folder to avoid opening GUI dialog
    mock_run = MagicMock()
    mock_run.return_value.stdout = str(new_dir)
    monkeypatch.setattr("subprocess.run", mock_run)

    app = create_app()
    with TestClient(app) as client:
        # Check storage-stats
        res = client.get("/api/v1/settings/storage-stats")
        assert res.status_code == 200
        data = res.json()
        assert "active_directory" in data
        assert "active_dir_track_count" in data
        assert "other_locations_track_count" in data
        assert "missing_files_count" in data
        assert "total_library_tracks" in data

        # Check browse-folder returns path
        browse_res = client.post("/api/v1/settings/browse-folder")
        assert browse_res.status_code == 200
        assert browse_res.json()["path"] == str(new_dir)

        # Check consolidate endpoint
        cons_res = client.post("/api/v1/settings/consolidate", json={"target_directory": str(new_dir), "move_files": True})
        assert cons_res.status_code == 200
        cons_data = cons_res.json()
        assert "moved_count" in cons_data
        assert "message" in cons_data
