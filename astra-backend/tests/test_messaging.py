"""Seller-buyer direct messaging: REST + WebSocket coverage."""
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.messaging import DirectMessage, SellerConversation

PRODUCT_ID = "samsung-galaxy-s25-ultra"


@pytest.fixture(autouse=True)
def clean_messaging_state():
    with SessionLocal() as db:
        db.query(DirectMessage).delete()
        db.query(SellerConversation).delete()
        db.commit()
    yield


_cached_sessions: dict[str, TestClient] = {}


def _session(email: str) -> TestClient:
    if email in _cached_sessions:
        return _cached_sessions[email]
    anonymous = TestClient(app)
    challenge = anonymous.post("/api/v1/auth/login", json={"email": email, "password": "demo1234"})
    assert challenge.status_code == 200, challenge.text
    verified = anonymous.post(
        "/api/v1/auth/verify-otp",
        json={"otp_token": challenge.json()["otp_token"], "code": "123456"},
    )
    assert verified.status_code == 200, verified.text
    client = TestClient(app, headers={"Authorization": f"Bearer {verified.json()['access_token']}"})
    _cached_sessions[email] = client
    return client


def test_buyer_opens_conversation_and_seller_sees_messages() -> None:
    buyer = _session("aisha@astra.ai")
    seller = _session("seller@astra.ai")

    opened = buyer.post("/api/v1/messaging/conversations", json={"product_id": PRODUCT_ID})
    assert opened.status_code == 201, opened.text
    conversation = opened.json()
    assert conversation["other_name"] == "TechBazaar Official"
    assert conversation["product_id"] == PRODUCT_ID
    conversation_id = conversation["id"]

    # Idempotent open returns the same thread.
    reopened = buyer.post("/api/v1/messaging/conversations", json={"product_id": PRODUCT_ID})
    assert reopened.status_code == 201
    assert reopened.json()["id"] == conversation_id

    sent = buyer.post(f"/api/v1/messaging/conversations/{conversation_id}/messages", json={"content": "Is this still available?"})
    assert sent.status_code == 201, sent.text
    assert sent.json()["content"] == "Is this still available?"

    seller_threads = seller.get("/api/v1/messaging/conversations")
    assert seller_threads.status_code == 200
    thread = next(item for item in seller_threads.json() if item["id"] == conversation_id)
    assert thread["other_name"] == "Aisha"
    assert thread["last_message"] == "Is this still available?"

    history = seller.get(f"/api/v1/messaging/conversations/{conversation_id}/messages")
    assert history.status_code == 200
    assert [message["content"] for message in history.json()] == ["Is this still available?"]
    reply = seller.post(f"/api/v1/messaging/conversations/{conversation_id}/messages", json={"content": "Yes, 10 units in stock."})
    assert reply.status_code == 201
    buyer_history = buyer.get(f"/api/v1/messaging/conversations/{conversation_id}/messages")
    assert len(buyer_history.json()) == 2


def test_seller_cannot_open_conversation_on_own_listing() -> None:
    seller = _session("seller@astra.ai")
    response = seller.post("/api/v1/messaging/conversations", json={"product_id": PRODUCT_ID})
    assert response.status_code == 400


def test_non_participant_cannot_read_thread() -> None:
    buyer = _session("aisha@astra.ai")
    outsider = _session("laptophub-pk@astra.ai")
    conversation_id = buyer.post("/api/v1/messaging/conversations", json={"product_id": PRODUCT_ID}).json()["id"]
    assert outsider.get(f"/api/v1/messaging/conversations/{conversation_id}/messages").status_code == 404
    assert outsider.post(f"/api/v1/messaging/conversations/{conversation_id}/messages", json={"content": "hi"}).status_code == 404


def test_websocket_exchange_is_realtime_and_persisted() -> None:
    buyer = _session("aisha@astra.ai")
    seller = _session("seller@astra.ai")
    buyer_token = buyer.headers["Authorization"].removeprefix("Bearer ")
    seller_token = seller.headers["Authorization"].removeprefix("Bearer ")
    conversation_id = buyer.post("/api/v1/messaging/conversations", json={"product_id": PRODUCT_ID}).json()["id"]

    with seller.websocket_connect(f"/ws/messages/{conversation_id}?token={seller_token}") as seller_ws:
        assert seller_ws.receive_json()["type"] == "connected"
        buyer.post(f"/api/v1/messaging/conversations/{conversation_id}/messages", json={"content": "WS ping from buyer"})
        event = seller_ws.receive_json()
        assert event["type"] == "message"
        assert event["content"] == "WS ping from buyer"

        with buyer.websocket_connect(f"/ws/messages/{conversation_id}?token={buyer_token}") as buyer_ws:
            assert buyer_ws.receive_json()["type"] == "connected"
            seller_ws.send_json({"content": "WS reply from seller"})
            event = buyer_ws.receive_json()
            assert event["type"] == "message"
            assert event["content"] == "WS reply from seller"
            assert event["sender_id"] != buyer.get("/api/v1/auth/me").json()["id"]

    history = buyer.get(f"/api/v1/messaging/conversations/{conversation_id}/messages").json()
    contents = [message["content"] for message in history]
    assert "WS ping from buyer" in contents
    assert "WS reply from seller" in contents


def test_websocket_requires_participant_token(anonymous_client) -> None:
    buyer = _session("aisha@astra.ai")
    conversation_id = buyer.post("/api/v1/messaging/conversations", json={"product_id": PRODUCT_ID}).json()["id"]
    connected = False
    try:
        with anonymous_client.websocket_connect(f"/ws/messages/{conversation_id}"):
            connected = True
    except Exception:
        pass
    assert connected is False, "WebSocket without a token should be rejected"
