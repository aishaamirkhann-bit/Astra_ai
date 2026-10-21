import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.order import Order
from app.models.product import Product
from app.models.wallet import UserWallet
from app.services.whatsapp_adapter import parse_webhook_messages, verify_meta_signature


def sample_payload():
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": [
        {"from": "923001234567", "id": "wamid.text", "type": "text", "text": {"body": "Yeh suit 4000 mein milega?"}},
        {"from": "923001234567", "id": "wamid.image", "type": "image", "image": {"id": "media-image", "mime_type": "image/jpeg", "caption": "black kurta"}},
        {"from": "923001234567", "id": "wamid.voice", "type": "audio", "audio": {"id": "media-audio", "mime_type": "audio/ogg; codecs=opus", "voice": True}},
    ]}}]}]}


def signed(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_meta_webhook_verification_challenge_and_bad_token(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", "test-verification-token")
    with TestClient(app) as client:
        ok = client.get("/api/v1/webhooks/whatsapp", params={
            "hub.mode": "subscribe", "hub.verify_token": "test-verification-token", "hub.challenge": "challenge-42",
        })
        denied = client.get("/api/v1/webhooks/whatsapp", params={
            "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "challenge-42",
        })
    assert ok.status_code == 200
    assert ok.text == "challenge-42"
    assert denied.status_code == 403


def test_text_image_and_voice_payload_parsing():
    messages = parse_webhook_messages(sample_payload())
    assert [(message.kind, message.message_id) for message in messages] == [
        ("text", "wamid.text"), ("image", "wamid.image"), ("audio", "wamid.voice"),
    ]
    assert messages[0].text == "Yeh suit 4000 mein milega?"
    assert messages[1].media_id == "media-image"
    assert messages[2].mime_type.startswith("audio/ogg")


def test_signature_validation_uses_raw_body():
    body = b'{"object":"whatsapp_business_account"}'
    signature = signed(body, "app-secret")
    assert verify_meta_signature(body, signature, "app-secret")
    assert not verify_meta_signature(body + b" ", signature, "app-secret")
    assert not verify_meta_signature(body, signature, "")


def test_signed_webhook_is_discovery_only_and_read_only(monkeypatch, demo_user_id):
    from app.api.v1.endpoints import whatsapp_webhook
    from app.services.vision import VisionResult

    secret = "test-app-secret"
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", secret)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
    monkeypatch.setattr(whatsapp_webhook, "download_meta_media", lambda _media_id: (b"fake-media", "image/jpeg"))
    monkeypatch.setattr(whatsapp_webhook, "analyze_image", lambda *_args: VisionResult(labels=["black kurta"], query="black kurta", confidence=0.9, provider="test"))
    monkeypatch.setattr(whatsapp_webhook, "transcribe", lambda *_args: "blue shirt")

    with SessionLocal() as db:
        product = db.query(Product).filter(Product.listing_status == "active").first()
        wallet = db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).first()
        assert product and wallet
        product_count = db.query(Product).count()
        order_state = [(item.id, item.status.value, item.price) for item in db.query(Order).order_by(Order.id).all()]
        wallet_balance = wallet.available_balance

    body = json.dumps(sample_payload(), separators=(",", ":")).encode()
    with TestClient(app) as client:
        response = client.post("/api/v1/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": signed(body, secret)})
        denied = client.post("/api/v1/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": "sha256=bad"})
    assert response.status_code == 200, response.text
    assert response.json()["processed"] == 3
    assert all(item["advisory_only"] and not item["outbound_sent"] for item in response.json()["messages"])
    assert "ref=whatsapp" in response.json()["messages"][0]["reply"] or "matching in-stock" in response.json()["messages"][0]["reply"]
    assert denied.status_code == 401
    with SessionLocal() as db:
        assert db.query(Product).count() == product_count
        assert [(item.id, item.status.value, item.price) for item in db.query(Order).order_by(Order.id).all()] == order_state
        assert db.query(UserWallet).filter(UserWallet.user_id == demo_user_id).one().available_balance == wallet_balance
