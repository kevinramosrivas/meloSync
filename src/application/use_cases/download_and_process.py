"""Use Case: Download and Process Track Pipeline.

Orchestrates the 5-step audio workflow with state-machine safety:
1. PENDIENTE -> Download raw audio via yt-dlp (DESCARGANDO)
2. Audio processing via ffmpeg (loudnorm + silenceremove) (PROCESANDO_AUDIO)
3. Fetch metadata from iTunes Search API with Regex fallback (OBTENIENDO_METADATOS)
4. Embed tags and 1000x1000 cover art via mutagen
5. Persist final state in SQLite via Unit of Work (COMPLETADA)
"""

from __future__ import annotations

from collections.abc import Callable
import logging
import os
from pathlib import Path
import re
from typing import Optional

from src.application.dto import DownloadProgressDTO, DownloadTrackCommand, TrackDTO
from src.domain.entities import DownloadStatus, Track, TrackMetadata
from src.domain.exceptions import AudioProcessingException, DownloadException
from src.domain.repositories import IUnitOfWork
from src.domain.services import (
    IAudioDownloaderService,
    IAudioProcessorService,
    IMetadataProviderService,
    ITaggingService,
    ITitleCleanerService,
)

logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    """Removes invalid filesystem characters for Windows/POSIX."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    return clean.strip() or "track"


class DownloadAndProcessTrackUseCase:
    """Application service coordinating the audio download and enrichment pipeline."""

    def __init__(
        self,
        uow_factory: Callable[[], IUnitOfWork],
        downloader_service: IAudioDownloaderService,
        audio_processor: IAudioProcessorService,
        metadata_provider: IMetadataProviderService,
        title_cleaner: ITitleCleanerService,
        tagging_service: ITaggingService,
        output_directory: str,
    ) -> None:
        self._uow_factory = uow_factory
        self._downloader = downloader_service
        self._processor = audio_processor
        self._metadata_provider = metadata_provider
        self._cleaner = title_cleaner
        self._tagger = tagging_service
        self._output_dir = Path(output_directory)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        command: DownloadTrackCommand,
        progress_callback: Optional[Callable[[DownloadProgressDTO], None]] = None,
    ) -> TrackDTO:
        """Executes the full download, processing, tagging, and persistence pipeline."""

        def notify(
            track_entity: Track,
            stage: str,
            speed: str = "",
            eta: str = "",
        ) -> None:
            if progress_callback:
                dto = DownloadProgressDTO(
                    track_id=track_entity.id,
                    youtube_id=track_entity.youtube_id,
                    status=track_entity.status,
                    progress_percent=track_entity.progress_percent,
                    stage_description=stage,
                    speed_text=speed,
                    eta_text=eta,
                )
                progress_callback(dto)

        # -------------------------------------------------------------
        # STEP 0: Initial State & Registration in Unit of Work
        # -------------------------------------------------------------
        with self._uow_factory() as uow:
            existing = uow.tracks.get_by_youtube_id(command.youtube_id)
            if existing:
                track = existing
                track.status = DownloadStatus.PENDIENTE
                track.progress_percent = 0.0
                track.error_message = None
                track.original_title = command.original_title
                track.duration_seconds = command.duration_seconds
                track.channel_name = command.channel_name
                uow.tracks.update(track)
            else:
                track = Track(
                    youtube_id=command.youtube_id,
                    url=command.url,
                    original_title=command.original_title,
                    duration_seconds=command.duration_seconds,
                    channel_name=command.channel_name,
                    status=DownloadStatus.PENDIENTE,
                )
                uow.tracks.add(track)
            uow.commit()

        notify(track, "Iniciando descarga...")

        raw_download_path: Optional[str] = None
        processed_path: Optional[str] = None

        try:
            # ---------------------------------------------------------
            # STEP 1: DOWNLOADING (yt-dlp)
            # ---------------------------------------------------------
            with self._uow_factory() as uow:
                t = uow.tracks.get_by_id(track.id)
                if t:
                    t.mark_downloading()
                    uow.tracks.update(t)
                    track = t
                uow.commit()

            notify(track, "Descargando stream de audio desde YouTube...")

            def on_download_progress(percent: float, speed: str, eta: str) -> None:
                track.update_progress(percent * 0.45)  # Descarga representa el 0-45% del proceso total
                notify(track, f"Descargando audio ({percent:.1f}%)", speed=speed, eta=eta)

            staging_dir = self._output_dir / "temp"
            staging_dir.mkdir(parents=True, exist_ok=True)

            raw_download_path = self._downloader.download(
                url=command.url,
                output_directory=str(staging_dir),
                quality=command.quality,
                progress_callback=on_download_progress,
            )

            if not raw_download_path or not os.path.exists(raw_download_path):
                raise DownloadException(command.url, "El archivo descargado no existe en disco.")

            # ---------------------------------------------------------
            # STEP 2: AUDIO PROCESSING (FFmpeg loudnorm & silenceremove)
            # ---------------------------------------------------------
            with self._uow_factory() as uow:
                t = uow.tracks.get_by_id(track.id)
                if t:
                    t.mark_processing_audio()
                    t.update_progress(50.0)
                    uow.tracks.update(t)
                    track = t
                uow.commit()

            notify(track, "Normalizando volumen (loudnorm) y recortando silencios...")

            def on_proc_progress(percent: float, msg: str) -> None:
                calc_percent = 50.0 + (percent * 0.25)  # Procesamiento representa 50-75%
                track.update_progress(calc_percent)
                notify(track, msg)

            processed_path = self._processor.normalize_and_trim(
                input_file_path=raw_download_path,
                output_directory=str(self._output_dir),
                target_loudness_lufs=-14.0,
                progress_callback=on_proc_progress,
            )

            # Cleanup raw temp file if different
            if raw_download_path and raw_download_path != processed_path and os.path.exists(raw_download_path):
                try:
                    os.remove(raw_download_path)
                except OSError as e:
                    logger.warning("Could not delete temporary raw audio file: %s", e)

            # ---------------------------------------------------------
            # STEP 3: METADATA ENRICHMENT (iTunes API + Regex Fallback)
            # ---------------------------------------------------------
            with self._uow_factory() as uow:
                t = uow.tracks.get_by_id(track.id)
                if t:
                    t.mark_fetching_metadata()
                    t.update_progress(75.0)
                    uow.tracks.update(t)
                    track = t
                uow.commit()

            notify(track, "Consultando metadatos oficiales y carátula 1000x1000...")

            # Regex clean YouTube title as baseline
            clean_artist, clean_title = self._cleaner.clean(command.original_title)
            if command.custom_artist:
                clean_artist = command.custom_artist
            if command.custom_title:
                clean_title = command.custom_title

            logger.info("Cleaned baseline: Artist='%s', Title='%s'", clean_artist, clean_title)

            metadata: Optional[TrackMetadata] = None
            try:
                search_term = f"{clean_artist} {clean_title}".strip() if clean_artist else clean_title
                metadata = self._metadata_provider.lookup(query=search_term, artist=clean_artist or None)
            except Exception as meta_err:
                logger.warning("iTunes metadata lookup failed, falling back to clean regex: %s", meta_err)

            # Fallback if iTunes returned nothing
            if not metadata:
                logger.info("Using regex fallback metadata for track: %s", clean_title)
                metadata = TrackMetadata(
                    title=clean_title or command.original_title,
                    artist=clean_artist or command.channel_name or "Artista Desconocido",
                    album="Single",
                )

            # ---------------------------------------------------------
            # STEP 4: EMBED TAGS & COVER ART (mutagen)
            # ---------------------------------------------------------
            track.update_progress(85.0)
            notify(track, "Inyectando metadatos ID3 y carátula...")

            self._tagger.apply_tags(audio_file_path=processed_path, metadata=metadata)

            # Rename file to standard format: "Artist - Title.ext"
            ext = Path(processed_path).suffix
            safe_artist = _sanitize_filename(metadata.artist)
            safe_title = _sanitize_filename(metadata.title)
            final_filename = f"{safe_artist} - {safe_title}{ext}"
            final_path = self._output_dir / final_filename

            # If a file with the same name exists, add unique suffix
            counter = 1
            while final_path.exists() and str(final_path) != str(Path(processed_path).resolve()):
                final_path = self._output_dir / f"{safe_artist} - {safe_title} ({counter}){ext}"
                counter += 1

            if Path(processed_path).resolve() != final_path.resolve():
                try:
                    os.replace(processed_path, final_path)
                    processed_path = str(final_path)
                except OSError as e:
                    logger.warning("Could not rename to standard format: %s", e)

            # ---------------------------------------------------------
            # STEP 5: COMPLETION & PERSISTENCE
            # ---------------------------------------------------------
            with self._uow_factory() as uow:
                t = uow.tracks.get_by_id(track.id)
                if t:
                    t.mark_completed(final_file_path=str(processed_path), metadata=metadata)
                    uow.tracks.update(t)
                    track = t
                uow.commit()

            notify(track, "Descarga y procesamiento completados")
            logger.info("Track pipeline completed successfully: %s", track.display_title)
            return TrackDTO.from_entity(track)

        except Exception as exc:
            logger.exception("Error during track pipeline execution for %s: %s", command.youtube_id, exc)
            with self._uow_factory() as uow:
                t = uow.tracks.get_by_id(track.id)
                if t:
                    t.mark_error(str(exc))
                    uow.tracks.update(t)
                    track = t
                uow.commit()

            notify(track, f"Error: {exc}")
            raise
