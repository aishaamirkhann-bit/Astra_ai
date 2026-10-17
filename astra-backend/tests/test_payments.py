"""Payment rails: method discovery, unconfigured degradation, idempotent webhook settlement."""
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

import app.services.payment_gateway as payment_gateway
from app.core.database import SessionLocal
from app.main import app
from app.models.payment import CardTopUp
from app.models.user import User
from app.models.wallet import UserWallet


def test_methods_wallet_only_when_stripe_unconfigured() -> None:
    with TestClient(app) as client:
        body = client.get("/api/v1/payments/methods").json()
    assert body["methods"] == ["wallet"]
    assert body["stripe_publishable_key"] is None


def test_card_topup_503_without_stripe(auth_token: str) -> None:
    with TestClient(app, headers={"Authorization": f"Bearer {auth_token}"}) as client:
        response = client.post("/api/v1/payments/card/topup", json={"amount": 5000})
    assert response.status_code == 503


def test_configured_card_topup_returns_mocked_payment_intent(auth_client, monkeypatch) -> None:
    calls: list[dict] = []
    intent_id = f"pi_topup_{uuid4().hex}"

    class MockPaymentIntents:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(id=intent_id, client_secret="pi_secret_mock")

    monkeypatch.setattr(payment_gateway, "stripe_configured", lambda: True)
    monkeypatch.setattr(
        payment_gateway,
        "_client",
        lambda: SimpleNamespace(payment_intents=MockPaymentIntents()),
    )
    response = auth_client.post("/api/v1/payments/card/topup", json={"amount": 2500})
    assert response.status_code == 200, response.text
    assert response.json() == {
        "intent_id": intent_id,
        "client_secret": "pi_secret_mock",
        "amount": 2500.0,
        "currency": "pkr",
    }
    assert calls[0]["amount"] == 250_000
    assert calls[0]["currency"] == "pkr"
    with SessionLocal() as db:
        topup = db.get(CardTopUp, intent_id)
        assert topup is not None and topup.status == "requires_payment"
        db.delete(topup)
        db.commit()


def test_webhook_settles_topup_exactly_once(auth_token: str, monkeypatch) -> None:
    monkeypatch.setattr(payment_gateway, "stripe_configured", lambda: True)
    intent_id = "pi_test_settle_once"
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "aisha@astra.ai").one()
        user_id = user.id
        wallet = db.query(UserWallet).filter(UserWallet.user_id == user_id).one()
        balance_before = wallet.available_balance
        if db.get(CardTopUp, intent_id) is None:
            db.add(CardTopUp(intent_id=intent_id, user_id=user_id, amount=2500.0))
            db.commit()

    fake_event = {"type": "payment_intent.succeeded", "data": {"object": {"id": intent_id}}}
    monkeypatch.setattr(payment_gateway, "construct_webhook_event", lambda body, sig: fake_event)

    with TestClient(app) as client:
        first = client.post("/api/v1/payments/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})
        second = client.post("/api/v1/payments/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})
    assert first.status_code == 200 and second.status_code == 200

    with SessionLocal() as db:
        wallet = db.query(UserWallet).filter(UserWallet.user_id == user_id).one()
        topup = db.get(CardTopUp, intent_id)
        credits = [t for t in wallet.ledger_entries if intent_id in t.description]
        settled_balance = wallet.available_balance
        status, settled_at = topup.status, topup.settled_at
        db.delete(topup)
        wallet.available_balance = balance_before
        for txn in credits:
            db.delete(txn)
        db.commit()

    assert status == "succeeded" and settled_at is not None
    assert len(credits) == 1
    assert settled_balance == balance_before + 2500.0
