"""Unit tests for Domain Layer: Entities, state machine and validations."""

import unittest

from src.domain.entities import (
    AudioQuality,
    DownloadStatus,
    Playlist,
    SearchResult,
    Track,
    TrackMetadata,
)
from src.domain.exceptions import InvalidStateTransitionException


class TestDomainEntities(unittest.TestCase):
    def test_track_initial_state(self) -> None:
        track = Track(
            youtube_id="dQw4w9WgXcQ",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            original_title="Rick Astley - Never Gonna Give You Up (Official Music Video)",
            duration_seconds=213,
            channel_name="Rick Astley",
        )
        self.assertEqual(track.status, DownloadStatus.PENDIENTE)
        self.assertEqual(track.progress_percent, 0.0)
        self.assertIsNone(track.file_path)
        self.assertIsNone(track.error_message)
        self.assertEqual(track.display_title, "Rick Astley - Never Gonna Give You Up (Official Music Video)")
        self.assertEqual(track.duration_formatted, "3:33")

    def test_track_valid_state_transitions(self) -> None:
        track = Track(
            youtube_id="abc12345",
            url="https://youtube.com/watch?v=abc12345",
            original_title="Sample Song",
        )

        # 1. PENDIENTE -> DESCARGANDO
        track.mark_downloading()
        self.assertEqual(track.status, DownloadStatus.DESCARGANDO)

        # 2. DESCARGANDO -> PROCESANDO_AUDIO
        track.mark_processing_audio()
        self.assertEqual(track.status, DownloadStatus.PROCESANDO_AUDIO)

        # 3. PROCESANDO_AUDIO -> OBTENIENDO_METADATOS
        track.mark_fetching_metadata()
        self.assertEqual(track.status, DownloadStatus.OBTENIENDO_METADATOS)

        # 4. OBTENIENDO_METADATOS -> COMPLETADA
        meta = TrackMetadata(
            title="Never Gonna Give You Up",
            artist="Rick Astley",
            album="Whenever You Need Somebody",
            year=1987,
        )
        track.mark_completed("/music/Rick Astley - Never Gonna Give You Up.mp3", metadata=meta)
        self.assertEqual(track.status, DownloadStatus.COMPLETADA)
        self.assertEqual(track.progress_percent, 100.0)
        self.assertEqual(track.display_title, "Never Gonna Give You Up")
        self.assertEqual(track.display_artist, "Rick Astley")
        self.assertEqual(track.display_album, "Whenever You Need Somebody")

    def test_track_invalid_state_transition_raises_exception(self) -> None:
        track = Track(
            youtube_id="xyz987",
            url="https://youtube.com/watch?v=xyz987",
            original_title="Invalid Jump Song",
        )
        with self.assertRaises(InvalidStateTransitionException):
            track.mark_completed("/path.mp3")

    def test_track_progress_clamping(self) -> None:
        track = Track(youtube_id="123", url="http://yt", original_title="Test")
        track.update_progress(-10.0)
        self.assertEqual(track.progress_percent, 0.0)

        track.update_progress(150.0)
        self.assertEqual(track.progress_percent, 100.0)

        track.update_progress(45.678)
        self.assertEqual(track.progress_percent, 45.68)

    def test_playlist_management(self) -> None:
        playlist = Playlist(name="Rock Classics")
        track1 = Track(youtube_id="t1", url="http://1", original_title="Track 1")
        track2 = Track(youtube_id="t2", url="http://2", original_title="Track 2")

        playlist.add_track(track1)
        playlist.add_track(track2)
        self.assertEqual(len(playlist.tracks), 2)

        # Prevent duplicates by ID
        playlist.add_track(track1)
        self.assertEqual(len(playlist.tracks), 2)

        playlist.remove_track(track1.id)
        self.assertEqual(len(playlist.tracks), 1)
        self.assertEqual(playlist.tracks[0].id, track2.id)


if __name__ == "__main__":
    unittest.main()
