"""Unit and integration tests for Apple Music metadata candidate search and editing."""

from collections.abc import Callable
import os
from pathlib import Path
import tempfile
from typing import Optional
import unittest
from unittest.mock import MagicMock, patch

from mutagen.id3 import ID3, TIT2, TPE1, TALB
from mutagen.mp3 import MP3

from src.application.dto import (
    MetadataCandidateDTO,
    TrackDTO,
    UpdateTrackMetadataCommand,
)
from src.application.use_cases.edit_metadata import (
    SearchMetadataCandidatesUseCase,
    UpdateTrackMetadataUseCase,
)
from src.domain.entities import DownloadStatus, Track, TrackMetadata
from src.domain.repositories import IPlaylistRepository, ITrackRepository, IUnitOfWork
from src.infrastructure.audio.mutagen_tagger import MutagenTaggingService
from src.infrastructure.metadata.itunes_client import ITunesMetadataProvider


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


class TestMetadataEditing(unittest.TestCase):
    @patch("httpx.Client")
    def test_itunes_client_search_candidates(self, mock_client_cls) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_search_res = MagicMock()
        mock_search_res.status_code = 200
        mock_search_res.json.return_value = {
            "results": [
                {
                    "trackName": "Blinding Lights",
                    "artistName": "The Weeknd",
                    "collectionName": "After Hours",
                    "releaseDate": "2020-03-20T07:00:00Z",
                    "primaryGenreName": "R&B/Soul",
                    "trackNumber": 9,
                    "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music115/v4/100x100bb.jpg",
                },
                {
                    "trackName": "Blinding Lights (Remix)",
                    "artistName": "The Weeknd & ROSALÍA",
                    "collectionName": "Blinding Lights (Remix) - Single",
                    "releaseDate": "2020-12-04T08:00:00Z",
                    "primaryGenreName": "Pop",
                    "trackNumber": 1,
                    "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music125/v4/100x100bb.jpg",
                },
            ]
        }
        mock_client.get.return_value = mock_search_res

        provider = ITunesMetadataProvider()
        candidates = provider.search_candidates("Blinding Lights", limit=5)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].title, "Blinding Lights")
        self.assertEqual(candidates[0].artist, "The Weeknd")
        self.assertEqual(candidates[0].album, "After Hours")
        self.assertEqual(candidates[0].year, 2020)
        self.assertEqual(candidates[0].genre, "R&B/Soul")
        self.assertEqual(candidates[0].track_number, 9)
        self.assertIn("1000x1000bb.jpg", candidates[0].cover_url)

        self.assertEqual(candidates[1].title, "Blinding Lights (Remix)")
        self.assertEqual(candidates[1].artist, "The Weeknd & ROSALÍA")

    @patch("httpx.Client")
    def test_itunes_client_download_cover_bytes(self, mock_client_cls) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_res = MagicMock()
        mock_res.status_code = 200
        mock_res.content = b"\xff\xd8\xff\xe0\x00\x10JFIFfake_jpeg"
        mock_client.get.return_value = mock_res

        provider = ITunesMetadataProvider()
        bytes_out = provider.download_cover_bytes("https://is1-ssl.mzstatic.com/image/1000x1000bb.jpg")

        self.assertEqual(bytes_out, b"\xff\xd8\xff\xe0\x00\x10JFIFfake_jpeg")
        mock_client.get.assert_called_once_with("https://is1-ssl.mzstatic.com/image/1000x1000bb.jpg")

    def test_search_metadata_candidates_use_case(self) -> None:
        mock_provider = MagicMock()
        mock_provider.search_candidates.return_value = [
            TrackMetadata(
                title="Starboy",
                artist="The Weeknd",
                album="Starboy",
                year=2016,
                genre="Pop",
                track_number=1,
                cover_url="https://is1-ssl.mzstatic.com/image/1000x1000bb.jpg",
            )
        ]

        use_case = SearchMetadataCandidatesUseCase(metadata_provider=mock_provider)
        results = use_case.execute("Starboy", limit=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Starboy")
        self.assertEqual(results[0].artist, "The Weeknd")
        self.assertEqual(results[0].thumbnail_url, "https://is1-ssl.mzstatic.com/image/200x200bb.jpg")
        mock_provider.search_candidates.assert_called_once_with(query="Starboy", limit=10)

    def test_update_track_metadata_use_case_and_tagging(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            dummy_file = tmp_path / "Old Artist - Old Title.mp3"

            # Create a simple valid dummy file structure
            dummy_file.write_bytes(b"dummy mp3 data")

            track_repo = InMemoryTrackRepository()
            uow = InMemoryUnitOfWork(track_repo)
            uow_factory: Callable[[], IUnitOfWork] = lambda: uow

            track = Track(
                youtube_id="edit_test_123",
                url="https://youtube.com/watch?v=edit_test_123",
                original_title="Old Artist - Old Title",
                duration_seconds=200,
                channel_name="Old Artist",
                file_path=str(dummy_file),
                status=DownloadStatus.COMPLETADA,
                metadata=TrackMetadata(
                    title="Old Title",
                    artist="Old Artist",
                    album="Old Album",
                ),
            )
            track_repo.add(track)

            mock_provider = MagicMock()
            mock_provider.download_cover_bytes.return_value = b"fake_cover_bytes"

            mock_tagger = MagicMock()

            use_case = UpdateTrackMetadataUseCase(
                uow_factory=uow_factory,
                metadata_provider=mock_provider,
                tagging_service=mock_tagger,
            )

            cmd = UpdateTrackMetadataCommand(
                track_id=track.id,
                title="New Title",
                artist="New Artist",
                album="New Album",
                year=2024,
                genre="Synthwave",
                track_number=3,
                cover_url="https://apple.com/cover1000.jpg",
                cover_bytes=None,  # should trigger download
                rename_file=True,
            )

            updated_dto = use_case.execute(cmd)

            self.assertEqual(updated_dto.title, "New Title")
            self.assertEqual(updated_dto.artist, "New Artist")
            self.assertEqual(updated_dto.album, "New Album")

            # Check tagging service was called
            mock_tagger.apply_tags.assert_called_once()
            tagged_args = mock_tagger.apply_tags.call_args[0]
            self.assertEqual(tagged_args[1].title, "New Title")
            self.assertEqual(tagged_args[1].artist, "New Artist")
            self.assertEqual(tagged_args[1].year, 2024)
            self.assertEqual(tagged_args[1].cover_bytes, b"fake_cover_bytes")

            # Check file was renamed on disk
            expected_new_file = tmp_path / "New Artist - New Title.mp3"
            self.assertTrue(expected_new_file.exists())
            self.assertEqual(updated_dto.file_path, str(expected_new_file))

            # Check DB updated in UOW
            self.assertTrue(uow.committed)
            saved = track_repo.get_by_id(track.id)
            self.assertIsNotNone(saved)
            self.assertEqual(saved.display_title, "New Title")
            self.assertEqual(saved.display_artist, "New Artist")
            self.assertEqual(saved.display_album, "New Album")

    def test_update_non_existent_track_raises_error(self) -> None:
        track_repo = InMemoryTrackRepository()
        uow = InMemoryUnitOfWork(track_repo)
        uow_factory: Callable[[], IUnitOfWork] = lambda: uow

        use_case = UpdateTrackMetadataUseCase(
            uow_factory=uow_factory,
            metadata_provider=MagicMock(),
            tagging_service=MagicMock(),
        )

        cmd = UpdateTrackMetadataCommand(
            track_id="non_existent_id",
            title="Title",
            artist="Artist",
        )

        with self.assertRaises(ValueError):
            use_case.execute(cmd)


if __name__ == "__main__":
    unittest.main()
