"""FFmpeg audio processor for volume normalization and silence trimming."""

from __future__ import annotations

import logging
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Callable, Optional

from ...domain.exceptions import AudioProcessingException
from ...domain.services import IAudioProcessorService

logger = logging.getLogger(__name__)


class FFmpegAudioProcessor(IAudioProcessorService):
    """Encapsulates ffmpeg process execution to normalize audio (EBU R128 loudnorm) and trim silence."""

    def __init__(self, ffmpeg_path: Optional[str] = None) -> None:
        self._ffmpeg_path = ffmpeg_path or self._resolve_ffmpeg_binary()

    @staticmethod
    def _resolve_ffmpeg_binary() -> str:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            meipass_path = Path(sys._MEIPASS)
            cand = meipass_path / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
            if cand.exists():
                return str(cand)

        exe_dir = Path(sys.executable).parent
        for cand in [exe_dir / "ffmpeg.exe", exe_dir / "bin" / "ffmpeg.exe", exe_dir / "ffmpeg"]:
            if cand.exists():
                return str(cand)

        return shutil.which("ffmpeg") or "ffmpeg"

    def normalize_and_trim(
        self,
        input_file_path: str,
        output_directory: str,
        target_loudness_lufs: float = -14.0,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> str:
        """Processes audio with loudnorm filter and silence trimming."""
        in_path = Path(input_file_path)
        if not in_path.exists():
            raise AudioProcessingException(f"Archivo de entrada no existe: {input_file_path}")

        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"proc_{in_path.stem}.mp3"

        if progress_callback:
            progress_callback(10.0, "Iniciando normalización de audio (EBU R128)...")

        # Complex audio filter: silenceremove + loudnorm + silenceremove at end
        # silenceremove: stop_periods=-1:stop_duration=1:stop_threshold=-50dB:detection=peak
        filter_complex = (
            f"silenceremove=start_periods=1:start_duration=0.1:start_threshold=-50dB,"
            f"loudnorm=I={target_loudness_lufs}:TP=-1.5:LRA=11,"
            f"areverse,silenceremove=start_periods=1:start_duration=0.1:start_threshold=-50dB,areverse"
        )

        cmd = [
            self._ffmpeg_path,
            "-y",  # Overwrite output
            "-i", str(in_path),
            "-af", filter_complex,
            "-c:a", "libmp3lame",
            "-b:a", "320k",
            str(out_path),
        ]

        logger.info("Executing ffmpeg: %s", " ".join(cmd))

        try:
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                startupinfo=startupinfo,
            )
            _, stderr = process.communicate()

            if process.returncode != 0:
                logger.error("FFmpeg failed with code %d: %s", process.returncode, stderr)
                # Fallback: simple copy if loudnorm filter failed
                raise AudioProcessingException(f"FFmpeg falló al procesar el audio: {stderr[-300:] if stderr else ''}")

            if progress_callback:
                progress_callback(100.0, "Procesamiento de audio completado")

            # Remove temporary raw input file if different from output
            if in_path.resolve() != out_path.resolve() and in_path.exists():
                try:
                    in_path.unlink()
                except Exception as e:
                    logger.warning("Could not remove intermediate file %s: %s", in_path, e)

            return str(out_path)

        except FileNotFoundError:
            raise AudioProcessingException("No se encontró el binario de 'ffmpeg' en el sistema.")
        except Exception as e:
            if isinstance(e, AudioProcessingException):
                raise
            raise AudioProcessingException(f"Error inesperado al ejecutar ffmpeg: {e}") from e
