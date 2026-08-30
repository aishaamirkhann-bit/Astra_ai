"""
Starter test. Run with: pytest
Protected endpoints require a valid JWT, so tests use the `auth_client`
fixture (real token for the seeded user). Run `python -m app.db.seed`
before running tests.
"""


def test_health_check(anonymous_client):
    res = anonymous_client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_home_page_aggregate(auth_client):
    res = auth_client.get("/api/v1/home")
    assert res.status_code == 200
    body = res.json()
    assert "recommended_products" in body
    assert "astra_check" in body
    assert "pipeline" in body
    assert "goals_wallet" in body


def test_recommended_products(auth_client):
    res = auth_client.get("/api/v1/products/recommended")
    assert res.status_code == 200
    assert len(res.json()) > 0


def test_astra_check_overall_verdict_present(auth_client):
    res = auth_client.get("/api/v1/astra-check")
    assert res.status_code == 200
    assert res.json()["overall_verdict"] in ["GOOD TO BUY", "REVIEW SUGGESTED", "NOT RECOMMENDED"]
