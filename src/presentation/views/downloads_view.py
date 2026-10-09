"""Downloads View: Live monitoring of active track downloads and the audio processing pipeline."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.application.dto import DownloadProgressDTO, TrackDTO
from src.domain.entities import DownloadStatus


def _get_badge_class(status: DownloadStatus) -> str:
    if status == DownloadStatus.PENDIENTE:
        return "BadgePending"
    elif status == DownloadStatus.DESCARGANDO:
        return "BadgeDownloading"
    elif status == DownloadStatus.PROCESANDO_AUDIO:
        return "BadgeProcessing"
    elif status == DownloadStatus.OBTENIENDO_METADATOS:
        return "BadgeMetadata"
    elif status == DownloadStatus.COMPLETADA:
        return "BadgeCompleted"
    elif status == DownloadStatus.ERROR:
        return "BadgeError"
    return "BadgePending"


class DownloadsView(QWidget):
    """Real-time monitoring view for active downloads and pipeline stages."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._row_map: dict[str, int] = {}  # youtube_id -> table row
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 20)
        main_layout.setSpacing(18)

        # Header
        header = QVBoxLayout()
        header.setSpacing(4)

        title = QLabel("Cola de Descargas")
        title.setObjectName("ViewTitle")
        header.addWidget(title)

        self.subtitle = QLabel("Monitoreo en tiempo real de la máquina de estados y procesamiento.")
        self.subtitle.setObjectName("ViewSubtitle")
        header.addWidget(self.subtitle)

        main_layout.addLayout(header)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Canción", "Estado", "Progreso", "Detalle"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 190)
        self.table.setColumnWidth(2, 220)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(58)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)

        main_layout.addWidget(self.table)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Dynamically adjusts column widths proportionally on window resize."""
        super().resizeEvent(event)
        self._adjust_columns()

    def showEvent(self, event) -> None:
        """Ensures columns are proportionally sized upon becoming visible."""
        super().showEvent(event)
        self._adjust_columns()

    def _adjust_columns(self) -> None:
        """Proportionally distributes remaining width: Song 55%, Detail 45%."""
        if not hasattr(self, "table"):
            return
        viewport_width = self.table.viewport().width()
        if viewport_width <= 0:
            return

        status_width = 190
        progress_width = 220
        self.table.setColumnWidth(1, status_width)
        self.table.setColumnWidth(2, progress_width)

        remaining = viewport_width - status_width - progress_width
        if remaining > 50:
            song_width = int(remaining * 0.55)
            detail_width = remaining - song_width
            self.table.setColumnWidth(0, max(140, song_width))
            self.table.setColumnWidth(3, max(120, detail_width))

    def _get_badge_label(self, row: int) -> QLabel | None:
        """Retrieves badge QLabel from cell container."""
        w = self.table.cellWidget(row, 1)
        if isinstance(w, QLabel):
            return w
        if w:
            return w.findChild(QLabel)
        return None

    def _get_progress_bar(self, row: int) -> QProgressBar | None:
        """Retrieves QProgressBar from cell container."""
        w = self.table.cellWidget(row, 2)
        if isinstance(w, QProgressBar):
            return w
        if w:
            return w.findChild(QProgressBar)
        return None

    def register_item(self, youtube_id: str, title: str) -> None:
        """Registers a new job in the downloads queue."""
        if youtube_id in self._row_map:
            row = self._row_map[youtube_id]
        else:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._row_map[youtube_id] = row
            self.table.setRowHeight(row, 58)

        # Title
        t_item = QTableWidgetItem(title)
        self.table.setItem(row, 0, t_item)

        # Badge in container
        badge_container = QWidget()
        badge_layout = QHBoxLayout(badge_container)
        badge_layout.setContentsMargins(4, 4, 4, 4)
        badge_layout.setAlignment(Qt.AlignCenter)

        badge = QLabel("PENDIENTE")
        badge.setProperty("class", "BadgePending")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedHeight(30)
        badge.setMinimumWidth(160)
        badge_layout.addWidget(badge)
        self.table.setCellWidget(row, 1, badge_container)

        # Progress bar in container
        pbar_container = QWidget()
        pbar_layout = QHBoxLayout(pbar_container)
        pbar_layout.setContentsMargins(8, 8, 8, 8)
        pbar_layout.setAlignment(Qt.AlignCenter)

        pbar = QProgressBar()
        pbar.setValue(0)
        pbar.setFixedHeight(10)
        pbar_layout.addWidget(pbar)
        self.table.setCellWidget(row, 2, pbar_container)

        # Detail text
        d_item = QTableWidgetItem("En cola...")
        d_item.setForeground(Qt.gray)
        self.table.setItem(row, 3, d_item)

        self._adjust_columns()

    def update_progress(self, dto: DownloadProgressDTO) -> None:
        """Updates live progress and stage information for a running job."""
        if dto.youtube_id not in self._row_map:
            self.register_item(dto.youtube_id, f"Video {dto.youtube_id}")

        row = self._row_map[dto.youtube_id]

        # Update Badge
        badge = self._get_badge_label(row)
        if badge:
            badge.setText(dto.status.value)
            badge.setProperty("class", _get_badge_class(dto.status))
            badge.style().unpolish(badge)
            badge.style().polish(badge)

        # Update ProgressBar
        pbar = self._get_progress_bar(row)
        if pbar:
            pbar.setValue(int(dto.progress_percent))

        # Update Detail
        detail_msg = dto.stage_description
        if dto.speed_text:
            detail_msg += f" • {dto.speed_text}"
        if dto.eta_text:
            detail_msg += f" • ETA {dto.eta_text}"

        d_item = self.table.item(row, 3)
        if d_item:
            d_item.setText(detail_msg)

    def mark_completed(self, track: TrackDTO) -> None:
        """Updates row when track completes pipeline."""
        if track.youtube_id in self._row_map:
            row = self._row_map[track.youtube_id]

            # Update Title with enriched title
            t_item = self.table.item(row, 0)
            if t_item:
                t_item.setText(f"{track.artist} - {track.title}")

            badge = self._get_badge_label(row)
            if badge:
                badge.setText("COMPLETADA")
                badge.setProperty("class", "BadgeCompleted")
                badge.style().unpolish(badge)
                badge.style().polish(badge)

            pbar = self._get_progress_bar(row)
            if pbar:
                pbar.setValue(100)

            d_item = self.table.item(row, 3)
            if d_item:
                d_item.setText("Etiquetada y guardada ✓")

    def mark_error(self, youtube_id: str, error_msg: str) -> None:
        """Updates row when job fails."""
        if youtube_id in self._row_map:
            row = self._row_map[youtube_id]

            badge = self._get_badge_label(row)
            if badge:
                badge.setText("ERROR")
                badge.setProperty("class", "BadgeError")
                badge.style().unpolish(badge)
                badge.style().polish(badge)

            d_item = self.table.item(row, 3)
            if d_item:
                d_item.setText(f"Error: {error_msg[:60]}")
                d_item.setToolTip(error_msg)
