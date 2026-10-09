"""Use Cases: Manage application settings (configurable download path, quality, normalization)."""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path

from ..dto import SettingsDTO, UpdateSettingsCommand
from ...domain.entities import AppSettings, utc_now
from ...domain.repositories import IUnitOfWork

logger = logging.getLogger(__name__)


class GetSettingsUseCase:
    """Retrieves current application settings."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self) -> SettingsDTO:
        with self._uow_factory() as uow:
            settings = uow.settings.get()
            return SettingsDTO.from_domain(settings)


class UpdateSettingsUseCase:
    """Updates and persists application settings."""

    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    def execute(self, command: UpdateSettingsCommand) -> SettingsDTO:
        target_dir = Path(command.music_download_directory).expanduser()
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create directory %s: %s", target_dir, e)

        with self._uow_factory() as uow:
            updated_entity = AppSettings(
                music_download_directory=str(target_dir),
                default_audio_quality=command.default_audio_quality,
                normalize_audio_lufs=command.normalize_audio_lufs,
                auto_tag_metadata=command.auto_tag_metadata,
                updated_at=utc_now(),
            )
            saved = uow.settings.update(updated_entity)
            return SettingsDTO.from_domain(saved)
