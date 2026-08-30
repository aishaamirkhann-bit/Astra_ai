"""Strict-auth enforcement + new B2B adapter and audit-trail coverage."""

PROTECTED_PATHS = [
    "/api/v1/home",
    "/api/v1/orders",
    "/api/v1/orders/audit",
    "/api/v1/wallet",
    "/api/v1/chat/history",
    "/api/v1/goals/budget",
]


def test_protected_endpoints_reject_missing_token(anonymous_client) -> None:
    for path in PROTECTED_PATHS:
        response = anonymous_client.get(path)
        assert response.status_code == 401, f"{path} should require authentication"


def test_protected_endpoints_reject_invalid_token(anonymous_client) -> None:
    headers = {"Authorization": "Bearer not-a-real-token"}
    assert anonymous_client.get("/api/v1/home", headers=headers).status_code == 401
    assert anonymous_client.get("/api/v1/orders", headers=headers).status_code == 401


def test_b2b_evaluate_approves_affordable_verified_payload(auth_client) -> None:
    payload = {
        "protocol": "UCP/1.2",
        "intent": "purchase",
        "agent_id": "shopping-copilot-04",
        "item": {"sku": "SGS25U-256-BLK", "price": 120000, "currency": "PKR"},
        "buyer_context": {"wallet_balance": 400000, "active_goals": ["laptop_fund"]},
    }
    response = auth_client.post("/api/v1/b2b/evaluate", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["verdict"] == "approve"
    assert body["event_ref"].startswith("EVT-")
    assert body["checks"]


def test_b2b_evaluate_holds_unaffordable_payload(auth_client) -> None:
    payload = {
        "protocol": "UCP/1.2",
        "agent_id": "shopping-copilot-04",
        "item": {"sku": "SGS25U-256-BLK", "price": 314999, "currency": "PKR"},
        "buyer_context": {"wallet_balance": 135000},
    }
    response = auth_client.post("/api/v1/b2b/evaluate", json=payload)
    assert response.status_code == 200
    assert response.json()["verdict"] == "hold"


def test_b2b_evaluate_rejects_untrusted_agent(auth_client) -> None:
    payload = {
        "protocol": "ACP/2.0",
        "action": "checkout.request",
        "agent": {"id": "rogue-agent", "trust_tier": "unverified"},
        "order": {"total": 15000, "currency": "PKR", "reversible_window_s": 30},
    }
    response = auth_client.post("/api/v1/b2b/evaluate", json=payload)
    assert response.status_code == 200
    assert response.json()["verdict"] == "reject"


def test_b2b_evaluate_writes_audit_trail(auth_client) -> None:
    payload = {
        "protocol": "ACP/2.0",
        "agent": {"id": "astra-orchestrator", "trust_tier": "verified"},
        "order": {"total": 25000, "currency": "PKR"},
    }
    evaluated = auth_client.post("/api/v1/b2b/evaluate", json=payload)
    assert evaluated.status_code == 200
    event_ref = evaluated.json()["event_ref"]
    trail = auth_client.get("/api/v1/orders/audit")
    assert trail.status_code == 200
    assert any(entry["id"] == event_ref and entry["type"] == "consent.evaluate" for entry in trail.json())


def test_b2b_evaluate_requires_authentication(anonymous_client) -> None:
    response = anonymous_client.post("/api/v1/b2b/evaluate", json={"protocol": "UCP/1.2"})
    assert response.status_code == 401
