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

from ..dto import DownloadProgressDTO, DownloadTrackCommand, TrackDTO
from ..events import IEventPublisher
from ...domain.entities import AudioQuality, DownloadStatus, Track, TrackMetadata
from ...domain.exceptions import AudioProcessingException, DownloadCancelledException, DownloadException
from ...domain.repositories import IUnitOfWork
from ...domain.services import (
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
        event_publisher: Optional[IEventPublisher] = None,
        default_output_directory: Optional[str] = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._downloader = downloader_service
        self._processor = audio_processor
        self._metadata_provider = metadata_provider
        self._cleaner = title_cleaner
        self._tagger = tagging_service
        self._event_publisher = event_publisher
        self._default_output_dir = default_output_directory

    def execute(
        self,
        command: DownloadTrackCommand,
        progress_callback: Optional[Callable[[DownloadProgressDTO], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> TrackDTO:
        """Executes the full download, processing, tagging, and persistence pipeline."""

        def check_cancellation() -> None:
            if cancel_check and cancel_check():
                raise DownloadCancelledException("Descarga cancelada por el usuario.")

        def notify(
            track_entity: Track,
            stage: str,
            speed: str = "",
            eta: str = "",
        ) -> None:
            dto = DownloadProgressDTO(
                track_id=track_entity.id,
                youtube_id=track_entity.youtube_id,
                status=track_entity.status,
                progress_percent=track_entity.progress_percent,
                stage_description=stage,
                speed_text=speed,
                eta_text=eta,
            )
            if progress_callback:
                progress_callback(dto)
            if self._event_publisher:
                self._event_publisher.publish_progress(dto)

        # -------------------------------------------------------------
        # STEP 0: Resolve Target Directory and Settings from UoW
        # -------------------------------------------------------------
        with self._uow_factory() as uow:
            settings = uow.settings.get()
            target_output_dir = Path(
                command.custom_output_dir
                or self._default_output_dir
                or settings.music_download_directory
            )
            target_output_dir.mkdir(parents=True, exist_ok=True)
            target_loudness = settings.normalize_audio_lufs
            quality = command.custom_quality or settings.default_audio_quality
            skip_non_music = settings.skip_non_music_sections
            trim_silence = settings.trim_silence

            existing = uow.tracks.get_by_youtube_id(command.youtube_id)
            if existing:
                track = existing
                track.status = DownloadStatus.PENDIENTE
                track.progress_percent = 0.0
                track.error_message = None
                track.original_title = command.original_title
                track.duration_seconds = command.duration_seconds
                track.channel_name = command.channel_name
                track = uow.tracks.update(track)
            else:
                track = Track(
                    youtube_id=command.youtube_id,
                    url=command.url,
                    original_title=command.original_title,
                    duration_seconds=command.duration_seconds,
                    channel_name=command.channel_name,
                    status=DownloadStatus.PENDIENTE,
                )
                track = uow.tracks.add(track)

        notify(track, "Iniciando proceso de descarga...")

        raw_audio_path: Optional[str] = None
        processed_audio_path: Optional[str] = None

        try:
            # -------------------------------------------------------------
            # STEP 1: yt-dlp Download (DESCARGANDO)
            # -------------------------------------------------------------
            check_cancellation()
            track.mark_downloading()
            with self._uow_factory() as uow:
                uow.tracks.update(track)

            notify(track, "Descargando audio de YouTube...")

            def on_ytdlp_progress(percent: float, speed: str, eta: str) -> None:
                check_cancellation()
                track.update_progress(percent * 0.45)  # Scale to 0-45%
                notify(track, f"Descargando audio: {percent:.1f}%", speed=speed, eta=eta)

            download_url = command.url
            if not download_url.startswith("http") and len(command.youtube_id) == 11 and not command.youtube_id.startswith("local_"):
                download_url = f"https://www.youtube.com/watch?v={command.youtube_id}"

            if command.youtube_id.startswith("local_") or download_url.startswith("local://") or not (download_url.startswith("http://") or download_url.startswith("https://")):
                candidate_name = download_url[len("local://"):] if download_url.startswith("local://") else f"{command.original_title}.mp3"
                candidate_path = target_output_dir / candidate_name
                if candidate_path.exists() and candidate_path.is_file():
                    raw_audio_path = str(candidate_path)
                else:
                    raise DownloadException(
                        f"La pista '{command.original_title}' proviene de un archivo local y no puede descargarse de YouTube. "
                        f"Copia '{candidate_name}' en tu carpeta de música para vincularla."
                    )
            else:
                raw_audio_path = self._downloader.download(
                    url=download_url,
                    output_directory=str(target_output_dir),
                    quality=quality,
                    progress_callback=on_ytdlp_progress,
                    skip_non_music_sections=skip_non_music,
                    cancel_check=cancel_check,
                )

            # -------------------------------------------------------------
            # STEP 2: FFmpeg Audio Processing (PROCESANDO_AUDIO)
            # -------------------------------------------------------------
            check_cancellation()
            track.mark_processing_audio()
            track.update_progress(45.0)
            with self._uow_factory() as uow:
                uow.tracks.update(track)

            notify(track, "Normalizando volumen (Loudnorm -14 LUFS) y masterizando audio...")

            def on_ffmpeg_progress(percent: float, desc: str) -> None:
                check_cancellation()
                scaled = 45.0 + (percent * 0.30)  # Scale to 45-75%
                track.update_progress(scaled)
                notify(track, desc)

            try:
                processed_audio_path = self._processor.normalize_and_trim(
                    input_file_path=raw_audio_path,
                    output_directory=str(target_output_dir),
                    target_loudness_lufs=target_loudness,
                    progress_callback=on_ffmpeg_progress,
                    quality=quality,
                    trim_silence=trim_silence,
                    cancel_check=cancel_check,
                )
            except AudioProcessingException as pe:
                logger.warning("FFmpeg processing failed (%s); falling back to raw audio.", pe)
                processed_audio_path = raw_audio_path

            # -------------------------------------------------------------
            # STEP 3: Metadata Resolution (OBTENIENDO_METADATOS)
            # -------------------------------------------------------------
            check_cancellation()
            track.mark_fetching_metadata()
            track.update_progress(75.0)
            with self._uow_factory() as uow:
                uow.tracks.update(track)

            notify(track, "Consultando metadatos oficiales y carátula HD en iTunes...")

            # Use preferred metadata from backup/import if provided, skipping external iTunes queries
            if command.preferred_metadata:
                enriched_meta = command.preferred_metadata
                if not enriched_meta.cover_bytes and enriched_meta.cover_url:
                    try:
                        downloaded_cover = self._metadata_provider.download_cover_bytes(enriched_meta.cover_url)
                        if downloaded_cover:
                            enriched_meta = TrackMetadata(
                                title=enriched_meta.title,
                                artist=enriched_meta.artist,
                                album=enriched_meta.album,
                                year=enriched_meta.year,
                                genre=enriched_meta.genre,
                                track_number=enriched_meta.track_number,
                                disc_number=enriched_meta.disc_number,
                                cover_url=enriched_meta.cover_url,
                                cover_bytes=downloaded_cover,
                                lyrics=enriched_meta.lyrics,
                            )
                    except Exception as ce:
                        logger.warning("Could not load cover bytes for preferred metadata: %s", ce)
            else:
                # Clean raw title
                clean_artist, clean_title = self._cleaner.clean(command.original_title)
                query_artist = clean_artist or command.channel_name
                query_title = clean_title or command.original_title

                enriched_meta = self._metadata_provider.lookup(query=query_title, artist=query_artist)

                if not enriched_meta:
                    logger.info("iTunes search yielded no match. Using regex cleaned fallback.")
                    enriched_meta = TrackMetadata(
                        title=clean_title or command.original_title,
                        artist=clean_artist or command.channel_name or "Desconocido",
                        album="Sencillo",
                    )

            track.update_progress(88.0)
            notify(track, f"Metadatos obtenidos: {enriched_meta.artist} - {enriched_meta.title}")

            # -------------------------------------------------------------
            # STEP 4: Mutagen Tagging & File Renaming
            # -------------------------------------------------------------
            check_cancellation()
            notify(track, "Inyectando etiquetas ID3v2.4 y carátula en alta resolución...")

            final_filename = _sanitize_filename(f"{enriched_meta.artist} - {enriched_meta.title}") + ".mp3"
            final_file_path = target_output_dir / final_filename

            # Move/Rename processed file to final name
            src_path = Path(processed_audio_path)
            if src_path.exists() and src_path.resolve() != final_file_path.resolve():
                if final_file_path.exists():
                    try:
                        final_file_path.unlink()
                    except Exception:
                        pass
                src_path.rename(final_file_path)
            elif not src_path.exists() and not final_file_path.exists():
                raise DownloadException("El archivo de audio final no existe en el disco.")

            # Apply ID3 tags
            check_cancellation()
            self._tagger.apply_tags(str(final_file_path), enriched_meta)

            # -------------------------------------------------------------
            # STEP 5: Persistence & Completion (COMPLETADA)
            # -------------------------------------------------------------
            check_cancellation()
            track.mark_completed(final_file_path=str(final_file_path), metadata=enriched_meta)

            with self._uow_factory() as uow:
                updated_track = uow.tracks.update(track)

            final_dto = TrackDTO.from_domain(updated_track)
            notify(track, "¡Descarga y procesamiento completados con éxito!")
            if self._event_publisher:
                self._event_publisher.publish_track_completed(final_dto)
                self._event_publisher.publish_library_updated()

            return final_dto

        except DownloadCancelledException as ce:
            logger.info("Pipeline cancelled for track %s: %s", command.youtube_id, ce)
            for p in (raw_audio_path, processed_audio_path):
                if p:
                    try:
                        cand = Path(p)
                        if cand.exists():
                            cand.unlink()
                    except Exception:
                        pass

            with self._uow_factory() as uow:
                try:
                    existing = uow.tracks.get_by_id(track.id)
                    if existing:
                        existing.mark_cancelled("Descarga cancelada por el usuario")
                        track = uow.tracks.update(existing)
                        uow.commit()
                except Exception as ue:
                    logger.warning("Could not update track to CANCELADA in database: %s", ue)

            notify(track, "Descarga cancelada por el usuario")
            raise

        except Exception as e:
            error_msg = str(e)
            logger.error("Pipeline failed for track %s: %s", command.youtube_id, error_msg, exc_info=True)
            track.mark_error(error_msg)
            with self._uow_factory() as uow:
                try:
                    uow.tracks.update(track)
                except Exception:
                    pass
            notify(track, f"Error: {error_msg}")
            raise DownloadException(f"Fallo en la descarga: {error_msg}") from e
