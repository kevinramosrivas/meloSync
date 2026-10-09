"""PySide6 Signals for thread-safe UI communication."""

from PySide6.QtCore import QObject, Signal

from src.application.dto import DownloadProgressDTO, TrackDTO


class DownloadWorkerSignals(QObject):
    """Signals emitted by background download and audio processing workers."""

    started = Signal(str)  # youtube_id
    progress = Signal(object)  # DownloadProgressDTO
    finished = Signal(object)  # TrackDTO
    error = Signal(str, str)  # (youtube_id, error_message)


class SearchWorkerSignals(QObject):
    """Signals emitted by background YouTube search workers."""

    started = Signal()
    results_ready = Signal(list)  # list[SearchResultItemDTO]
    error = Signal(str)  # error_message


class MetadataSearchWorkerSignals(QObject):
    """Signals emitted by background Apple Music candidate search workers."""

    started = Signal(int)  # search_id
    results_ready = Signal(int, list)  # (search_id, list[MetadataCandidateDTO])
    error = Signal(int, str)  # (search_id, error_message)



class CoverDownloadSignals(QObject):
    """Signals emitted by background artwork download worker."""

    started = Signal(str)  # cover_url
    cover_ready = Signal(str, bytes)  # (cover_url, cover_bytes)
    error = Signal(str, str)  # (cover_url, error_message)


class UpdateMetadataWorkerSignals(QObject):
    """Signals emitted by background metadata update worker."""

    started = Signal(str)  # track_id
    finished = Signal(object)  # TrackDTO
    error = Signal(str, str)  # (track_id, error_message)

