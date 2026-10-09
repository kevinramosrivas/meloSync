"""Persistent bottom bar widget displaying global download progress and current job status."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from src.application.dto import DownloadProgressDTO, TrackDTO


class BottomBarWidget(QWidget):
    """Permanent bottom bar showing global progress and real-time state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BottomBarWidget")
        self.setFixedHeight(70)

        self._active_jobs: int = 0
        self._total_jobs: int = 0
        self._completed_jobs: int = 0

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 10, 24, 10)
        layout.setSpacing(24)

        # -------------------------------------------------------------
        # Left: Current song & stage text
        # -------------------------------------------------------------
        left_layout = QHBoxLayout()
        left_layout.setSpacing(12)

        self.icon_label = QLabel("🎵")
        self.icon_label.setStyleSheet("font-size: 24px;")
        left_layout.addWidget(self.icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setAlignment(Qt.AlignVCenter)

        self.title_label = QLabel("Listo")
        self.title_label.setObjectName("BottomStatusTitle")
        text_layout.addWidget(self.title_label)

        self.status_label = QLabel("Esperando descargas...")
        self.status_label.setObjectName("BottomStatusSubtitle")
        text_layout.addWidget(self.status_label)

        left_layout.addLayout(text_layout)
        layout.addLayout(left_layout, stretch=2)

        # -------------------------------------------------------------
        # Center: Global Progress Bar
        # -------------------------------------------------------------
        center_layout = QVBoxLayout()
        center_layout.setSpacing(4)
        center_layout.setAlignment(Qt.AlignVCenter)

        self.global_progress_bar = QProgressBar()
        self.global_progress_bar.setValue(0)
        self.global_progress_bar.setFixedHeight(8)
        center_layout.addWidget(self.global_progress_bar)

        self.progress_percent_label = QLabel("0%")
        self.progress_percent_label.setStyleSheet("font-size: 11px; color: #86868b; font-weight: 500;")
        self.progress_percent_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(self.progress_percent_label)

        layout.addLayout(center_layout, stretch=3)

        # -------------------------------------------------------------
        # Right: Active Counter Badge
        # -------------------------------------------------------------
        self.counter_badge = QLabel("Todo al día ✓")
        self.counter_badge.setFixedHeight(34)
        self.counter_badge.setMinimumWidth(140)
        self.counter_badge.setStyleSheet(
            "background-color: #232328; color: #30d158; border: 1px solid rgba(48, 209, 88, 0.3); "
            "border-radius: 12px; padding: 4px 16px; font-weight: 600; font-size: 12px;"
        )
        self.counter_badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.counter_badge, stretch=1)

    def on_job_added(self, title: str) -> None:
        """Called when a new track is queued."""
        self._active_jobs += 1
        self._total_jobs += 1
        self.title_label.setText(title)
        self.status_label.setText("Iniciando pipeline...")
        self._update_counter()

    def on_progress(self, dto: DownloadProgressDTO) -> None:
        """Called on every progress tick."""
        self.status_label.setText(f"{dto.status.value}: {dto.stage_description}")
        self.global_progress_bar.setValue(int(dto.progress_percent))
        self.progress_percent_label.setText(f"{int(dto.progress_percent)}%")

    def on_job_completed(self, track: TrackDTO) -> None:
        """Called when a track finishes processing."""
        self._active_jobs = max(0, self._active_jobs - 1)
        self._completed_jobs += 1
        self.title_label.setText(f"{track.artist} - {track.title}")
        self.status_label.setText("Completada y guardada")
        self.global_progress_bar.setValue(100)
        self.progress_percent_label.setText("100%")
        self._update_counter()

    def on_job_error(self, youtube_id: str, error_msg: str) -> None:
        """Called when a job fails."""
        self._active_jobs = max(0, self._active_jobs - 1)
        self.status_label.setText(f"Error: {error_msg[:40]}...")
        self._update_counter()

    def on_metadata_updated(self, track: TrackDTO) -> None:
        """Called when metadata of a track is updated."""
        self.title_label.setText(f"{track.artist} - {track.title}")
        self.status_label.setText("Metadatos actualizados")

    def _update_counter(self) -> None:
        if self._active_jobs > 0:
            self.counter_badge.setText(f"{self._active_jobs} descarga{'s' if self._active_jobs > 1 else ''} activa{'s' if self._active_jobs > 1 else ''}")
            self.counter_badge.setStyleSheet(
                "background-color: rgba(250, 45, 72, 0.2); color: #fa2d48; "
                "border: 1px solid rgba(250, 45, 72, 0.4); "
                "border-radius: 12px; padding: 4px 14px; font-weight: 600; font-size: 12px;"
            )
        else:
            self.counter_badge.setText("Todo al día")
            self.counter_badge.setStyleSheet(
                "background-color: #232328; color: #30d158; "
                "border: 1px solid rgba(48, 209, 88, 0.3); "
                "border-radius: 12px; padding: 4px 14px; font-weight: 600; font-size: 12px;"
            )

