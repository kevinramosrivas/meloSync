"""Domain-level custom exceptions for meloSync."""

from __future__ import annotations


class MeloSyncDomainException(Exception):
    """Base exception for domain layer errors."""
    pass


class InvalidStateTransitionException(MeloSyncDomainException):
    """Raised when an illegal transition is attempted on the track state machine."""

    def __init__(self, current_state: str, target_state: str, reason: str = "") -> None:
        self.current_state = current_state
        self.target_state = target_state
        self.reason = reason
        msg = f"No se puede transicionar de '{current_state}' a '{target_state}'."
        if reason:
            msg += f" Motivo: {reason}"
        super().__init__(msg)


class TrackNotFoundException(MeloSyncDomainException):
    """Raised when a track ID or YouTube ID is not found in repositories."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Pista no encontrada con identificador: '{identifier}'")


class PlaylistNotFoundException(MeloSyncDomainException):
    """Raised when a playlist is not found."""

    def __init__(self, playlist_id: str) -> None:
        super().__init__(f"Playlist no encontrada con ID: '{playlist_id}'")


class DownloadException(MeloSyncDomainException):
    """Raised when yt-dlp download fails."""
    pass


class AudioProcessingException(MeloSyncDomainException):
    """Raised when ffmpeg normalization or audio conversion fails."""
    pass


class MetadataFetchException(MeloSyncDomainException):
    """Raised when iTunes API search or network retrieval fails."""
    pass


class TaggingException(MeloSyncDomainException):
    """Raised when mutagen fails to write metadata or cover art."""
    pass
