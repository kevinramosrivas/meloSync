"""Unit tests for Infrastructure layer adapters."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.domain.entities import DownloadStatus, Track, TrackMetadata
from src.infrastructure.metadata.itunes_client import ITunesMetadataProvider
from src.infrastructure.metadata.title_cleaner import RegexTitleCleaner
from src.infrastructure.persistence.database import DatabaseManager
from src.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class TestInfrastructureAdapters(unittest.TestCase):
    def test_regex_title_cleaner(self) -> None:
        cleaner = RegexTitleCleaner()

        # Case 1: Standard YouTube official video format
        raw1 = "Queen - Bohemian Rhapsody (Official Video Remastered)"
        artist1, title1 = cleaner.clean(raw1)
        self.assertEqual(artist1, "Queen")
        self.assertEqual(title1, "Bohemian Rhapsody")

        # Case 2: Bracket noise and 4K tags
        raw2 = "Daft Punk - Get Lucky [Official Audio] [4K]"
        artist2, title2 = cleaner.clean(raw2)
        self.assertEqual(artist2, "Daft Punk")
        self.assertEqual(title2, "Get Lucky")

        # Case 3: Title without artist delimiter
        raw3 = "Despacito (Video Oficial)"
        artist3, title3 = cleaner.clean(raw3)
        self.assertEqual(artist3, "")
        self.assertEqual(title3, "Despacito")

    def test_database_and_unit_of_work(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
            db_path = tmp_db.name

        try:
            db_mgr = DatabaseManager(db_path=db_path)
            db_mgr.init_database()

            uow = SqlAlchemyUnitOfWork(db_mgr)
            track = Track(
                youtube_id="infra_test_123",
                url="https://youtube.com/watch?v=infra_test_123",
                original_title="Test Artist - Test Song",
                channel_name="Test Channel",
            )

            with uow:
                uow.tracks.add(track)
                uow.commit()

            # Read back in a new session
            with uow:
                saved = uow.tracks.get_by_youtube_id("infra_test_123")
                self.assertIsNotNone(saved)
                self.assertEqual(saved.youtube_id, "infra_test_123")
                self.assertEqual(saved.status, DownloadStatus.PENDIENTE)

                # Update track status and metadata
                saved.mark_downloading()
                saved.metadata = TrackMetadata(
                    title="Test Song",
                    artist="Test Artist",
                    album="Test Album",
                    year=2024,
                )
                uow.tracks.update(saved)
                uow.commit()

            with uow:
                updated = uow.tracks.get_by_youtube_id("infra_test_123")
                self.assertIsNotNone(updated)
                self.assertEqual(updated.status, DownloadStatus.DESCARGANDO)
                self.assertEqual(updated.display_title, "Test Song")
                self.assertEqual(updated.display_artist, "Test Artist")
                self.assertEqual(updated.display_album, "Test Album")
        finally:
            db_mgr.remove_session()
            db_mgr.engine.dispose()
            Path(db_path).unlink(missing_ok=True)

    @patch("httpx.Client")
    def test_itunes_client_metadata_lookup(self, mock_client_cls) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_search_res = MagicMock()
        mock_search_res.status_code = 200
        mock_search_res.json.return_value = {
            "results": [
                {
                    "trackName": "Viva La Vida",
                    "artistName": "Coldplay",
                    "collectionName": "Viva La Vida or Death and All His Friends",
                    "releaseDate": "2008-06-12T07:00:00Z",
                    "primaryGenreName": "Alternative",
                    "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music/100x100bb.jpg",
                }
            ]
        }

        mock_img_res = MagicMock()
        mock_img_res.status_code = 200
        mock_img_res.content = b"fake_high_res_jpeg_bytes"

        # First call is search, second is cover download
        mock_client.get.side_effect = [mock_search_res, mock_img_res]

        provider = ITunesMetadataProvider()
        meta = provider.lookup("Viva La Vida", artist="Coldplay")

        self.assertIsNotNone(meta)
        self.assertEqual(meta.title, "Viva La Vida")
        self.assertEqual(meta.artist, "Coldplay")
        self.assertEqual(meta.album, "Viva La Vida or Death and All His Friends")
        self.assertEqual(meta.year, 2008)
        self.assertEqual(meta.cover_bytes, b"fake_high_res_jpeg_bytes")
        # Ensure 100x100 was upgraded to 1000x1000
        self.assertIn("1000x1000bb.jpg", meta.cover_url)


if __name__ == "__main__":
    unittest.main()
