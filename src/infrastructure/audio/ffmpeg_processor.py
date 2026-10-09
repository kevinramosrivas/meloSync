"""FFmpeg audio processor for volume normalization (loudnorm) and silence trimming."""

from __future__ import annotations

from collections.abc import Callable
import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Optional

from src.domain.exceptions import AudioProcessingException
from src.domain.services import IAudioProcessorService

logger = logging.getLogger(__name__)


class FFmpegAudioProcessor(IAudioProcessorService):
    """Concrete audio processing service using system FFmpeg binary."""

    def __init__(self, ffmpeg_path: Optional[str] = None) -> None:
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"
        self._verify_ffmpeg()

    def _verify_ffmpeg(self) -> None:
        """Verifies that FFmpeg is accessible."""
        try:
            res = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                logger.warning("FFmpeg binary at '%s' returned code %d", self.ffmpeg_path, res.returncode)
            else:
                logger.info("FFmpeg binary verified successfully: %s", self.ffmpeg_path)
        except Exception as e:
            logger.error("FFmpeg not accessible at '%s': %s", self.ffmpeg_path, e)

    def normalize_and_trim(
        self,
        input_file_path: str,
        output_directory: str,
        target_loudness_lufs: float = -14.0,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> str:
        """Normalizes volume using loudnorm and trims lead/tail silence."""
        in_path = Path(input_file_path)
        if not in_path.exists():
            raise AudioProcessingException(input_file_path, "El archivo de entrada no existe.")

        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)

        output_filename = f"{in_path.stem}_processed.mp3"
        out_path = out_dir / output_filename

        if progress_callback:
            progress_callback(10.0, "Configurando filtros FFmpeg...")

        # Audio filter pipeline:
        # 1. silenceremove: Strip leading silence (< -50dB for 0.1s)
        # 2. areverse + silenceremove + areverse: Strip trailing silence (< -50dB for 0.1s)
        # 3. loudnorm: Normalize loudness to target LUFS (EBU R128 standard)
        audio_filter = (
            f"silenceremove=start_periods=1:start_duration=0.1:start_threshold=-50dB,"
            f"areverse,"
            f"silenceremove=start_periods=1:start_duration=0.1:start_threshold=-50dB,"
            f"areverse,"
            f"loudnorm=I={target_loudness_lufs:.1f}:TP=-1.5:LRA=11"
        )

        cmd = [
            self.ffmpeg_path,
            "-y",  # Overwrite output without asking
            "-i", str(in_path),
            "-af", audio_filter,
            "-c:a", "libmp3lame",
            "-b:a", "320k",
            str(out_path),
        ]

        logger.info("Executing FFmpeg command: %s", " ".join(cmd))
        if progress_callback:
            progress_callback(40.0, "Ejecutando normalización de volumen y recorte...")

        try:
            # Hide console window on Windows if subprocess spawned
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                startupinfo=startupinfo,
            )

            if process.returncode != 0:
                logger.error("FFmpeg failed with code %d. stderr: %s", process.returncode, process.stderr)
                # Fallback: try simple re-encode without complex filters if filters failed
                logger.info("Attempting fallback encoding without filters...")
                fallback_cmd = [
                    self.ffmpeg_path,
                    "-y",
                    "-i", str(in_path),
                    "-c:a", "libmp3lame",
                    "-b:a", "320k",
                    str(out_path),
                ]
                fb_res = subprocess.run(fallback_cmd, capture_output=True, text=True, check=False, startupinfo=startupinfo)
                if fb_res.returncode != 0:
                    raise AudioProcessingException(
                        input_file_path,
                        f"FFmpeg error: {process.stderr or fb_res.stderr}",
                    )

            if not out_path.exists() or out_path.stat().st_size == 0:
                raise AudioProcessingException(input_file_path, "El archivo procesado no fue generado.")

            if progress_callback:
                progress_callback(100.0, "Procesamiento de audio completado.")

            logger.info("Audio processed successfully: %s", out_path)
            return str(out_path)

        except Exception as e:
            if isinstance(e, AudioProcessingException):
                raise
            raise AudioProcessingException(input_file_path, str(e)) from e
