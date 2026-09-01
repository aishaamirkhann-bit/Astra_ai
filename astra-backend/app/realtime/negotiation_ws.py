"""A2A engine: buyer agent vs seller agent negotiating live over WebSocket.

The room streams every round (buyer proposal → seller counter) together with
the agents' target parameters and a convergence progress value, then settles
the deal deterministically within MAX_ROUNDS. The settled session is
persisted through the existing NegotiationSession/NegotiationRound models.
"""
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import func

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.deal import MarketPriceHistory
from app.models.negotiation import NegotiationRound, NegotiationSession
from app.models.product import Product

router = APIRouter()

MAX_ROUNDS = 6
ROUND_PAUSE_SECONDS = 0.45


def _load_context(product_id: str) -> dict | None:
    db = SessionLocal()
    try:
        product = db.get(Product, product_id)
        if product is None:
            return None
        average = db.query(func.avg(MarketPriceHistory.price)).filter(MarketPriceHistory.product_id == product_id).scalar()
        market_average = float(average) if average else product.base_price * 1.08
        floor_pct = 0.10 + (100 - product.trust) / 200
        return {
            "product": product,
            "list_price": product.base_price,
            "market_average": round(market_average, 2),
            "floor": round(max(market_average * (1 - floor_pct), product.base_price * 0.75), 2),
        }
    finally:
        db.close()


def _persist_session(product_id: str, user_id: int, rounds: list[dict], final_price: float) -> None:
    db = SessionLocal()
    try:
        session = NegotiationSession(user_id=user_id, product_id=product_id, status="accepted", final_price=final_price)
        db.add(session)
        db.flush()
        for index, round_data in enumerate(rounds, start=1):
            db.add(NegotiationRound(
                session_id=session.id, round_number=index,
                buyer_offer=round_data["buyer"], seller_ask=round_data["seller"],
                counter_offer=round_data["seller"], status="accepted" if index == len(rounds) else "counter",
                provider="a2a", reasoning_json="[]",
            ))
        db.commit()
    finally:
        db.close()


@router.websocket("/ws/negotiation/{product_id}")
async def a2a_negotiation(websocket: WebSocket, product_id: str) -> None:
    token = websocket.query_params.get("token") or websocket.cookies.get(settings.AUTH_COOKIE_NAME)
    payload = decode_access_token(token) if token else None
    if not payload:
        await websocket.close(code=1008, reason="Valid access token required")
        return
    user_id = int(payload.get("sub", 0) or 0)

    context = await asyncio.to_thread(_load_context, product_id)
    if context is None:
        await websocket.close(code=1008, reason="Product not found")
        return

    await websocket.accept()
    product = context["product"]
    list_price = context["list_price"]
    market_average = context["market_average"]
    floor = context["floor"]

    buyer_budget = round(min(list_price * 0.93, market_average * 0.97))
    buyer_opening = round(buyer_budget * 0.95)
    seller_ask = round(list_price * 0.985)
    initial_gap = max(seller_ask - buyer_opening, 1)
    delay_threshold_ms = 900

    await websocket.send_json({
        "type": "a2a_started",
        "product_id": product_id,
        "product_name": product.title,
        "params": {
            "buyer_agent": "ASTRA-Buyer",
            "seller_agent": f"{product.seller_name} · Seller-Agent",
            "buyer_budget": buyer_budget,
            "buyer_opening_offer": buyer_opening,
            "delay_threshold_ms": delay_threshold_ms,
            "seller_ask": seller_ask,
            "seller_floor": floor,
            "market_average": market_average,
            "max_rounds": MAX_ROUNDS,
        },
    })

    buyer_offer = buyer_opening
    rounds: list[dict] = []
    final_price: float | None = None
    try:
        for round_number in range(1, MAX_ROUNDS + 1):
            gap = seller_ask - buyer_offer
            progress = round(min(max(1 - gap / initial_gap, 0), 1), 3)
            await websocket.send_json({
                "type": "buyer_offer", "round": round_number, "agent": "ASTRA-Buyer",
                "offer": buyer_offer, "progress": progress,
                "message": f"Budget capped at Rs. {buyer_budget:,}; offering Rs. {buyer_offer:,} (market avg Rs. {market_average:,.0f}).",
            })
            await asyncio.sleep(ROUND_PAUSE_SECONDS)

            if round_number >= MAX_ROUNDS or gap <= initial_gap * 0.08:
                final_price = round((buyer_offer + seller_ask) / 2 / 50) * 50
                final_price = min(max(final_price, floor), buyer_budget)
                rounds.append({"buyer": buyer_offer, "seller": seller_ask})
                break

            seller_next = round(buyer_offer + gap * 0.72 / 50) * 50
            seller_next = max(seller_next, floor)
            await websocket.send_json({
                "type": "seller_counter", "round": round_number, "agent": "Seller-Agent",
                "ask": seller_next, "progress": progress,
                "message": f"Floor protected at Rs. {floor:,}; countering at Rs. {seller_next:,}.",
            })
            rounds.append({"buyer": buyer_offer, "seller": seller_next})
            buyer_offer = min(buyer_budget, round(buyer_offer + (seller_next - buyer_offer) * 0.48 / 50) * 50)
            seller_ask = seller_next
            await asyncio.sleep(ROUND_PAUSE_SECONDS)
        else:
            final_price = round((buyer_offer + seller_ask) / 2 / 50) * 50

        await websocket.send_json({
            "type": "deal_settled", "final_price": final_price, "rounds": len(rounds),
            "list_price": list_price,
            "savings_vs_list": round(list_price - final_price, 2),
            "message": f"A2A handshake complete — deal sealed at Rs. {final_price:,} after {len(rounds)} rounds.",
        })
        await asyncio.to_thread(_persist_session, product_id, user_id, rounds, final_price)

        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        return
