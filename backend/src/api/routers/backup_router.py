"""Backup Router: Export and Import meloSync library, playlists, and settings."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from ..dependencies import Container, get_container
from ..schemas.backup_schemas import (
    BackupPayloadSchema,
    ImportBackupOptionsRequest,
    ImportBackupRequest,
    ImportBackupResponse,
)
from ...application.dto import ImportBackupOptionsDTO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["Backup"])


@router.get("/export", response_model=BackupPayloadSchema)
def export_backup_get(
    preferences_json: Optional[str] = Query(None, description="Serialized JSON string of frontend user preferences"),
    container: Container = Depends(get_container),
) -> BackupPayloadSchema:
    """Exports entire library, custom playlists, and settings to a JSON backup bundle."""
    user_prefs: dict[str, Any] = {}
    if preferences_json:
        try:
            user_prefs = json.loads(preferences_json)
        except Exception:
            logger.warning("Could not parse preferences_json query parameter.")

    use_case = container.get_export_backup_use_case()
    dto = use_case.execute(user_preferences=user_prefs)
    return BackupPayloadSchema.from_dto(dto)


@router.post("/export", response_model=BackupPayloadSchema)
def export_backup_post(
    body: Optional[dict[str, Any]] = None,
    container: Container = Depends(get_container),
) -> BackupPayloadSchema:
    """Exports entire library with user preferences provided in request body."""
    user_prefs: dict[str, Any] = {}
    if body and "user_preferences" in body:
        user_prefs = body["user_preferences"]

    use_case = container.get_export_backup_use_case()
    dto = use_case.execute(user_preferences=user_prefs)
    return BackupPayloadSchema.from_dto(dto)


@router.post("/import", response_model=ImportBackupResponse)
async def import_backup_json(
    request: ImportBackupRequest,
    container: Container = Depends(get_container),
) -> ImportBackupResponse:
    """Restores library, playlists, and settings from a JSON payload and starts async downloads."""
    try:
        loop = asyncio.get_running_loop()
        import_uc = container.get_import_backup_use_case()
        download_uc = container.get_download_use_case()

        options_dto = ImportBackupOptionsDTO(
            download_missing_audio=request.options.download_missing_audio,
            restore_settings=request.options.restore_settings,
            restore_preferences=request.options.restore_preferences,
            overwrite_existing_metadata=request.options.overwrite_existing_metadata,
        )

        result_dto = import_uc.execute(
            backup_dict=request.backup_data.model_dump(),
            options=options_dto,
            task_executor=container.task_executor,
            download_use_case=download_uc,
            loop=loop,
            event_publisher=container.ws_manager,
        )

        return ImportBackupResponse.from_dto(result_dto)

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Error during backup import: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fallo al importar respaldo: {str(e)}")


@router.post("/import-raw", response_model=ImportBackupResponse)
async def import_backup_raw(
    request: Request,
    download_missing_audio: bool = Query(True),
    restore_settings: bool = Query(True),
    restore_preferences: bool = Query(True),
    overwrite_existing_metadata: bool = Query(False),
    container: Container = Depends(get_container),
) -> ImportBackupResponse:
    """Restores library, playlists, and settings from a raw JSON payload stream."""
    try:
        content = await request.body()
        try:
            raw_data = json.loads(content.decode("utf-8"))
        except Exception as pe:
            raise HTTPException(status_code=400, detail=f"El contenido no es un JSON válido: {str(pe)}")

        loop = asyncio.get_running_loop()
        import_uc = container.get_import_backup_use_case()
        download_uc = container.get_download_use_case()

        options_dto = ImportBackupOptionsDTO(
            download_missing_audio=download_missing_audio,
            restore_settings=restore_settings,
            restore_preferences=restore_preferences,
            overwrite_existing_metadata=overwrite_existing_metadata,
        )

        result_dto = import_uc.execute(
            backup_dict=raw_data,
            options=options_dto,
            task_executor=container.task_executor,
            download_use_case=download_uc,
            loop=loop,
            event_publisher=container.ws_manager,
        )

        return ImportBackupResponse.from_dto(result_dto)

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Error during raw backup import: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fallo al importar respaldo: {str(e)}")
