"""Metadata Edit Dialog: Search Apple Music, select track version, preview HD cover art, and save tags."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QCloseEvent, QIntValidator, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.application.dto import (
    MetadataCandidateDTO,
    TrackDTO,
    UpdateTrackMetadataCommand,
)
from src.application.use_cases.edit_metadata import (
    SearchMetadataCandidatesUseCase,
    UpdateTrackMetadataUseCase,
)
from src.domain.services import IMetadataProviderService
from src.presentation.concurrency.workers import (
    CoverDownloadWorker,
    MetadataCandidateSearchWorker,
    UpdateMetadataWorker,
)

logger = logging.getLogger(__name__)


def _create_rounded_pixmap(pixmap: QPixmap, size: int = 240, radius: int = 12) -> QPixmap:
    """Creates a high-quality antialiased rounded corner pixmap."""
    if pixmap.isNull() or size <= 0:
        return QPixmap()

    scaled = pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )

    # Crop to square if needed
    if scaled.width() != size or scaled.height() != size:
        x = max(0, (scaled.width() - size) // 2)
        y = max(0, (scaled.height() - size) // 2)
        scaled = scaled.copy(x, y, size, size)

    rounded = QPixmap(size, size)
    rounded.fill(Qt.transparent)

    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()

    return rounded


class CandidateItemWidget(QWidget):
    """Custom widget for an Apple Music candidate row in the results list."""

    def __init__(self, candidate: MetadataCandidateDTO, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.candidate = candidate
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        # Thumbnail
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(48, 48)
        self.thumb_label.setStyleSheet(
            "background-color: #26262b; border-radius: 6px; border: 1px solid rgba(255,255,255,0.08);"
        )
        self.thumb_label.setAlignment(Qt.AlignCenter)
        self.thumb_label.setText("🎵")
        layout.addWidget(self.thumb_label)

        # Info layout
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        # Title
        title_label = QLabel(self.candidate.title)
        title_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #ffffff;")
        info_layout.addWidget(title_label)

        # Artist & Album & Year
        sub_text_parts = []
        if self.candidate.artist:
            sub_text_parts.append(self.candidate.artist)
        if self.candidate.album and self.candidate.album != "Single":
            sub_text_parts.append(f"— {self.candidate.album}")
        if self.candidate.year:
            sub_text_parts.append(f"({self.candidate.year})")

        sub_label = QLabel(" ".join(sub_text_parts))
        sub_label.setStyleSheet("font-size: 11px; color: #a1a1a6;")
        info_layout.addWidget(sub_label)

        layout.addLayout(info_layout, stretch=1)

        # Genre pill badge
        if self.candidate.genre:
            genre_badge = QLabel(self.candidate.genre)
            genre_badge.setStyleSheet(
                "background-color: rgba(250, 45, 72, 0.15); color: #fa2d48; "
                "font-size: 10px; font-weight: 600; padding: 3px 8px; border-radius: 5px;"
            )
            layout.addWidget(genre_badge)

    def set_thumbnail_pixmap(self, rounded_pixmap: QPixmap) -> None:
        """Sets pre-rendered rounded thumbnail pixmap."""
        if not rounded_pixmap.isNull():
            self.thumb_label.setPixmap(rounded_pixmap)
            self.thumb_label.setText("")


class MetadataEditDialog(QDialog):
    """Modern modal dialog for searching Apple Music, previewing HD artwork, and updating audio tags."""

    metadata_saved = Signal(object)  # TrackDTO

    def __init__(
        self,
        track: TrackDTO,
        search_use_case: SearchMetadataCandidatesUseCase,
        update_use_case: UpdateTrackMetadataUseCase,
        metadata_provider: IMetadataProviderService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.track = track
        self.search_use_case = search_use_case
        self.update_use_case = update_use_case
        self.metadata_provider = metadata_provider
        self.thread_pool = QThreadPool.globalInstance()

        self._active_workers: list[QRunnable] = []
        self._current_cover_bytes: Optional[bytes] = None
        self._current_cover_url: Optional[str] = track.cover_url
        self._candidates: list[MetadataCandidateDTO] = []
        self._is_updating = False
        self._search_id = 0

        self._setup_dialog()
        self._setup_ui()
        self._populate_initial_data()

        # Automatically initiate candidate search on open
        self._on_search_clicked()

    def _start_worker(self, worker: QRunnable) -> None:
        """Keeps a strong reference to active workers to prevent premature GC."""
        self._active_workers.append(worker)
        self.thread_pool.start(worker)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Cleans up active worker references on dialog close."""
        self._active_workers.clear()
        super().closeEvent(event)

    def reject(self) -> None:
        """Cleans up active worker references on cancel."""
        self._active_workers.clear()
        super().reject()

    def _setup_dialog(self) -> None:
        self.setWindowTitle(f"Editar Metadatos — {self.track.title}")
        self.resize(920, 680)
        self.setMinimumSize(860, 600)
        self.setModal(True)
        self.setObjectName("MetadataEditDialog")

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 24, 28, 20)
        main_layout.setSpacing(16)

        # -------------------------------------------------------------
        # Header
        # -------------------------------------------------------------
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        dialog_title = QLabel("🏷️ Editar Metadatos de la Canción")
        dialog_title.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")
        header_layout.addWidget(dialog_title)

        dialog_subtitle = QLabel(
            "Busca la canción en Apple Music para auto-completar carátula y datos oficiales, o modifícalos manualmente."
        )
        dialog_subtitle.setStyleSheet("font-size: 12px; color: #86868b;")
        header_layout.addWidget(dialog_subtitle)

        main_layout.addLayout(header_layout)

        # -------------------------------------------------------------
        # Body Content (Columns: Left = Cover/File, Right = Search/Form)
        # -------------------------------------------------------------
        body_layout = QHBoxLayout()
        body_layout.setSpacing(22)

        # =============================================================
        # LEFT COLUMN: Cover Art & File Details
        # =============================================================
        left_column = QVBoxLayout()
        left_column.setSpacing(14)
        left_column.setAlignment(Qt.AlignTop)

        # Cover Container Frame
        self.cover_frame = QFrame()
        self.cover_frame.setFixedSize(260, 260)
        self.cover_frame.setStyleSheet(
            "background-color: #1a1a1e; border: 1px solid rgba(255, 255, 255, 0.08); "
            "border-radius: 14px;"
        )
        cover_frame_layout = QVBoxLayout(self.cover_frame)
        cover_frame_layout.setContentsMargins(8, 8, 8, 8)
        cover_frame_layout.setAlignment(Qt.AlignCenter)

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(240, 240)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("color: #86868b; font-size: 13px;")
        self.cover_label.setText("Sin Carátula\n(Buscando en Apple Music...)")
        cover_frame_layout.addWidget(self.cover_label)

        left_column.addWidget(self.cover_frame)

        # Cover Action Buttons
        cover_actions = QHBoxLayout()
        cover_actions.setSpacing(8)

        self.btn_load_file = QPushButton("📁 Cargar imagen")
        self.btn_load_file.setProperty("class", "SecondaryButton")
        self.btn_load_file.setCursor(Qt.PointingHandCursor)
        self.btn_load_file.setToolTip("Seleccionar una imagen JPEG/PNG de tu computadora")
        self.btn_load_file.clicked.connect(self._on_choose_custom_image)
        cover_actions.addWidget(self.btn_load_file)

        left_column.addLayout(cover_actions)

        # File Specs Card
        specs_card = QFrame()
        specs_card.setStyleSheet(
            "background-color: #161619; border: 1px solid rgba(255,255,255,0.06); "
            "border-radius: 10px; padding: 10px;"
        )
        specs_layout = QVBoxLayout(specs_card)
        specs_layout.setContentsMargins(10, 8, 10, 8)
        specs_layout.setSpacing(5)

        ext = Path(self.track.file_path).suffix.upper() if self.track.file_path else "AUDIO"
        specs_title = QLabel("Información del Archivo")
        specs_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #86868b; text-transform: uppercase;")
        specs_layout.addWidget(specs_title)

        self.lbl_file_format = QLabel(f"• Formato: {ext}")
        self.lbl_file_format.setStyleSheet("font-size: 11px; color: #aeaeb2;")
        specs_layout.addWidget(self.lbl_file_format)

        self.lbl_file_duration = QLabel(f"• Duración: {self.track.duration_formatted}")
        self.lbl_file_duration.setStyleSheet("font-size: 11px; color: #aeaeb2;")
        specs_layout.addWidget(self.lbl_file_duration)

        if self.track.file_path:
            file_name = Path(self.track.file_path).name
            self.lbl_file_name = QLabel(f"• Archivo: {file_name}")
            self.lbl_file_name.setToolTip(self.track.file_path)
            self.lbl_file_name.setStyleSheet("font-size: 11px; color: #86868b;")
            specs_layout.addWidget(self.lbl_file_name)

        left_column.addWidget(specs_card)
        left_column.addStretch()

        body_layout.addLayout(left_column)

        # =============================================================
        # RIGHT COLUMN: Apple Music Search + Form
        # =============================================================
        right_column = QVBoxLayout()
        right_column.setSpacing(12)

        # --- 1. Search in Apple Music ---
        search_group = QVBoxLayout()
        search_group.setSpacing(6)

        search_header = QLabel("Búsqueda en Apple Music")
        search_header.setStyleSheet("font-size: 13px; font-weight: 600; color: #ffffff;")
        search_group.addWidget(search_header)

        search_input_layout = QHBoxLayout()
        search_input_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Escribe canción, artista o álbum para buscar...")
        self.search_input.setText(f"{self.track.artist} {self.track.title}".strip())
        self.search_input.returnPressed.connect(self._on_search_clicked)
        search_input_layout.addWidget(self.search_input, stretch=1)

        self.btn_search = QPushButton("🔍 Buscar")
        self.btn_search.setProperty("class", "AccentButton")
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.clicked.connect(self._on_search_clicked)
        search_input_layout.addWidget(self.btn_search)

        search_group.addLayout(search_input_layout)

        # Search Results List
        self.candidate_list = QListWidget()
        self.candidate_list.setObjectName("CandidateList")
        self.candidate_list.setFixedHeight(150)
        self.candidate_list.setStyleSheet(
            "QListWidget { background-color: #17171a; border: 1px solid rgba(255,255,255,0.08); "
            "border-radius: 9px; padding: 4px; } "
            "QListWidget::item { border-radius: 7px; margin-bottom: 3px; } "
            "QListWidget::item:selected { background-color: rgba(250, 45, 72, 0.22); border: 1px solid #fa2d48; }"
        )
        self.candidate_list.itemClicked.connect(self._on_candidate_selected)
        search_group.addWidget(self.candidate_list)

        right_column.addLayout(search_group)

        # --- 2. Metadata Editable Fields ---
        form_group = QVBoxLayout()
        form_group.setSpacing(8)

        form_title = QLabel("Detalles de la Canción")
        form_title.setStyleSheet("font-size: 13px; font-weight: 600; color: #ffffff;")
        form_group.addWidget(form_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        # Row 0: Title
        grid.addWidget(QLabel("Título:"), 0, 0)
        self.txt_title = QLineEdit()
        grid.addWidget(self.txt_title, 0, 1, 1, 3)

        # Row 1: Artist
        grid.addWidget(QLabel("Artista:"), 1, 0)
        self.txt_artist = QLineEdit()
        grid.addWidget(self.txt_artist, 1, 1, 1, 3)

        # Row 2: Album
        grid.addWidget(QLabel("Álbum:"), 2, 0)
        self.txt_album = QLineEdit()
        grid.addWidget(self.txt_album, 2, 1, 1, 3)

        # Row 3: Year, Genre, Track Number
        grid.addWidget(QLabel("Año:"), 3, 0)
        self.txt_year = QLineEdit()
        self.txt_year.setValidator(QIntValidator(1900, 2099, self))
        self.txt_year.setPlaceholderText("Ej: 2024")
        grid.addWidget(self.txt_year, 3, 1)

        grid.addWidget(QLabel("Género:"), 3, 2)
        self.txt_genre = QLineEdit()
        self.txt_genre.setPlaceholderText("Ej: Pop")
        grid.addWidget(self.txt_genre, 3, 3)

        # Row 4: Track Number & Rename Option
        grid.addWidget(QLabel("N° Pista:"), 4, 0)
        self.txt_track_number = QLineEdit()
        self.txt_track_number.setValidator(QIntValidator(1, 999, self))
        self.txt_track_number.setPlaceholderText("Ej: 1")
        grid.addWidget(self.txt_track_number, 4, 1)

        self.chk_rename = QCheckBox("Renombrar archivo en disco (Artista - Título)")
        self.chk_rename.setChecked(True)
        self.chk_rename.setStyleSheet("color: #a1a1a6; font-size: 12px;")
        grid.addWidget(self.chk_rename, 4, 2, 1, 2)

        form_group.addLayout(grid)
        right_column.addLayout(form_group)

        body_layout.addLayout(right_column, stretch=1)
        main_layout.addLayout(body_layout, stretch=1)

        # -------------------------------------------------------------
        # Footer Action Buttons
        # -------------------------------------------------------------
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 8, 0, 0)
        footer_layout.setSpacing(12)

        self.status_label = QLabel("Listo para editar")
        self.status_label.setStyleSheet("color: #86868b; font-size: 12px;")
        footer_layout.addWidget(self.status_label)

        footer_layout.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setProperty("class", "SecondaryButton")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("💾 Guardar Cambios")
        self.btn_save.setProperty("class", "AccentButton")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._on_save_clicked)
        footer_layout.addWidget(self.btn_save)

        main_layout.addLayout(footer_layout)

    def _populate_initial_data(self) -> None:
        """Sets form fields from the current TrackDTO."""
        self.txt_title.setText(self.track.title)
        self.txt_artist.setText(self.track.artist)
        self.txt_album.setText(self.track.album if self.track.album != "Unknown Album" else "")

        # If track has a cover_url, load it initially
        if self.track.cover_url:
            self._download_cover_preview(self.track.cover_url)

    # -----------------------------------------------------------------
    # Apple Music Candidate Search Slots
    # -----------------------------------------------------------------
    @Slot()
    def _on_search_clicked(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            return

        self._search_id += 1

        self.status_label.setText("Buscando en Apple Music...")
        self.btn_search.setEnabled(False)
        self.candidate_list.clear()

        # Loading placeholder item
        loading_item = QListWidgetItem("Buscando canciones coincidentes...")
        loading_item.setFlags(Qt.NoItemFlags)
        self.candidate_list.addItem(loading_item)

        worker = MetadataCandidateSearchWorker(
            self.search_use_case,
            query=query,
            limit=15,
            search_id=self._search_id,
        )
        worker.signals.results_ready.connect(self._on_search_results_ready)
        worker.signals.error.connect(self._on_search_error)
        self._start_worker(worker)

    @Slot(int, list)
    def _on_search_results_ready(self, search_id: int, candidates: list[MetadataCandidateDTO]) -> None:
        if search_id != self._search_id:
            return

        self.btn_search.setEnabled(True)
        self.candidate_list.clear()
        self._candidates = candidates

        if not candidates:
            self.status_label.setText("No se encontraron resultados en Apple Music.")
            empty_item = QListWidgetItem("No se encontraron coincidencias. Puedes editar los campos manualmente.")
            empty_item.setFlags(Qt.NoItemFlags)
            self.candidate_list.addItem(empty_item)
            return

        self.status_label.setText(f"Se encontraron {len(candidates)} versiones en Apple Music.")

        for candidate in candidates:
            item = QListWidgetItem()
            widget = CandidateItemWidget(candidate)
            item.setSizeHint(widget.sizeHint())
            self.candidate_list.addItem(item)
            self.candidate_list.setItemWidget(item, widget)

            # Pre-load thumbnail if available
            if candidate.thumbnail_url:
                self._load_thumbnail_async(candidate.thumbnail_url)

        # Automatically select first candidate
        if self.candidate_list.count() > 0:
            self.candidate_list.setCurrentRow(0)
            self._on_candidate_selected(self.candidate_list.item(0))

    @Slot(int, str)
    def _on_search_error(self, search_id: int, err_msg: str) -> None:
        if search_id != self._search_id:
            return

        self.btn_search.setEnabled(True)
        self.candidate_list.clear()
        self.status_label.setText("Error al consultar Apple Music.")
        err_item = QListWidgetItem(f"Error de conexión: {err_msg}")
        err_item.setFlags(Qt.NoItemFlags)
        self.candidate_list.addItem(err_item)

    # -----------------------------------------------------------------
    # Candidate Selection & Form Auto-fill
    # -----------------------------------------------------------------
    @Slot(QListWidgetItem)
    def _on_candidate_selected(self, item: QListWidgetItem) -> None:
        row = self.candidate_list.row(item)
        if row < 0 or row >= len(self._candidates):
            return

        selected = self._candidates[row]

        # Auto-fill form fields
        self.txt_title.setText(selected.title)
        self.txt_artist.setText(selected.artist)
        self.txt_album.setText(selected.album)
        self.txt_year.setText(str(selected.year) if selected.year else "")
        self.txt_genre.setText(selected.genre or "")
        self.txt_track_number.setText(str(selected.track_number) if selected.track_number else "")

        # Download HD Cover Preview
        if selected.cover_url:
            self._current_cover_url = selected.cover_url
            self._download_cover_preview(selected.cover_url)
            self.status_label.setText(f"Seleccionado: {selected.title} — {selected.artist}")

    # -----------------------------------------------------------------
    # Cover Art Handling & Asynchronous Downloading
    # -----------------------------------------------------------------
    def _download_cover_preview(self, cover_url: str) -> None:
        """Downloads high-res artwork in background and renders into preview frame."""
        self.cover_label.setText("Descargando\ncarátula HD (1000x1000)...")
        worker = CoverDownloadWorker(self.metadata_provider, cover_url)
        worker.signals.cover_ready.connect(self._on_cover_downloaded)
        worker.signals.error.connect(self._on_cover_error)
        self._start_worker(worker)

    @Slot(str, bytes)
    def _on_cover_downloaded(self, url: str, cover_bytes: bytes) -> None:
        if url == self._current_cover_url and cover_bytes:
            self._current_cover_bytes = cover_bytes
            pixmap = QPixmap()
            if pixmap.loadFromData(cover_bytes):
                rounded = _create_rounded_pixmap(pixmap, size=240, radius=12)
                if not rounded.isNull():
                    self.cover_label.setPixmap(rounded)
                    self.cover_label.setText("")
                else:
                    self.cover_label.setText("Error al renderizar carátula")
            else:
                self.cover_label.setText("Carátula descargada\n(Formato no soportado)")

    @Slot(str, str)
    def _on_cover_error(self, url: str, err: str) -> None:
        if url == self._current_cover_url:
            self.cover_label.setText("No se pudo cargar\nla carátula")

    def _load_thumbnail_async(self, thumb_url: str) -> None:
        """Loads a list thumbnail asynchronously using a Qt slot on the main dialog."""
        worker = CoverDownloadWorker(self.metadata_provider, thumb_url)
        worker.signals.cover_ready.connect(self._on_thumbnail_downloaded)
        self._start_worker(worker)

    @Slot(str, bytes)
    def _on_thumbnail_downloaded(self, url: str, thumb_bytes: bytes) -> None:
        """Executes safely on the main GUI thread."""
        if not thumb_bytes:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(thumb_bytes):
            rounded = _create_rounded_pixmap(pixmap, size=48, radius=6)
            if rounded.isNull():
                return
            for row in range(self.candidate_list.count()):
                item = self.candidate_list.item(row)
                if item:
                    widget = self.candidate_list.itemWidget(item)
                    if isinstance(widget, CandidateItemWidget) and widget.candidate.thumbnail_url == url:
                        widget.set_thumbnail_pixmap(rounded)

    @Slot()
    def _on_choose_custom_image(self) -> None:
        """Opens file dialog for user to choose custom artwork image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Carátula",
            "",
            "Imágenes (*.jpg *.jpeg *.png *.webp)",
        )
        if not file_path or not os.path.exists(file_path):
            return

        try:
            with open(file_path, "rb") as f:
                img_bytes = f.read()

            pixmap = QPixmap()
            if pixmap.loadFromData(img_bytes):
                self._current_cover_bytes = img_bytes
                self._current_cover_url = None
                rounded = _create_rounded_pixmap(pixmap, size=240, radius=12)
                if not rounded.isNull():
                    self.cover_label.setPixmap(rounded)
                    self.cover_label.setText("")
                    self.status_label.setText(f"Carátula cargada desde: {Path(file_path).name}")
            else:
                QMessageBox.warning(self, "Error de Imagen", "El archivo seleccionado no es una imagen válida.")
        except Exception as e:
            QMessageBox.warning(self, "Error al leer imagen", f"No se pudo cargar la imagen: {e}")

    # -----------------------------------------------------------------
    # Save & Update
    # -----------------------------------------------------------------
    @Slot()
    def _on_save_clicked(self) -> None:
        """Validates form and executes update use case asynchronously."""
        if self._is_updating:
            return

        title = self.txt_title.text().strip()
        artist = self.txt_artist.text().strip()
        album = self.txt_album.text().strip() or "Unknown Album"

        if not title:
            QMessageBox.warning(self, "Campo Requerido", "El título de la canción no puede estar vacío.")
            self.txt_title.setFocus()
            return

        if not artist:
            QMessageBox.warning(self, "Campo Requerido", "El artista de la canción no puede estar vacío.")
            self.txt_artist.setFocus()
            return

        year_str = self.txt_year.text().strip()
        year = int(year_str) if year_str.isdigit() else None

        genre = self.txt_genre.text().strip() or None

        track_num_str = self.txt_track_number.text().strip()
        track_number = int(track_num_str) if track_num_str.isdigit() else None

        command = UpdateTrackMetadataCommand(
            track_id=self.track.id,
            title=title,
            artist=artist,
            album=album,
            year=year,
            genre=genre,
            track_number=track_number,
            cover_url=self._current_cover_url,
            cover_bytes=self._current_cover_bytes,
            rename_file=self.chk_rename.isChecked(),
        )

        self._is_updating = True
        self.btn_save.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.status_label.setText("Guardando metadatos y aplicando etiquetas al archivo...")

        worker = UpdateMetadataWorker(self.update_use_case, command)
        worker.signals.finished.connect(self._on_update_finished)
        worker.signals.error.connect(self._on_update_error)
        self._start_worker(worker)

    @Slot(object)
    def _on_update_finished(self, updated_track: TrackDTO) -> None:
        self._is_updating = False
        self.status_label.setText("¡Metadatos guardados exitosamente!")
        self.metadata_saved.emit(updated_track)
        self.accept()

    @Slot(str, str)
    def _on_update_error(self, track_id: str, error_msg: str) -> None:
        self._is_updating = False
        self.btn_save.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.status_label.setText(f"Error al guardar: {error_msg}")
        QMessageBox.critical(
            self,
            "Error al Guardar Metadatos",
            f"Ocurrió un error al guardar los metadatos:\n\n{error_msg}",
        )
