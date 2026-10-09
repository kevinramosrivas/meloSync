"""Sidebar navigation widget with Apple Music aesthetics."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpacerItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class SidebarWidget(QWidget):
    """Navigation sidebar on the left side of the application."""

    tab_changed = Signal(int)

    def __init__(self, music_directory: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarWidget")
        self.setFixedWidth(230)
        self.music_directory = music_directory

        self._active_index = 0
        self._nav_buttons: list[QPushButton] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 20)
        layout.setSpacing(6)

        # -------------------------------------------------------------
        # App Branding Header
        # -------------------------------------------------------------
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(10)

        logo_label = QLabel("🎵")
        logo_label.setStyleSheet("font-size: 26px; padding-left: 4px;")
        brand_layout.addWidget(logo_label)

        title_container = QVBoxLayout()
        title_container.setSpacing(1)

        app_title = QLabel("meloSync")
        app_title.setObjectName("AppTitleLabel")
        title_container.addWidget(app_title)

        app_sub = QLabel("MUSIC MANAGER")
        app_sub.setObjectName("AppSubtitleLabel")
        title_container.addWidget(app_sub)

        brand_layout.addLayout(title_container)
        brand_layout.addStretch()
        layout.addLayout(brand_layout)

        layout.addSpacing(20)

        # -------------------------------------------------------------
        # Section Label
        # -------------------------------------------------------------
        section_label = QLabel("EXPLORAR")
        section_label.setStyleSheet(
            "font-size: 11px; font-weight: 700; color: #6e6e73; padding-left: 10px; margin-bottom: 4px;"
        )
        layout.addWidget(section_label)

        # -------------------------------------------------------------
        # Navigation Items
        # -------------------------------------------------------------
        nav_items = [
            ("🔍  Buscar en YouTube", 0),
            ("📚  Biblioteca", 1),
            ("⬇️  Descargas Activas", 2),
        ]

        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setProperty("class", "SidebarNavButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=index: self.set_active_tab(idx))
            self._nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # -------------------------------------------------------------
        # Bottom Utility Actions
        # -------------------------------------------------------------
        folder_btn = QPushButton("📁 Abrir Carpeta")
        folder_btn.setProperty("class", "SecondaryButton")
        folder_btn.setCursor(Qt.PointingHandCursor)
        folder_btn.setFixedHeight(36)
        folder_btn.setToolTip("Abrir carpeta local donde se guardan las canciones")
        folder_btn.clicked.connect(self._open_music_folder)
        layout.addWidget(folder_btn)

        version_label = QLabel("v1.0.0 • Production Ready")
        version_label.setStyleSheet("font-size: 10px; color: #55555c; text-align: center; padding-top: 8px;")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        # Set initial active tab
        self.set_active_tab(0)

    def set_active_tab(self, index: int) -> None:
        """Changes active tab visually and notifies listener."""
        self._active_index = index
        for i, btn in enumerate(self._nav_buttons):
            if i == index:
                btn.setProperty("active", "true")
            else:
                btn.setProperty("active", "false")
            # Refresh stylesheet state
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.tab_changed.emit(index)

    def _open_music_folder(self) -> None:
        """Opens user's music directory in Windows Explorer / system file manager."""
        path = Path(self.music_directory)
        path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(path))
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
