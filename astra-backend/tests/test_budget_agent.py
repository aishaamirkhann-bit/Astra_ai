from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.budget import BudgetAlert, ShoppingGoal
from app.models.user import User

client = TestClient(app)


def test_budget_dashboard_returns_live_metrics() -> None:
    response = client.get("/api/v1/goals/budget")
    assert response.status_code == 200
    budget = response.json()["budget"]
    assert budget["monthly_limit"] > 0
    assert budget["available_safe_balance"] == max(budget["monthly_limit"] + budget["rollover_savings"] - budget["current_spent"], 0)


def test_create_update_and_match_verified_goal() -> None:
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "aisha@astra.ai").first()
        original_wallet = user.wallet.available_balance

    created = client.post("/api/v1/goals/create", json={
        "target_title": "Verified Tech Deal Test", "target_price": 1000000,
        "category": "Tech", "priority_level": "High", "deadline": "2027-12-31",
    })
    assert created.status_code == 201
    goal = created.json()
    updated = client.put(f"/api/v1/goals/{goal['goal_id']}/update", json={"deposit_amount": 100, "target_price": 900000})
    assert updated.status_code == 200
    assert updated.json()["saved_amount"] == 100
    assert updated.json()["target_price"] == 900000

    matches = client.get("/api/v1/goals/matched-deals")
    assert matches.status_code == 200
    goal_matches = [item for item in matches.json() if item["goal_id"] == goal["goal_id"]]
    assert goal_matches
    assert all(item["trust_score"] >= 75 for item in goal_matches)
    assert all(item["listing_price"] <= item["target_price"] for item in goal_matches)

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "aisha@astra.ai").first()
        user.wallet.available_balance = original_wallet
        db.query(BudgetAlert).filter(BudgetAlert.goal_id == goal["goal_id"]).delete()
        db.query(ShoppingGoal).filter(ShoppingGoal.goal_id == goal["goal_id"]).delete()
        db.commit()


def test_budget_guardrail_creates_warning_and_installment() -> None:
    original = client.get("/api/v1/goals/budget").json()["budget"]
    created = client.post("/api/v1/goals/create", json={
        "target_title": "Guardrail Test", "target_price": 1000000,
        "category": "Tech", "priority_level": "Medium",
    }).json()
    client.put("/api/v1/goals/budget", json={"monthly_limit": 1000, "current_spent": 900})
    matches = client.get("/api/v1/goals/matched-deals").json()
    warnings = [item for item in matches if item["goal_id"] == created["goal_id"]]
    assert warnings
    assert all(item["alert_type"] == "Budget_Warning" for item in warnings)
    assert all(item["suggested_installment"] is not None for item in warnings)

    client.put("/api/v1/goals/budget", json={
        "monthly_limit": original["monthly_limit"], "current_spent": original["current_spent"],
        "rollover_savings": original["rollover_savings"],
    })
    with SessionLocal() as db:
        db.query(BudgetAlert).filter(BudgetAlert.goal_id == created["goal_id"]).delete()
        db.query(ShoppingGoal).filter(ShoppingGoal.goal_id == created["goal_id"]).delete()
        db.commit()


def test_repeated_match_scan_deduplicates_alerts() -> None:
    first = client.get("/api/v1/goals/matched-deals")
    second = client.get("/api/v1/goals/matched-deals")
    assert first.status_code == second.status_code == 200
    with SessionLocal() as db:
        alerts = db.query(BudgetAlert).all()
        keys = {(item.user_id, item.goal_id, item.deal_id, item.alert_type) for item in alerts}
        assert len(keys) == len(alerts)
