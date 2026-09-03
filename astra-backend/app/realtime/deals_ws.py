import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.security import decode_access_token
from app.core.config import settings

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, event: dict[str, Any]) -> None:
        message = json.dumps(event, default=str)
        async with self._lock:
            connections = tuple(self._connections)
        stale: list[WebSocket] = []
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            await self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/deals")
async def deals_websocket(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token") or websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    if not token or decode_access_token(token) is None:
        await websocket.close(code=1008, reason="Valid access token required")
        return
    await manager.connect(websocket)
    await websocket.send_json({"type": "connected", "channel": "astra:deals"})
    try:
        while True:
            # Client pings keep intermediary proxies from closing idle sockets.
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
