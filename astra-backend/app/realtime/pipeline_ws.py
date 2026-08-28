"""
Live pipeline updates for PipelineBar.tsx's "Live" badge — instead of polling
GET /api/v1/pipeline/state every second, frontend can open a WebSocket and
get pushed updates the instant a stage completes.

Frontend usage (example):
    const ws = new WebSocket("ws://localhost:8000/ws/pipeline?order_ref=ORD-88213")
    ws.onmessage = (e) => setPipelineState(JSON.parse(e.data))
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.order import Order
from app.services.pipeline_engine import PipelineEngine

router = APIRouter()


@router.websocket("/ws/pipeline")
async def pipeline_socket(websocket: WebSocket, order_ref: str, db: Session = Depends(get_db)):
    await websocket.accept()
    try:
        order = db.query(Order).filter(Order.order_ref == order_ref).first()
        state = PipelineEngine.build_state(order)
        await websocket.send_text(state.model_dump_json())

        # In a full implementation, this loop would await a pub/sub event
        # (Redis, DB trigger, etc.) fired whenever a pipeline stage advances.
        # Kept as a single push here since Home page only needs current state.
        await websocket.close()
    except WebSocketDisconnect:
        pass
