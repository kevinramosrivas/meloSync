"""meloSync - Main Application Entrypoint & Composition Root.

Wires dependencies according to Clean Architecture and launches the PySide6 UI.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from src.application.use_cases import (
    DeleteTrackUseCase,
    DownloadAndProcessTrackUseCase,
    GetLibraryTracksUseCase,
    GetTrackByIdUseCase,
    SearchMetadataCandidatesUseCase,
    SearchYouTubeUseCase,
    UpdateTrackMetadataUseCase,
)
from src.infrastructure.audio import FFmpegAudioProcessor, MutagenTaggingService
from src.infrastructure.downloader import YtDlpAudioDownloader
from src.infrastructure.metadata import ITunesMetadataProvider, RegexTitleCleaner
from src.infrastructure.persistence import DatabaseManager, SqlAlchemyUnitOfWork
from src.presentation.styles import load_stylesheet
from src.presentation.views import MainWindow

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("meloSync")


def _get_default_music_dir() -> Path:
    """Finds or creates a writable default music directory."""
    candidates = [
        Path.home() / "Music" / "meloSync",
        Path.home() / "Música" / "meloSync",
        Path.home() / "meloSync_Music",
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            continue
    fallback = Path.home() / "meloSync_Music"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def build_application() -> tuple[QApplication, MainWindow]:
    """Composition Root: Instantiates infrastructure, use cases and UI."""
    # 1. Establish User Paths
    home_dir = Path.home()
    app_data_dir = home_dir / ".melosync"
    app_data_dir.mkdir(parents=True, exist_ok=True)

    music_dir = _get_default_music_dir()

    db_path = str(app_data_dir / "melosync.db")
    logger.info("Initializing meloSync with DB at '%s' and Music at '%s'", db_path, music_dir)

    # 2. Infrastructure Setup
    db_manager = DatabaseManager(db_path=db_path)
    db_manager.init_database()

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(db_manager)

    downloader = YtDlpAudioDownloader()
    audio_processor = FFmpegAudioProcessor()
    metadata_provider = ITunesMetadataProvider()
    title_cleaner = RegexTitleCleaner()
    tagging_service = MutagenTaggingService()

    # 3. Application Layer (Use Cases)
    search_use_case = SearchYouTubeUseCase(search_service=downloader)
    download_use_case = DownloadAndProcessTrackUseCase(
        uow_factory=uow_factory,
        downloader_service=downloader,
        audio_processor=audio_processor,
        metadata_provider=metadata_provider,
        title_cleaner=title_cleaner,
        tagging_service=tagging_service,
        output_directory=str(music_dir),
    )
    get_library_use_case = GetLibraryTracksUseCase(uow_factory=uow_factory)
    delete_track_use_case = DeleteTrackUseCase(uow_factory=uow_factory)
    get_track_by_id_use_case = GetTrackByIdUseCase(uow_factory=uow_factory)
    search_metadata_use_case = SearchMetadataCandidatesUseCase(metadata_provider=metadata_provider)
    update_metadata_use_case = UpdateTrackMetadataUseCase(
        uow_factory=uow_factory,
        metadata_provider=metadata_provider,
        tagging_service=tagging_service,
    )

    # 4. Presentation (PySide6)
    # Configure native Qt 6 High-DPI scaling policy
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # Set default system font
    app_font = QFont("Segoe UI", 10)
    app_font.setStyleHint(QFont.SansSerif)
    app.setFont(app_font)

    app.setApplicationName("meloSync")
    app.setApplicationDisplayName("meloSync — Gestor Inteligente de Música")

    # Load Apple Music Dark Stylesheet
    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    # Assemble MainWindow
    main_window = MainWindow(
        uow_factory=uow_factory,
        search_use_case=search_use_case,
        download_use_case=download_use_case,
        get_library_use_case=get_library_use_case,
        delete_track_use_case=delete_track_use_case,
        get_track_by_id_use_case=get_track_by_id_use_case,
        search_metadata_use_case=search_metadata_use_case,
        update_metadata_use_case=update_metadata_use_case,
        metadata_provider=metadata_provider,
        music_directory=str(music_dir),
    )

    return app, main_window


def main() -> None:
    """Application entrypoint."""
    app, window = build_application()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
