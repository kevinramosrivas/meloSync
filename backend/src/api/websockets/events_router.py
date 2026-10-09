"""WebSocket router endpoint for real-time streaming of application events."""

from __future__ import annotations

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .connection_manager import WebSocketConnectionManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSockets"])
ws_manager = WebSocketConnectionManager()


@router.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket gateway emitting real-time download and library updates."""
    await ws_manager.connect(websocket)
    # Send initial welcome / handshake
    await websocket.send_json({
        "event": "connected",
        "data": {"message": "meloSync WebSocket gateway established."},
    })
    try:
        while True:
            # Keep-alive loop & receive optional client heartbeats / ping
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning("WebSocket exception: %s", e)
        ws_manager.disconnect(websocket)
