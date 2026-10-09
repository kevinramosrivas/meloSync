"""Unit tests for Application Layer Use Cases using Mocks and unittest."""

from collections.abc import Callable
import os
from pathlib import Path
import tempfile
from typing import Optional
import unittest
from unittest.mock import MagicMock

from src.application.dto import (
    DownloadProgressDTO,
    DownloadTrackCommand,
    SearchQueryDTO,
)
from src.application.use_cases.download_and_process import DownloadAndProcessTrackUseCase
from src.application.use_cases.search_youtube import SearchYouTubeUseCase
from src.domain.entities import (
    AudioQuality,
    DownloadStatus,
    SearchResult,
    Track,
    TrackMetadata,
)
from src.domain.repositories import IPlaylistRepository, ITrackRepository, IUnitOfWork


class InMemoryTrackRepository(ITrackRepository):
    def __init__(self) -> None:
        self.tracks: dict[str, Track] = {}

    def add(self, track: Track) -> Track:
        self.tracks[track.id] = track
        return track

    def get_by_id(self, track_id: str) -> Optional[Track]:
        return self.tracks.get(track_id)

    def get_by_youtube_id(self, youtube_id: str) -> Optional[Track]:
        for t in self.tracks.values():
            if t.youtube_id == youtube_id:
                return t
        return None

    def list_all(self) -> list[Track]:
        return list(self.tracks.values())

    def list_by_status(self, status: DownloadStatus) -> list[Track]:
        return [t for t in self.tracks.values() if t.status == status]

    def update(self, track: Track) -> Track:
        self.tracks[track.id] = track
        return track

    def delete(self, track_id: str) -> bool:
        if track_id in self.tracks:
            del self.tracks[track_id]
            return True
        return False


class InMemoryUnitOfWork(IUnitOfWork):
    def __init__(self, track_repo: InMemoryTrackRepository) -> None:
        self.tracks = track_repo
        self.playlists = MagicMock(spec=IPlaylistRepository)
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "InMemoryUnitOfWork":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.rollback()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class TestApplicationUseCases(unittest.TestCase):
    def test_search_youtube_use_case(self) -> None:
        search_service = MagicMock()
        search_service.search.return_value = [
            SearchResult(
                youtube_id="vid1",
                title="Bohemian Rhapsody",
                duration_seconds=354,
                channel_name="Queen Official",
                thumbnail_url="http://thumb.jpg",
                url="https://youtube.com/watch?v=vid1",
            )
        ]

        use_case = SearchYouTubeUseCase(search_service=search_service)
        results = use_case.execute(SearchQueryDTO(query="Bohemian Rhapsody", max_results=5))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].youtube_id, "vid1")
        self.assertEqual(results[0].title, "Bohemian Rhapsody")
        self.assertEqual(results[0].duration_formatted, "5:54")
        search_service.search.assert_called_once_with("Bohemian Rhapsody", max_results=5)

    def test_download_and_process_pipeline_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            track_repo = InMemoryTrackRepository()
            uow = InMemoryUnitOfWork(track_repo)
            uow_factory: Callable[[], IUnitOfWork] = lambda: uow

            downloader = MagicMock()
            raw_audio_file = tmp_path / "raw_audio.opus"
            raw_audio_file.write_text("dummy audio stream")
            downloader.download.return_value = str(raw_audio_file)

            processor = MagicMock()
            processed_audio_file = tmp_path / "processed_audio.mp3"
            processed_audio_file.write_text("processed normalized audio")
            processor.normalize_and_trim.return_value = str(processed_audio_file)

            metadata_provider = MagicMock()
            metadata_provider.lookup.return_value = TrackMetadata(
                title="Clocks",
                artist="Coldplay",
                album="A Rush of Blood to the Head",
                year=2002,
                cover_url="https://itunes.apple.com/cover1000.jpg",
            )

            cleaner = MagicMock()
            cleaner.clean.return_value = ("Coldplay", "Clocks")

            tagger = MagicMock()

            use_case = DownloadAndProcessTrackUseCase(
                uow_factory=uow_factory,
                downloader_service=downloader,
                audio_processor=processor,
                metadata_provider=metadata_provider,
                title_cleaner=cleaner,
                tagging_service=tagger,
                output_directory=str(tmp_path),
            )

            progress_events: list[DownloadProgressDTO] = []

            command = DownloadTrackCommand(
                youtube_id="coldplay_clocks",
                url="https://youtube.com/watch?v=coldplay_clocks",
                original_title="Coldplay - Clocks (Official Video)",
                duration_seconds=307,
                channel_name="Coldplay",
                quality=AudioQuality.BEST,
            )

            result_dto = use_case.execute(command, progress_callback=lambda p: progress_events.append(p))

            # Assertions
            self.assertEqual(result_dto.status, DownloadStatus.COMPLETADA.value)
            self.assertEqual(result_dto.title, "Clocks")
            self.assertEqual(result_dto.artist, "Coldplay")
            self.assertEqual(result_dto.album, "A Rush of Blood to the Head")

            # Verify pipeline steps were called
            downloader.download.assert_called_once()
            processor.normalize_and_trim.assert_called_once()
            metadata_provider.lookup.assert_called_once()
            tagger.apply_tags.assert_called_once()

            # Verify progress events covered stages
            statuses_emitted = [e.status for e in progress_events]
            self.assertIn(DownloadStatus.PENDIENTE, statuses_emitted)
            self.assertIn(DownloadStatus.DESCARGANDO, statuses_emitted)
            self.assertIn(DownloadStatus.PROCESANDO_AUDIO, statuses_emitted)
            self.assertIn(DownloadStatus.OBTENIENDO_METADATOS, statuses_emitted)
            self.assertIn(DownloadStatus.COMPLETADA, statuses_emitted)


if __name__ == "__main__":
    unittest.main()
