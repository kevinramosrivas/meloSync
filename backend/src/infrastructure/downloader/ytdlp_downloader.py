"""yt-dlp audio downloader and search infrastructure."""

from __future__ import annotations

import logging
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Optional, cast

import yt_dlp

from ...domain.entities import AudioQuality, SearchResult
from ...domain.exceptions import DownloadException
from ...domain.services import (
    IAudioDownloaderService,
    IYouTubeSearchService,
    ProgressCallback,
)

logger = logging.getLogger(__name__)


class YtDlpAudioDownloader(IAudioDownloaderService, IYouTubeSearchService):
    """Audio downloader and YouTube search implementation using yt-dlp."""

    @staticmethod
    def _build_ydl_opts(custom_opts: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Builds robust yt-dlp options with JS runtimes, remote EJS challenge solvers, and cookies."""
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "remote_components": ["ejs:github"],
            "extractor_args": {
                "youtube": {
                    "player_client": ["mweb", "web"],
                }
            },
        }

        # Resolve ffmpeg directory for yt-dlp postprocessors (bundled PyInstaller, Tauri, or system)
        ffmpeg_dir = None
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            meipass_path = Path(sys._MEIPASS)
            if (meipass_path / "ffmpeg.exe").exists() or (meipass_path / "ffmpeg").exists():
                ffmpeg_dir = str(meipass_path)

        if not ffmpeg_dir:
            exe_dir = Path(sys.executable).parent
            for cand in [exe_dir, exe_dir / "bin"]:
                if (cand / "ffmpeg.exe").exists() or (cand / "ffmpeg").exists():
                    ffmpeg_dir = str(cand)
                    break

        if not ffmpeg_dir:
            system_ffmpeg = shutil.which("ffmpeg")
            if system_ffmpeg:
                ffmpeg_dir = str(Path(system_ffmpeg).parent)

        if ffmpeg_dir:
            opts["ffmpeg_location"] = ffmpeg_dir

        # Detect JavaScript runtime (Node.js or Deno) for YouTube signature/challenge solving
        node_path = shutil.which("node") or shutil.which("deno")
        if node_path:
            opts["js_runtimes"] = {"node": {}}

        # Check for cookies file in common locations
        cookie_candidates = [
            Path("cookies.txt"),
            Path("../cookies.txt"),
            Path.home() / ".meloSync" / "cookies.txt",
            Path.home() / "cookies.txt",
        ]
        for cand in cookie_candidates:
            if cand.exists() and cand.is_file():
                opts["cookiefile"] = str(cand.resolve())
                logger.debug("Using yt-dlp cookie file: %s", cand)
                break

        if custom_opts:
            opts.update(custom_opts)

        return opts

    def search(self, query: str, max_results: int = 15) -> list[SearchResult]:
        """Searches YouTube using ytsearch and returns clean SearchResult objects."""
        if not query or not query.strip():
            return []

        search_query = f"ytsearch{max_results}:{query.strip()}"
        ydl_opts = self._build_ydl_opts({
            "extract_flat": "in_playlist",
            "skip_download": True,
        })

        results: list[SearchResult] = []
        try:
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                info = ydl.extract_info(search_query, download=False)
                if not info or "entries" not in info:
                    return []

                for entry in info["entries"]:
                    if not entry:
                        continue
                    youtube_id = str(entry.get("id") or "")
                    title = str(entry.get("title") or "Desconocido")
                    duration = int(entry.get("duration") or 0)
                    channel = str(entry.get("uploader") or entry.get("channel") or "")
                    url = str(entry.get("url") or f"https://www.youtube.com/watch?v={youtube_id}")
                    
                    # Thumbnail
                    thumbnail_url = str(entry.get("thumbnail") or "")
                    if not thumbnail_url and youtube_id:
                        thumbnail_url = f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg"

                    results.append(
                        SearchResult(
                            youtube_id=youtube_id,
                            title=title,
                            duration_seconds=duration,
                            channel_name=channel,
                            thumbnail_url=thumbnail_url,
                            url=url,
                        )
                    )
        except Exception as e:
            logger.error("YouTube search error for query '%s': %s", query, e)
            raise DownloadException(f"Error al buscar en YouTube: {e}") from e

        return results

    def get_info(self, url_or_id: str) -> Optional[SearchResult]:
        """Fetches metadata for a single YouTube video or URL."""
        url = url_or_id
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={url_or_id}"

        ydl_opts = self._build_ydl_opts({
            "skip_download": True,
        })

        try:
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None

                youtube_id = str(info.get("id") or "")
                title = str(info.get("title") or "Desconocido")
                duration = int(info.get("duration") or 0)
                channel = str(info.get("uploader") or info.get("channel") or "")
                thumbnail_url = str(info.get("thumbnail") or f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg")

                return SearchResult(
                    youtube_id=youtube_id,
                    title=title,
                    duration_seconds=duration,
                    channel_name=channel,
                    thumbnail_url=thumbnail_url,
                    url=url,
                )
        except Exception as e:
            logger.warning("Error fetching info for %s: %s", url_or_id, e)
            return None

    def download(
        self,
        url: str,
        output_directory: str,
        quality: AudioQuality = AudioQuality.BEST,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """Downloads audio stream using yt-dlp and converts to high-quality audio."""
        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)

        downloaded_file_holder: list[str] = []

        def ytdlp_hook(d: dict[str, Any]) -> None:
            status = d.get("status")
            if status == "downloading":
                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded_bytes = d.get("downloaded_bytes") or 0
                percent = 0.0
                if total_bytes > 0:
                    percent = (downloaded_bytes / total_bytes) * 100.0
                elif "_percent_str" in d:
                    clean_pct = re.sub(r"[^\d.]", "", d["_percent_str"])
                    try:
                        percent = float(clean_pct)
                    except ValueError:
                        percent = 0.0

                speed_str = d.get("_speed_str") or ""
                eta_str = d.get("_eta_str") or ""

                if progress_callback:
                    progress_callback(percent, speed_str, eta_str)

            elif status == "finished":
                filename = d.get("filename")
                if filename:
                    downloaded_file_holder.append(filename)
                if progress_callback:
                    progress_callback(100.0, "", "")

        # Configure quality
        quality_map = {
            AudioQuality.BEST: "0",
            AudioQuality.HIGH_320K: "320",
            AudioQuality.MID_256K: "256",
            AudioQuality.LOW_128K: "128",
        }
        preferred_quality = quality_map.get(quality, "0")

        out_template = str(out_dir / "%(id)s_raw.%(ext)s")

        ydl_opts = self._build_ydl_opts({
            "format": "bestaudio/best",
            "outtmpl": out_template,
            "noplaylist": True,
            "progress_hooks": [ytdlp_hook],
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": preferred_quality,
                }
            ],
        })

        logger.info("Starting yt-dlp download for: %s", url)

        try:
            with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise DownloadException("yt-dlp no pudo extraer información del video.")

                youtube_id = str(info.get("id") or "track")
                # Expected destination after postprocessing
                expected_mp3 = out_dir / f"{youtube_id}_raw.mp3"
                if expected_mp3.exists():
                    return str(expected_mp3)

                # Check if holder captured it
                if downloaded_file_holder:
                    cand = Path(downloaded_file_holder[-1])
                    mp3_cand = cand.with_suffix(".mp3")
                    if mp3_cand.exists():
                        return str(mp3_cand)
                    if cand.exists():
                        return str(cand)

                # Fallback search in directory
                matches = list(out_dir.glob(f"{youtube_id}_raw.*"))
                if matches:
                    return str(matches[0])

                raise DownloadException("El archivo descargado no fue encontrado en el disco.")

        except Exception as e:
            if isinstance(e, DownloadException):
                raise
            logger.error("Download failed for %s: %s", url, e)
            raise DownloadException(f"Error durante la descarga de YouTube: {e}") from e
