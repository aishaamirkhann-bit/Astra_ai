import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.messaging import DirectMessage, SellerConversation

router = APIRouter()


class MessagingManager:
    """In-process fan-out keyed by conversation id (Redis upgrade path mirrors deals_ws)."""

    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def broadcast(self, conversation_id: int, event: dict[str, Any]) -> None:
        stale = []
        for socket in tuple(self.connections.get(conversation_id, ())):
            try:
                await socket.send_json(event)
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.connections[conversation_id].discard(socket)


manager = MessagingManager()


def _is_participant(user_id: int, conversation_id: int) -> bool:
    with SessionLocal() as db:
        conversation = db.get(SellerConversation, conversation_id)
        return bool(conversation and user_id in (conversation.buyer_id, conversation.seller_id))


def _persist_incoming(user_id: int, conversation_id: int, raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    content = str(payload.get("content", "")).strip()
    if not content or len(content) > 2000:
        return None
    with SessionLocal() as db:
        if db.get(SellerConversation, conversation_id) is None:
            return None
        message = DirectMessage(conversation_id=conversation_id, sender_id=user_id, content=content)
        db.add(message)
        db.query(SellerConversation).filter(SellerConversation.id == conversation_id).update(
            {"last_message_at": datetime.now(timezone.utc)}
        )
        db.commit()
        db.refresh(message)
        return {
            "type": "message",
            "id": message.id,
            "conversation_id": conversation_id,
            "sender_id": message.sender_id,
            "content": message.content,
            "created_at": message.created_at.isoformat() if message.created_at else None,
        }


@router.websocket("/ws/messages/{conversation_id}")
async def messages_socket(websocket: WebSocket, conversation_id: int):
    token = websocket.query_params.get("token") or websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    claims = decode_access_token(token) if token else None
    try:
        user_id = int(claims["sub"]) if claims else 0
    except (KeyError, TypeError, ValueError):
        user_id = 0
    if not user_id:
        await websocket.close(code=1008, reason="Valid access token required")
        return
    if not _is_participant(user_id, conversation_id):
        await websocket.close(code=1008, reason="Not a participant of this conversation")
        return

    await websocket.accept()
    manager.connections[conversation_id].add(websocket)
    await websocket.send_json({"type": "connected", "channel": f"messaging:{conversation_id}"})
    try:
        while True:
            raw = await websocket.receive_text()
            if raw == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            event = _persist_incoming(user_id, conversation_id, raw)
            if event:
                await manager.broadcast(conversation_id, event)
    except WebSocketDisconnect:
        manager.connections[conversation_id].discard(websocket)
