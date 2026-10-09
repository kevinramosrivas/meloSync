"""Unit of Work implementation wrapping SQLAlchemy transactions."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from ...domain.repositories import (
    IPlaylistRepository,
    ISettingsRepository,
    ITrackRepository,
    IUnitOfWork,
)
from .database import DatabaseManager
from .repositories import (
    SqlAlchemyPlaylistRepository,
    SqlAlchemySettingsRepository,
    SqlAlchemyTrackRepository,
)

logger = logging.getLogger(__name__)


class SqlAlchemyUnitOfWork(IUnitOfWork):
    """Scoped SQLAlchemy Unit of Work ensuring thread-safe atomic transactions."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self._db_manager = db_manager
        self._session: Optional[Session] = None
        self.tracks: ITrackRepository
        self.playlists: IPlaylistRepository
        self.settings: ISettingsRepository

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._db_manager.get_session()
        self.tracks = SqlAlchemyTrackRepository(self._session)
        self.playlists = SqlAlchemyPlaylistRepository(self._session)
        self.settings = SqlAlchemySettingsRepository(self._session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
            self._session.close()

    def commit(self) -> None:
        if self._session:
            try:
                self._session.commit()
            except Exception as e:
                logger.error("Commit failed in UnitOfWork: %s", e)
                self.rollback()
                raise

    def rollback(self) -> None:
        if self._session:
            self._session.rollback()
