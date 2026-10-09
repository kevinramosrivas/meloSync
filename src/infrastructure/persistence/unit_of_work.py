"""Concrete Unit of Work backed by SQLAlchemy 2.0 scoped_session."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session, scoped_session

from src.domain.repositories import IUnitOfWork
from src.infrastructure.persistence.database import DatabaseManager
from src.infrastructure.persistence.repositories import (
    SqlAlchemyPlaylistRepository,
    SqlAlchemyTrackRepository,
)

logger = logging.getLogger(__name__)


class SqlAlchemyUnitOfWork(IUnitOfWork):
    """Thread-safe Unit of Work implementation using SQLAlchemy scoped sessions."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self._db_manager = db_manager
        self._session: Optional[Session] = None
        self._tracks: Optional[SqlAlchemyTrackRepository] = None
        self._playlists: Optional[SqlAlchemyPlaylistRepository] = None

    @property
    def tracks(self) -> SqlAlchemyTrackRepository:
        if self._tracks is None:
            raise RuntimeError("UnitOfWork has not been entered. Use 'with uow:' context.")
        return self._tracks

    @property
    def playlists(self) -> SqlAlchemyPlaylistRepository:
        if self._playlists is None:
            raise RuntimeError("UnitOfWork has not been entered. Use 'with uow:' context.")
        return self._playlists

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        # Get thread-local session from scoped_session
        self._session = self._db_manager.get_session()
        self._tracks = SqlAlchemyTrackRepository(self._session)
        self._playlists = SqlAlchemyPlaylistRepository(self._session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            logger.debug("Exception detected in UnitOfWork, rolling back: %s", exc_val)
            self.rollback()
        if self._session:
            self._session.close()
            self._db_manager.remove_session()
        self._session = None
        self._tracks = None
        self._playlists = None

    def commit(self) -> None:
        if self._session:
            self._session.commit()

    def rollback(self) -> None:
        if self._session:
            self._session.rollback()
