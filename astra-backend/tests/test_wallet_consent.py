from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_high_value_checkout_requires_consent_and_refunds_atomically() -> None:
    wallet_before = client.get("/api/v1/wallet").json()
    deals = client.get("/api/v1/deals", params={"page_size": 100}).json()["items"]
    deal = next(item for item in deals if 50000 < item["price"] < wallet_before["available_balance"] and item["stock_remaining"] > 0)
    reservation = client.post(f"/api/v1/deals/{deal['id']}/reserve", json={"quantity": 1}).json()
    order_ref = reservation["order_ref"]

    blocked = client.post("/api/v1/approval/approve", json={"order_ref": order_ref})
    assert blocked.status_code == 428
    assert "FINANCIAL_CONSENT_REQUIRED" in blocked.json()["detail"]

    consent = client.post("/api/v1/wallet/authorize-consent", json={
        "amount": deal["price"], "auth_method": "Voice", "order_ref": order_ref,
        "voice_transcript": f"I authorize payment of Rs. {int(deal['price'])}",
    })
    assert consent.status_code == 200
    approved = client.post("/api/v1/approval/approve", json={"order_ref": order_ref, "consent_id": consent.json()["consent_id"]})
    assert approved.status_code == 200
    replay = client.post("/api/v1/approval/approve", json={"order_ref": order_ref, "consent_id": consent.json()["consent_id"]})
    assert replay.status_code == 400

    wallet_after = client.get("/api/v1/wallet").json()
    assert wallet_after["available_balance"] == wallet_before["available_balance"] - deal["price"]
    assert wallet_after["ledger"][0]["transaction_type"] == "Debit"

    reversed_order = client.post(f"/api/v1/orders/{order_ref}/reverse")
    assert reversed_order.status_code == 200
    refunded = client.get("/api/v1/wallet").json()
    assert refunded["available_balance"] == wallet_before["available_balance"]
    assert refunded["ledger"][0]["transaction_type"] == "Refund"


def test_otp_consent_is_amount_bound() -> None:
    challenge = client.post("/api/v1/wallet/authorize-consent", json={"amount": 51000, "auth_method": "OTP"})
    assert challenge.status_code == 200
    body = challenge.json()
    invalid = client.post("/api/v1/wallet/authorize-consent", json={
        "amount": 52000, "auth_method": "OTP", "consent_id": body["consent_id"], "otp_code": body["dev_otp"],
    })
    assert invalid.status_code == 410
