"""Application events and publisher interface for real-time notifications."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .dto import DownloadProgressDTO, TrackDTO


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True, frozen=True)
class ApplicationEvent:
    """Base event payload structure."""
    event_type: str
    data: dict[str, Any]
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            object.__setattr__(self, "timestamp", utc_now_iso())

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class IEventPublisher(ABC):
    """Port for publishing application events to subscribers (WebSockets, loggers, UI)."""

    @abstractmethod
    def publish(self, event: ApplicationEvent) -> None:
        """Publishes an event synchronously or schedules it asynchronously."""
        raise NotImplementedError

    def publish_progress(self, progress: DownloadProgressDTO) -> None:
        """Helper to broadcast download progress event."""
        payload = {
            "track_id": progress.track_id,
            "youtube_id": progress.youtube_id,
            "status": progress.status.value,
            "progress_percent": progress.progress_percent,
            "stage_description": progress.stage_description,
            "speed_text": progress.speed_text,
            "eta_text": progress.eta_text,
        }
        self.publish(ApplicationEvent(event_type="download_progress", data=payload))

    def publish_track_completed(self, track: TrackDTO) -> None:
        """Helper to broadcast track completion event."""
        self.publish(ApplicationEvent(event_type="download_completed", data={"track": asdict(track)}))

    def publish_library_updated(self) -> None:
        """Helper to signal library content changes."""
        self.publish(ApplicationEvent(event_type="library_updated", data={"message": "Library refreshed"}))
