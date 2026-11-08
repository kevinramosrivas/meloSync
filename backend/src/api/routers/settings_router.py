"""Settings Router: Manage configurable application preferences."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import Container, get_container
from ..schemas import (
    ConsolidateRequest,
    ConsolidateResponse,
    SettingsResponse,
    StorageStatsResponse,
    UpdateSettingsRequest,
)
from ...application.dto import UpdateSettingsCommand
from ...domain.entities import DownloadStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])


def _format_size(size_bytes: int) -> str:
    """Formats byte counts into human-readable strings."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_backend_version() -> str:
    """Reads the backend version from environment variable with fallback to 2.1.0."""
    return os.getenv("MELOSYNC_BACKEND_VERSION", os.getenv("BACKEND_VERSION", "2.1.0"))


@router.get("", response_model=SettingsResponse)
def get_settings(
    container: Container = Depends(get_container),
):
    """Retrieves current application preferences."""
    use_case = container.get_settings_use_case()
    settings = use_case.execute()
    return SettingsResponse.from_dto(settings, backend_version=get_backend_version())


@router.put("", response_model=SettingsResponse)
def update_settings(
    body: UpdateSettingsRequest,
    container: Container = Depends(get_container),
):
    """Updates and persists application preferences."""
    use_case = container.get_update_settings_use_case()
    command = UpdateSettingsCommand(
        music_download_directory=body.music_download_directory,
        default_audio_quality=body.default_audio_quality,
        normalize_audio_lufs=body.normalize_audio_lufs,
        auto_tag_metadata=body.auto_tag_metadata,
        skip_non_music_sections=body.skip_non_music_sections,
        trim_silence=body.trim_silence,
    )
    saved = use_case.execute(command)
    return SettingsResponse.from_dto(saved, backend_version=get_backend_version())


@router.get("/storage-stats", response_model=StorageStatsResponse)
def get_storage_stats(
    container: Container = Depends(get_container),
):
    """Calculates distribution of track files across active directory, foreign directories, and missing files."""
    with container.uow_factory() as uow:
        settings = uow.settings.get()
        active_dir = Path(settings.music_download_directory).resolve()
        tracks = uow.tracks.list_by_status(DownloadStatus.COMPLETADA)

        active_count = 0
        other_count = 0
        missing_count = 0
        total_size = 0

        for track in tracks:
            if not track.file_path:
                missing_count += 1
                continue

            try:
                p = Path(track.file_path).resolve()
                if not p.is_file():
                    missing_count += 1
                    continue

                size = p.stat().st_size
                if p.parent == active_dir or p.is_relative_to(active_dir):
                    active_count += 1
                    total_size += size
                else:
                    other_count += 1
            except Exception:
                missing_count += 1

        return StorageStatsResponse(
            active_directory=str(active_dir),
            active_dir_track_count=active_count,
            other_locations_track_count=other_count,
            missing_files_count=missing_count,
            total_library_tracks=len(tracks),
            active_dir_size_bytes=total_size,
            active_dir_size_formatted=_format_size(total_size),
        )


@router.post("/browse-folder")
def browse_folder():
    """Opens native OS folder picker dialog and returns the selected path."""
    selected_path = None
    try:
        if sys.platform == "win32":
            ps_script = (
                "[System.Reflection.Assembly]::LoadWithPartialName('System.windows.forms') | Out-Null; "
                "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "$f.Description = 'Selecciona la carpeta de música para meloSync'; "
                "$f.ShowNewFolderButton = $true; "
                "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.SelectedPath }"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = res.stdout.strip()
            if out and Path(out).is_dir():
                selected_path = out
        elif sys.platform == "darwin":
            script = 'choose folder with prompt "Selecciona la carpeta de música para meloSync"'
            res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=120)
            out = res.stdout.strip().replace("alias ", "")
            if out:
                selected_path = out
        else:
            res = subprocess.run(
                ["zenity", "--file-selection", "--directory", "--title=Selecciona la carpeta de música"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = res.stdout.strip()
            if out and Path(out).is_dir():
                selected_path = out
    except Exception as e:
        logger.warning("Native folder picker cancelled or encountered error: %s", e)

    return {"path": selected_path}


@router.post("/consolidate", response_model=ConsolidateResponse)
def consolidate_library(
    body: ConsolidateRequest,
    container: Container = Depends(get_container),
):
    """Consolidates track files from multiple or legacy folders into the target/active music directory."""
    use_case = container.get_consolidate_library_use_case()
    report = use_case.execute(target_directory=body.target_directory, move_files=body.move_files)
    container.ws_manager.publish_library_updated()
    return ConsolidateResponse(
        moved_count=report.moved_count,
        already_there_count=report.already_there_count,
        missing_count=report.missing_count,
        total_tracks=report.total_tracks,
        target_directory=report.target_directory,
        message=report.message,
    )


@router.post("/open-folder")
def open_music_folder(
    container: Container = Depends(get_container),
):
    """Opens the configured music download folder in the OS explorer."""
    use_case = container.get_settings_use_case()
    settings = use_case.execute()
    folder_path = Path(settings.music_download_directory)
    folder_path.mkdir(parents=True, exist_ok=True)

    path_str = str(folder_path)
    if sys.platform == "win32":
        os.startfile(path_str)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path_str])
    else:
        subprocess.Popen(["xdg-open", path_str])

    return {"message": "Carpeta de música abierta en el explorador.", "path": path_str}

