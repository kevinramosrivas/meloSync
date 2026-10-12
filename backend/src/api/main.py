"""FastAPI Application Main Entrypoint and Lifespan Configuration."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .dependencies import get_container
from .routers import (
    downloads_router,
    library_router,
    metadata_router,
    search_router,
    settings_router,
)
from .websockets import ws_manager, ws_router

from pathlib import Path

# Setup structured logging with safe fallback for headless/windowless GUI execution
log_handlers: list[logging.Handler] = []
if sys.stdout is not None:
    log_handlers.append(logging.StreamHandler(sys.stdout))
else:
    log_dir = Path.home() / ".melosync"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_handlers.append(logging.FileHandler(str(log_dir / "melosync_backend.log"), encoding="utf-8"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger("meloSync.API")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    logger.info("Starting meloSync FastAPI Server...")
    loop = asyncio.get_running_loop()
    ws_manager.set_event_loop(loop)
    container = get_container()
    logger.info("Database and Worker thread pool initialized.")
    yield
    logger.info("Shutting down meloSync...")
    container.task_executor.shutdown()


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="meloSync API 🎵",
        description="FastAPI + WebSockets Backend for meloSync Music Manager",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Enable CORS for Angular frontend (localhost:4200, tauri://localhost, etc.)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:4200",
            "http://127.0.0.1:4200",
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "tauri://localhost",
            "https://tauri.localhost",
            "*",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount REST routers
    api_v1_prefix = "/api/v1"
    app.include_router(search_router, prefix=api_v1_prefix)
    app.include_router(downloads_router, prefix=api_v1_prefix)
    app.include_router(library_router, prefix=api_v1_prefix)
    app.include_router(metadata_router, prefix=api_v1_prefix)
    app.include_router(settings_router, prefix=api_v1_prefix)

    # Mount WebSocket router
    app.include_router(ws_router)

    @app.get("/health", tags=["Health"])
    def health_check():
        return {"status": "ok", "service": "meloSync API", "version": "2.0.0"}

    return app


app = create_app()
