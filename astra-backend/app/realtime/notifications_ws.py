from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.core.config import settings

router = APIRouter()


class NotificationManager:
    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def broadcast(self, user_id: int, event: dict[str, Any]) -> None:
        stale = []
        for socket in tuple(self.connections.get(user_id, ())):
            try: await socket.send_json(event)
            except Exception: stale.append(socket)
        for socket in stale: self.connections[user_id].discard(socket)


manager = NotificationManager()


@router.websocket("/ws/notifications")
async def notifications_socket(websocket: WebSocket):
    token = websocket.query_params.get("token") or websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    claims = decode_access_token(token) if token else None
    try: user_id = int(claims["sub"]) if claims else 0
    except (KeyError, TypeError, ValueError): user_id = 0
    if not user_id:
        await websocket.close(code=1008, reason="Valid access token required"); return
    await websocket.accept(); manager.connections[user_id].add(websocket)
    await websocket.send_json({"type": "connected", "channel": "astra:notifications"})
    try:
        while True:
            if await websocket.receive_text() == "ping": await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.connections[user_id].discard(websocket)


@router.websocket("/ws/orders")
async def orders_socket(websocket: WebSocket):
    token = websocket.query_params.get("token") or websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    claims = decode_access_token(token) if token else None
    try: user_id = int(claims["sub"]) if claims else 0
    except (KeyError, TypeError, ValueError): user_id = 0
    if not user_id:
        await websocket.close(code=1008, reason="Valid access token required"); return
    await websocket.accept(); manager.connections[user_id].add(websocket)
    await websocket.send_json({"type": "connected", "channel": "astra:orders"})
    try:
        while True:
            if await websocket.receive_text() == "ping": await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.connections[user_id].discard(websocket)
