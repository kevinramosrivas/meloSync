"""Search View: YouTube search interface displaying tracks with duration and one-click download."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.application.dto import SearchQueryDTO, SearchResultItemDTO

logger = logging.getLogger(__name__)


class SearchView(QWidget):
    """View allowing the user to search YouTube and trigger audio downloads."""

    search_requested = Signal(SearchQueryDTO)
    download_requested = Signal(SearchResultItemDTO)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_results: list[SearchResultItemDTO] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 28, 32, 20)
        main_layout.setSpacing(20)

        # -------------------------------------------------------------
        # Header
        # -------------------------------------------------------------
        header = QVBoxLayout()
        header.setSpacing(4)

        title = QLabel("Buscar en YouTube")
        title.setObjectName("ViewTitle")
        header.addWidget(title)

        subtitle = QLabel("Explora millones de canciones o pega un enlace directo de YouTube.")
        subtitle.setObjectName("ViewSubtitle")
        header.addWidget(subtitle)

        main_layout.addLayout(header)

        # -------------------------------------------------------------
        # Search Bar
        # -------------------------------------------------------------
        search_box = QHBoxLayout()
        search_box.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Nombre de canción, artista o enlace (ej: Bohemian Rhapsody)...")
        self.search_input.returnPressed.connect(self._on_search_clicked)
        search_box.addWidget(self.search_input)

        self.search_btn = QPushButton("Buscar")
        self.search_btn.setProperty("class", "AccentButton")
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.setFixedHeight(42)
        self.search_btn.clicked.connect(self._on_search_clicked)
        search_box.addWidget(self.search_btn)

        main_layout.addLayout(search_box)

        # Status / Feedback label
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #86868b; font-size: 12px; padding-left: 2px;")
        main_layout.addWidget(self.status_label)

        # -------------------------------------------------------------
        # Results Table
        # -------------------------------------------------------------
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels(["Título", "Canal / Artista", "Duración", "Acción"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.results_table.setColumnWidth(2, 90)
        self.results_table.setColumnWidth(3, 175)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.verticalHeader().setDefaultSectionSize(58)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setShowGrid(False)

        main_layout.addWidget(self.results_table)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Dynamically adjusts column widths proportionally on window resize."""
        super().resizeEvent(event)
        self._adjust_columns()

    def showEvent(self, event) -> None:
        """Ensures columns are proportionally sized upon becoming visible."""
        super().showEvent(event)
        self._adjust_columns()

    def _adjust_columns(self) -> None:
        """Proportionally allocates remaining width: 60% Title, 40% Channel/Artist."""
        if not hasattr(self, "results_table"):
            return
        viewport_width = self.results_table.viewport().width()
        if viewport_width <= 0:
            return

        duration_width = 90
        action_width = 175
        self.results_table.setColumnWidth(2, duration_width)
        self.results_table.setColumnWidth(3, action_width)

        remaining = viewport_width - duration_width - action_width
        if remaining > 50:
            title_width = int(remaining * 0.60)
            channel_width = remaining - title_width
            self.results_table.setColumnWidth(0, max(140, title_width))
            self.results_table.setColumnWidth(1, max(120, channel_width))

    def _on_search_clicked(self) -> None:
        """Triggered when Search button or Enter is pressed."""
        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText("Por favor, ingresa un término de búsqueda o URL.")
            return

        self.status_label.setText(f"🔍 Buscando '{query}' en YouTube...")
        self.search_btn.setEnabled(False)
        self.search_input.setEnabled(False)
        self.results_table.setRowCount(0)

        query_dto = SearchQueryDTO(query=query, max_results=15)
        self.search_requested.emit(query_dto)

    def set_results(self, results: list[SearchResultItemDTO]) -> None:
        """Populates the table with search results."""
        self._current_results = results
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.results_table.setRowCount(len(results))

        if not results:
            self.status_label.setText("No se encontraron resultados para la búsqueda.")
            return

        self.status_label.setText(f"Se encontraron {len(results)} canciones.")

        for row, item in enumerate(results):
            # Title
            title_item = QTableWidgetItem(item.title)
            title_item.setToolTip(item.title)
            self.results_table.setItem(row, 0, title_item)

            # Channel / Artist
            channel_item = QTableWidgetItem(item.channel_name)
            channel_item.setForeground(Qt.gray)
            self.results_table.setItem(row, 1, channel_item)

            # Duration
            duration_item = QTableWidgetItem(item.duration_formatted)
            duration_item.setTextAlignment(Qt.AlignCenter)
            self.results_table.setItem(row, 2, duration_item)

            # Download Button Container
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 4, 4, 4)
            btn_layout.setAlignment(Qt.AlignCenter)

            dl_btn = QPushButton("⬇ Descargar")
            dl_btn.setProperty("class", "TableDownloadButton")
            dl_btn.setCursor(Qt.PointingHandCursor)
            dl_btn.setFixedHeight(36)
            dl_btn.setMinimumWidth(140)
            dl_btn.clicked.connect(lambda _, itm=item, b=dl_btn: self._on_download_clicked(itm, b))

            btn_layout.addWidget(dl_btn)
            self.results_table.setCellWidget(row, 3, btn_widget)
            self.results_table.setRowHeight(row, 58)

        self._adjust_columns()

    def set_error(self, message: str) -> None:
        """Displays error when search fails."""
        self.search_btn.setEnabled(True)
        self.search_input.setEnabled(True)
        self.status_label.setText(f"❌ Error al buscar: {message}")

    def _on_download_clicked(self, item: SearchResultItemDTO, button: QPushButton) -> None:
        """Dispatches download event and visual feedback."""
        button.setText("Añadida ✓")
        button.setEnabled(False)
        self.download_requested.emit(item)
