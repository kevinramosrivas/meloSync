"""yt-dlp adapter for YouTube search and audio stream downloading."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
from typing import Any, Optional

import yt_dlp

from src.domain.entities import AudioQuality, SearchResult
from src.domain.exceptions import DownloadException
from src.domain.services import (
    IAudioDownloaderService,
    IYouTubeSearchService,
    ProgressCallback,
)

logger = logging.getLogger(__name__)


class YtDlpAudioDownloader(IAudioDownloaderService, IYouTubeSearchService):
    """Adapter wrapping yt-dlp to implement search and audio download contracts."""

    def __init__(self, ffmpeg_location: Optional[str] = None) -> None:
        self.ffmpeg_location = ffmpeg_location

    # -------------------------------------------------------------------------
    # IYouTubeSearchService implementation
    # -------------------------------------------------------------------------
    def search(self, query: str, max_results: int = 15) -> list[SearchResult]:
        """Performs a fast flat-search on YouTube using yt-dlp."""
        query = query.strip()
        if not query:
            return []

        search_spec = f"ytsearch{max_results}:{query}"
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "ignoreerrors": True,
        }

        results: list[SearchResult] = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_spec, download=False)
                if not info or "entries" not in info:
                    return []

                for entry in info["entries"]:
                    if not entry:
                        continue
                    video_id = entry.get("id") or ""
                    title = entry.get("title") or "Unknown Title"
                    duration = int(entry.get("duration") or 0)
                    uploader = entry.get("uploader") or entry.get("channel") or ""
                    url = entry.get("url") or f"https://www.youtube.com/watch?v={video_id}"

                    # Thumbnails
                    thumbnails = entry.get("thumbnails") or []
                    thumbnail_url = thumbnails[-1].get("url") if thumbnails else f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                    results.append(
                        SearchResult(
                            youtube_id=video_id,
                            title=title,
                            duration_seconds=duration,
                            channel_name=uploader,
                            thumbnail_url=thumbnail_url,
                            url=url,
                        )
                    )
        except Exception as e:
            logger.error("YouTube search error for query '%s': %s", query, e)

        return results

    def get_info(self, url_or_id: str) -> Optional[SearchResult]:
        """Fetches metadata for a single video or URL."""
        if not (url_or_id.startswith("http://") or url_or_id.startswith("https://")):
            url = f"https://www.youtube.com/watch?v={url_or_id}"
        else:
            url = url_or_id

        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ignoreerrors": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None

                video_id = info.get("id") or ""
                title = info.get("title") or "Unknown Title"
                duration = int(info.get("duration") or 0)
                uploader = info.get("uploader") or info.get("channel") or ""
                thumbnails = info.get("thumbnails") or []
                thumbnail_url = thumbnails[-1].get("url") if thumbnails else f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                return SearchResult(
                    youtube_id=video_id,
                    title=title,
                    duration_seconds=duration,
                    channel_name=uploader,
                    thumbnail_url=thumbnail_url,
                    url=url,
                )
        except Exception as e:
            logger.error("Failed to fetch video info for '%s': %s", url_or_id, e)
            return None

    # -------------------------------------------------------------------------
    # IAudioDownloaderService implementation
    # -------------------------------------------------------------------------
    def download(
        self,
        url: str,
        output_directory: str,
        quality: AudioQuality = AudioQuality.BEST,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """Downloads the highest quality raw audio stream."""
        out_dir = Path(output_directory)
        out_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = str(out_dir / "%(id)s_raw.%(ext)s")

        downloaded_file: list[str] = []

        def ytdlp_hook(d: dict[str, Any]) -> None:
            if d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                percent = (downloaded / total * 100.0) if total > 0 else 0.0

                # Clean ANSI codes if string was returned
                speed_str = d.get("_speed_str", "").strip()
                eta_str = d.get("_eta_str", "").strip()

                if progress_callback:
                    progress_callback(percent, speed_str, eta_str)

            elif d.get("status") == "finished":
                filename = d.get("filename")
                if filename and os.path.exists(filename):
                    downloaded_file.append(filename)

        ydl_opts: dict[str, Any] = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [ytdlp_hook],
            "nocheckcertificate": True,
            "retries": 5,
        }

        if self.ffmpeg_location:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_location

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise DownloadException(url, "No se pudo extraer la información del stream.")

                # If hook captured the filename
                if downloaded_file and os.path.exists(downloaded_file[0]):
                    return downloaded_file[0]

                # Fallback to prepare_filename
                expected_filename = ydl.prepare_filename(info)
                if os.path.exists(expected_filename):
                    return expected_filename

                # Or search directory for generated raw file matching video id
                video_id = info.get("id")
                if video_id:
                    for f in out_dir.glob(f"{video_id}_raw.*"):
                        if f.is_file():
                            return str(f)

                raise DownloadException(url, "El archivo descargado no se pudo localizar en disco.")
        except Exception as e:
            if isinstance(e, DownloadException):
                raise
            raise DownloadException(url, str(e)) from e
