"""Domain layer custom exceptions."""


class DomainException(Exception):
    """Base exception for all domain layer business rule violations."""
    pass


class EntityNotFoundException(DomainException):
    """Raised when an aggregate root or entity cannot be found."""

    def __init__(self, entity_name: str, identifier: str) -> None:
        self.entity_name = entity_name
        self.identifier = identifier
        super().__init__(f"{entity_name} with identifier '{identifier}' was not found.")


class InvalidStateTransitionException(DomainException):
    """Raised when an invalid status transition is attempted on an entity."""

    def __init__(self, current_state: str, target_state: str, reason: str = "") -> None:
        self.current_state = current_state
        self.target_state = target_state
        self.reason = reason
        msg = f"Cannot transition from state '{current_state}' to '{target_state}'."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(msg)


class DownloadException(DomainException):
    """Raised when a download operation fails."""

    def __init__(self, url: str, message: str) -> None:
        self.url = url
        super().__init__(f"Failed to download audio from '{url}': {message}")


class AudioProcessingException(DomainException):
    """Raised when audio conversion, normalization, or trimming fails."""

    def __init__(self, file_path: str, message: str) -> None:
        self.file_path = file_path
        super().__init__(f"Audio processing error on '{file_path}': {message}")


class MetadataFetchException(DomainException):
    """Raised when remote metadata service lookup fails."""

    def __init__(self, query: str, message: str) -> None:
        self.query = query
        super().__init__(f"Failed to fetch metadata for '{query}': {message}")


class TaggingException(DomainException):
    """Raised when embedding metadata or album artwork fails."""

    def __init__(self, file_path: str, message: str) -> None:
        self.file_path = file_path
        super().__init__(f"Failed to embed tags into '{file_path}': {message}")
