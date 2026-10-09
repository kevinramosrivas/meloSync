"""Library View: Local music library displaying downloaded songs with tags, artwork and playback/file management."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.application.dto import TrackDTO

logger = logging.getLogger(__name__)


class LibraryView(QWidget):
    """Displays local music library tracks with options to play, open or delete."""

    delete_requested = Signal(str)  # track_id
    edit_requested = Signal(str)    # track_id
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tracks: list[TrackDTO] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 20)
        main_layout.setSpacing(18)

        # -------------------------------------------------------------
        # Header
        # -------------------------------------------------------------
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(4)

        title = QLabel("Biblioteca Local")
        title.setObjectName("ViewTitle")
        header_text.addWidget(title)

        self.subtitle = QLabel("0 canciones guardadas y etiquetadas en alta fidelidad.")
        self.subtitle.setObjectName("ViewSubtitle")
        header_text.addWidget(self.subtitle)

        header.addLayout(header_text)
        header.addStretch()

        refresh_btn = QPushButton("🔄 Actualizar")
        refresh_btn.setProperty("class", "SecondaryButton")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(lambda: self.refresh_requested.emit())
        header.addWidget(refresh_btn)

        main_layout.addLayout(header)

        # -------------------------------------------------------------
        # Quick Filter
        # -------------------------------------------------------------
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("🔍 Filtrar por título, artista o álbum...")
        self.filter_input.textChanged.connect(self._apply_filter)
        main_layout.addWidget(self.filter_input)

        # -------------------------------------------------------------
        # Library Table
        # -------------------------------------------------------------
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Título", "Artista", "Álbum", "Duración", "Acciones"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 85)
        self.table.setColumnWidth(4, 395)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(58)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)

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
        """Proportionally distributes remaining width: Title 44%, Artist 31%, Album 25%."""
        if not hasattr(self, "table"):
            return
        viewport_width = self.table.viewport().width()
        if viewport_width <= 0:
            return

        duration_width = 85
        actions_width = 395
        self.table.setColumnWidth(3, duration_width)
        self.table.setColumnWidth(4, actions_width)

        remaining = viewport_width - duration_width - actions_width
        if remaining > 50:
            title_width = int(remaining * 0.44)
            artist_width = int(remaining * 0.31)
            album_width = remaining - title_width - artist_width
            self.table.setColumnWidth(0, max(120, title_width))
            self.table.setColumnWidth(1, max(100, artist_width))
            self.table.setColumnWidth(2, max(80, album_width))

    def set_tracks(self, tracks: list[TrackDTO]) -> None:
        """Populates the table with library tracks."""
        self._tracks = tracks
        self._render_tracks(tracks)

    def _render_tracks(self, tracks: list[TrackDTO]) -> None:
        self.table.setRowCount(len(tracks))
        self.subtitle.setText(f"{len(self._tracks)} canciones en tu biblioteca.")

        for row, track in enumerate(tracks):
            # Title
            t_item = QTableWidgetItem(track.title)
            t_item.setToolTip(track.file_path or track.title)
            t_item.setData(Qt.UserRole, track.id)
            self.table.setItem(row, 0, t_item)

            # Artist
            a_item = QTableWidgetItem(track.artist)
            self.table.setItem(row, 1, a_item)

            # Album
            alb_item = QTableWidgetItem(track.album)
            alb_item.setForeground(Qt.gray)
            self.table.setItem(row, 2, alb_item)

            # Duration
            d_item = QTableWidgetItem(track.duration_formatted)
            d_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, d_item)

            # Actions container
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 4, 2, 4)
            action_layout.setSpacing(6)
            action_layout.setAlignment(Qt.AlignCenter)

            # 1. Play button
            play_btn = QPushButton("▶ Play")
            play_btn.setProperty("class", "TablePlayButton")
            play_btn.setCursor(Qt.PointingHandCursor)
            play_btn.setFixedHeight(34)
            play_btn.setFixedWidth(82)
            play_btn.setToolTip("Reproducir canción en el reproductor del sistema")
            play_btn.clicked.connect(lambda _, fp=track.file_path: self._open_file(fp))
            action_layout.addWidget(play_btn)

            # 2. Edit Metadata button
            edit_btn = QPushButton("✏️ Editar")
            edit_btn.setProperty("class", "TableEditButton")
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setFixedHeight(34)
            edit_btn.setFixedWidth(88)
            edit_btn.setToolTip("Editar metadatos y carátula buscando en Apple Music")
            edit_btn.clicked.connect(lambda _, tid=track.id: self.edit_requested.emit(tid))
            action_layout.addWidget(edit_btn)

            # 3. Open Folder button
            folder_btn = QPushButton("📁 Carpeta")
            folder_btn.setProperty("class", "TableFolderButton")
            folder_btn.setCursor(Qt.PointingHandCursor)
            folder_btn.setFixedHeight(34)
            folder_btn.setFixedWidth(94)
            folder_btn.setToolTip("Abrir archivo en su carpeta contenedora")
            folder_btn.clicked.connect(lambda _, fp=track.file_path: self._open_folder(fp))
            action_layout.addWidget(folder_btn)

            # 4. Delete button
            del_btn = QPushButton("🗑 Borrar")
            del_btn.setProperty("class", "TableDeleteButton")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setFixedHeight(34)
            del_btn.setFixedWidth(84)
            del_btn.setToolTip("Eliminar de la biblioteca y borrar archivo de audio")
            del_btn.clicked.connect(lambda _, tid=track.id, tname=track.title: self._confirm_delete(tid, tname))
            action_layout.addWidget(del_btn)

            self.table.setCellWidget(row, 4, action_widget)
            self.table.setRowHeight(row, 58)

        self._adjust_columns()

    def _on_row_double_clicked(self, row: int, column: int) -> None:
        """Opens metadata editor when double clicking a row (except actions column)."""
        if column != 4:
            item = self.table.item(row, 0)
            if item:
                track_id = item.data(Qt.UserRole)
                if track_id:
                    self.edit_requested.emit(track_id)

    def _apply_filter(self, text: str) -> None:
        """Filters locally rendered tracks matching keyword."""
        q = text.lower().strip()
        if not q:
            self._render_tracks(self._tracks)
            return

        filtered = [
            t for t in self._tracks
            if q in t.title.lower() or q in t.artist.lower() or q in t.album.lower()
        ]
        self._render_tracks(filtered)

    def _open_file(self, file_path: str | None) -> None:
        """Launches default system music player for the file."""
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Archivo no encontrado", "El archivo de audio no existe en el disco.")
            return

        if os.name == "nt":
            os.startfile(file_path)
        else:
            subprocess.run(["xdg-open", file_path], check=False)

    def _open_folder(self, file_path: str | None) -> None:
        """Opens the containing folder and selects the file in Windows Explorer."""
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Archivo no encontrado", "El archivo de audio no existe en el disco.")
            return

        norm_path = os.path.normpath(file_path)
        if os.name == "nt":
            subprocess.run(f'explorer /select,"{norm_path}"', check=False)
        else:
            folder = os.path.dirname(norm_path)
            subprocess.run(["xdg-open", folder], check=False)

    def _confirm_delete(self, track_id: str, title: str) -> None:
        """Prompts user for deletion confirmation."""
        reply = QMessageBox.question(
            self,
            "Eliminar Canción",
            f"¿Deseas eliminar '{title}' de la biblioteca y borrar su archivo?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.delete_requested.emit(track_id)

