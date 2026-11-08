"""FFmpeg audio processor for volume normalization and silence trimming."""

from __future__ import annotations

import logging
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Callable, Optional

from ...domain.entities import AudioQuality
from ...domain.exceptions import AudioProcessingException, DownloadCancelledException
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

    @staticmethod
    def _build_codec_args(quality: AudioQuality) -> list[str]:
        """Builds LAME MP3 encoder flags according to selected audio quality."""
        bitrate_map = {
            AudioQuality.BEST: "320k",
            AudioQuality.HIGH_320K: "320k",
            AudioQuality.MID_256K: "256k",
            AudioQuality.LOW_128K: "128k",
        }
        bitrate = bitrate_map.get(quality, "320k")
        return ["-c:a", "libmp3lame", "-b:a", bitrate, "-compression_level", "0"]

    def _run_cancellable_process(
        self,
        cmd: list[str],
        startupinfo: Any,
        cancel_check: Optional[Callable[[], bool]],
        in_path: Path,
        out_path: Path,
    ) -> tuple[int, str]:
        """Runs an FFmpeg subprocess with cooperative, real-time cancellation check."""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            startupinfo=startupinfo,
        )
        while True:
            if cancel_check and cancel_check():
                try:
                    process.kill()
                    process.wait(timeout=2.0)
                except Exception:
                    pass
                try:
                    if in_path.exists():
                        in_path.unlink()
                except Exception:
                    pass
                try:
                    if out_path.exists():
                        out_path.unlink()
                except Exception:
                    pass
                raise DownloadCancelledException("Descarga cancelada por el usuario.")
            try:
                _, stderr = process.communicate(timeout=0.25)
                return process.returncode, stderr or ""
            except subprocess.TimeoutExpired:
                continue

    def normalize_and_trim(
        self,
        input_file_path: str,
        output_directory: str,
        target_loudness_lufs: float = -14.0,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        quality: AudioQuality = AudioQuality.BEST,
        trim_silence: bool = True,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> str:
        """Processes raw audio in a single pass with RMS silence trimming, EBU R128 loudnorm, and SoX resampling."""
        if cancel_check and cancel_check():
            raise DownloadCancelledException("Descarga cancelada por el usuario.")

        in_path = Path(input_file_path)
        if not in_path.exists():
            raise AudioProcessingException(f"Archivo de entrada no existe: {input_file_path}")

        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"proc_{in_path.stem}.mp3"

        if progress_callback:
            progress_callback(10.0, "Iniciando normalización y masterización en paso único (EBU R128)...")

        # Build single-pass streaming filter chain (eliminates slow double in-memory areverse pass)
        filters: list[str] = []
        if trim_silence:
            filters.append("silenceremove=start_periods=1:start_duration=0.15:start_threshold=-45dB:detection=rms")
        filters.append(f"loudnorm=I={target_loudness_lufs}:TP=-1.5:LRA=11:linear=true")
        filters.append("aresample=resampler=soxr:precision=28")
        filter_complex = ",".join(filters)

        codec_args = self._build_codec_args(quality)

        cmd = [
            self._ffmpeg_path,
            "-y",  # Overwrite output
            "-i", str(in_path),
            "-vn",  # Strip any embedded video/thumbnail stream
            "-af", filter_complex,
            *codec_args,
            str(out_path),
        ]

        logger.info("Executing single-pass ffmpeg: %s", " ".join(cmd))

        try:
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            returncode, stderr = self._run_cancellable_process(
                cmd=cmd,
                startupinfo=startupinfo,
                cancel_check=cancel_check,
                in_path=in_path,
                out_path=out_path,
            )

            if returncode != 0:
                logger.warning(
                    "FFmpeg primary filter chain failed with code %d, retrying with fallback filter without soxr: %s",
                    returncode,
                    stderr[-300:] if stderr else "",
                )
                # Fallback without soxr in case bundled ffmpeg lacks libsoxr support
                fallback_filters: list[str] = []
                if trim_silence:
                    fallback_filters.append("silenceremove=start_periods=1:start_duration=0.15:start_threshold=-45dB:detection=rms")
                fallback_filters.append(f"loudnorm=I={target_loudness_lufs}:TP=-1.5:LRA=11")
                fallback_cmd = [
                    self._ffmpeg_path,
                    "-y",
                    "-i", str(in_path),
                    "-vn",
                    "-af", ",".join(fallback_filters),
                    *codec_args,
                    str(out_path),
                ]
                fb_code, fb_stderr = self._run_cancellable_process(
                    cmd=fallback_cmd,
                    startupinfo=startupinfo,
                    cancel_check=cancel_check,
                    in_path=in_path,
                    out_path=out_path,
                )
                if fb_code != 0:
                    logger.error("FFmpeg fallback failed with code %d: %s", fb_code, fb_stderr)
                    raise AudioProcessingException(
                        f"FFmpeg falló al procesar el audio: {fb_stderr[-300:] if fb_stderr else ''}"
                    )

            if progress_callback:
                progress_callback(100.0, "Procesamiento de audio completado")

            # Remove temporary raw input file if different from output
            if in_path.resolve() != out_path.resolve() and in_path.exists():
                try:
                    in_path.unlink()
                except Exception as e:
                    logger.warning("Could not remove intermediate file %s: %s", in_path, e)

            return str(out_path)

        except DownloadCancelledException:
            raise
        except FileNotFoundError:
            raise AudioProcessingException("No se encontró el binario de 'ffmpeg' en el sistema.")
        except Exception as e:
            if isinstance(e, AudioProcessingException):
                raise
            raise AudioProcessingException(f"Error inesperado al ejecutar ffmpeg: {e}") from e
