"""Routers module."""

from .downloads_router import router as downloads_router
from .library_router import router as library_router
from .metadata_router import router as metadata_router
from .search_router import router as search_router
from .settings_router import router as settings_router

__all__ = [
    "downloads_router",
    "library_router",
    "metadata_router",
    "search_router",
    "settings_router",
]
