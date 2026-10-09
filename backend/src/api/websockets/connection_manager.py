"""WebSocket Connection Manager and real-time event broadcaster."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import logging
from typing import Any, Set

from fastapi import WebSocket

from ...application.events import ApplicationEvent, IEventPublisher

logger = logging.getLogger(__name__)


class WebSocketConnectionManager(IEventPublisher):
    """Thread-safe WebSocket broadcaster supporting multiple connected clients."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("WebSocket client connected. Total active: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        logger.info("WebSocket client disconnected. Remaining: %d", len(self.active_connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Asynchronously broadcasts a JSON payload to all connected clients."""
        if not self.active_connections:
            return

        payload_str = json.dumps(message)
        dead_connections: list[WebSocket] = []

        for conn in list(self.active_connections):
            try:
                await conn.send_text(payload_str)
            except Exception as e:
                logger.warning("Error sending WebSocket message: %s", e)
                dead_connections.append(conn)

        for dead in dead_connections:
            self.disconnect(dead)

    def publish(self, event: ApplicationEvent) -> None:
        """Implements IEventPublisher by scheduling broadcast onto the asyncio event loop."""
        data = event.to_dict()
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(data), self._loop)
        else:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.broadcast(data))
            except Exception:
                pass
