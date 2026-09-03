def test_deal_checkout_requires_consent_and_refunds_atomically(auth_client) -> None:
    wallet_before = auth_client.get("/api/v1/wallet").json()
    deals = auth_client.get("/api/v1/deals", params={"page_size": 100}).json()["items"]
    deal = next(item for item in deals if 50000 < item["price"] < wallet_before["available_balance"] and item["stock_remaining"] > 0)
    reservation = auth_client.post(f"/api/v1/deals/{deal['id']}/reserve", json={"quantity": 1}).json()
    order_ref = reservation["order_ref"]

    blocked = auth_client.post("/api/v1/approval/approve", json={"order_ref": order_ref})
    assert blocked.status_code == 428
    assert "FINANCIAL_CONSENT_REQUIRED" in blocked.json()["detail"]

    consent = auth_client.post("/api/v1/wallet/authorize-consent", json={
        "amount": deal["price"], "auth_method": "Voice", "order_ref": order_ref,
        "voice_transcript": f"I authorize payment of Rs. {int(deal['price'])}",
    })
    assert consent.status_code == 200
    approved = auth_client.post("/api/v1/approval/approve", json={"order_ref": order_ref, "consent_id": consent.json()["consent_id"]})
    assert approved.status_code == 200
    replay = auth_client.post("/api/v1/approval/approve", json={"order_ref": order_ref, "consent_id": consent.json()["consent_id"]})
    assert replay.status_code == 409

    wallet_after = auth_client.get("/api/v1/wallet").json()
    assert wallet_after["available_balance"] == wallet_before["available_balance"] - deal["price"]
    assert wallet_after["ledger"][0]["transaction_type"] == "Debit"

    reversed_order = auth_client.post(f"/api/v1/orders/{order_ref}/reverse")
    assert reversed_order.status_code == 200
    refunded = auth_client.get("/api/v1/wallet").json()
    assert refunded["available_balance"] == wallet_before["available_balance"]
    assert refunded["ledger"][0]["transaction_type"] == "Refund"


def test_otp_consent_is_amount_bound(auth_client) -> None:
    deal = next(
        item
        for item in auth_client.get("/api/v1/deals", params={"page_size": 100}).json()["items"]
        if item["stock_remaining"] > 0
    )
    reservation = auth_client.post(f"/api/v1/deals/{deal['id']}/reserve", json={"quantity": 1}).json()
    order_ref = reservation["order_ref"]
    challenge = auth_client.post("/api/v1/wallet/authorize-consent", json={
        "amount": deal["price"], "auth_method": "OTP", "order_ref": order_ref,
    })
    assert challenge.status_code == 200
    body = challenge.json()
    invalid = auth_client.post("/api/v1/wallet/authorize-consent", json={
        "amount": deal["price"] + 1, "auth_method": "OTP", "order_ref": order_ref,
        "consent_id": body["consent_id"], "otp_code": body["dev_otp"],
    })
    assert invalid.status_code == 409
    cancelled = auth_client.post("/api/v1/approval/cancel", json={"order_ref": order_ref})
    assert cancelled.status_code == 200
