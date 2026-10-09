"""Settings Router: Manage configurable application preferences."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import Container, get_container
from ..schemas import SettingsResponse, UpdateSettingsRequest
from ...application.dto import UpdateSettingsCommand

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("", response_model=SettingsResponse)
def get_settings(
    container: Container = Depends(get_container),
):
    """Retrieves current application preferences."""
    use_case = container.get_settings_use_case()
    settings = use_case.execute()
    return SettingsResponse.from_dto(settings)


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
    )
    saved = use_case.execute(command)
    return SettingsResponse.from_dto(saved)


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
