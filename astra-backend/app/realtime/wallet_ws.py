from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.security import decode_access_token
from app.core.config import settings


router = APIRouter()


class WalletConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        self._connections[user_id].discard(websocket)
        if not self._connections[user_id]:
            self._connections.pop(user_id, None)

    async def balance_updated(self, user_id: int, balance: float, transaction_type: str) -> None:
        event = {
            "type": "balance_updated",
            "user_id": user_id,
            "available_balance": round(balance, 2),
            "transaction_type": transaction_type,
        }
        stale: list[WebSocket] = []
        for socket in tuple(self._connections.get(user_id, ())):
            try:
                await socket.send_json(event)
            except Exception:
                stale.append(socket)
        for socket in stale:
            self.disconnect(user_id, socket)


manager = WalletConnectionManager()


@router.websocket("/ws/wallet/{user_id}")
async def wallet_socket(websocket: WebSocket, user_id: int):
    token = websocket.query_params.get("token") or websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    claims = decode_access_token(token) if token else None
    if not claims or str(claims.get("sub")) != str(user_id):
        await websocket.close(code=1008, reason="Wallet token does not match user")
        return
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
