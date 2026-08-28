"""
Starter test. Run with: pytest
Uses the dev-fallback in get_current_user (no token = seeded Aisha user),
so run `python -m app.db.seed` before running tests.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_home_page_aggregate():
    res = client.get("/api/v1/home")
    assert res.status_code == 200
    body = res.json()
    assert "recommended_products" in body
    assert "astra_check" in body
    assert "pipeline" in body
    assert "goals_wallet" in body


def test_recommended_products():
    res = client.get("/api/v1/products/recommended")
    assert res.status_code == 200
    assert len(res.json()) > 0


def test_astra_check_overall_verdict_present():
    res = client.get("/api/v1/astra-check")
    assert res.status_code == 200
    assert res.json()["overall_verdict"] in ["GOOD TO BUY", "REVIEW SUGGESTED", "NOT RECOMMENDED"]
