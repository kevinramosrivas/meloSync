"""SQLAlchemy 2.0 Database configuration, engine and thread-safe scoped_session."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy 2.0 models."""
    pass


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """Enables SQLite Write-Ahead Logging (WAL) and busy timeout for safe concurrency."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=10000")  # 10s timeout to prevent locking errors
        cursor.close()
    except Exception as e:
        logger.debug("Failed to set SQLite PRAGMA: %s", e)


class DatabaseManager:
    """Thread-safe database manager utilizing SQLAlchemy scoped_session."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            # Default to local app directory
            app_dir = Path.home() / ".melosync"
            app_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(app_dir / "melosync.db")
        else:
            self.db_path = db_path

        db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            echo=False,
            future=True,
        )

        self._session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        self.scoped_session = scoped_session(self._session_factory)

    def init_database(self) -> None:
        """Creates all database tables defined in metadata."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database initialized successfully at: %s", self.db_path)

    def get_session(self):
        """Returns thread-local scoped session."""
        return self.scoped_session()

    def remove_session(self) -> None:
        """Cleans up thread-local session."""
        self.scoped_session.remove()
