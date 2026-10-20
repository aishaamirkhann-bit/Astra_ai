import asyncio

import pytest
from pydantic import ValidationError

from app.schemas.product_research import (
    ProductResearchInput,
    ProductResearchOut,
    ResearchSource,
)
from app.services import product_research


PRODUCT_ID = "samsung-galaxy-s25-ultra"
PRODUCT_URL = "https://reviews.example.test/phone"
SELLER_URL = "https://seller.example.test/store"
SELLER_REVIEW_URL = "https://reviews.example.test/seller"


def _subject(seller_name: str | None = "TechBazaar Official") -> ProductResearchInput:
    return ProductResearchInput(
        id=PRODUCT_ID,
        slug=PRODUCT_ID,
        name="Samsung Galaxy S25 Ultra",
        brand="Samsung",
        category="Mobiles",
        seller_name=seller_name,
    )


def _synthesis(*args) -> dict:
    _ = args
    return {
        "overview": "A flagship Android phone based on the cited review.",
        "specifications": {"Display": "6.9-inch AMOLED"},
        "pros": ["Bright display"],
        "cons": ["Large size"],
        "review_summary": {
            "overall_sentiment": "Mostly positive",
            "common_complaints": ["Large size"],
        },
        "price_comparison": [{
            "store": "Example Store",
            "price": 300000,
            "currency": "PKR",
            "url": PRODUCT_URL,
        }],
        "alternatives": [{"name": "Example Alternative", "why": "Lower-priced option", "approx_price": "PKR 250,000"}],
        "warranty_support": "A one-year warranty is listed.",
        "red_flags": [],
        "buying_advice": "Compare the warranty terms before purchase.",
        "seller_report": {
            "name": "Ignored model value",
            "rating": 4.2,
            "reputation_signals": ["Store profile found"],
            "complaints_or_scam_reports": [],
            "return_policy": "Returns within seven days.",
            "verdict": "trustworthy",
        },
        "evidence": {
            "overview": [PRODUCT_URL],
            "specifications": [PRODUCT_URL],
            "pros": [PRODUCT_URL],
            "cons": [PRODUCT_URL],
            "review_summary": [PRODUCT_URL],
            "price_comparison": [PRODUCT_URL],
            "alternatives": [PRODUCT_URL],
            "warranty_support": [PRODUCT_URL],
            "buying_advice": [PRODUCT_URL],
            "seller_report": [SELLER_URL, SELLER_REVIEW_URL],
        },
    }


def _mock_research(monkeypatch, *, fail_search: bool = False) -> dict[str, int]:
    monkeypatch.setattr(product_research.settings, "SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr(product_research.settings, "SEARCH_API_KEY", "test-search-key")
    monkeypatch.setattr(product_research.settings, "GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(product_research.settings, "VISION_API_KEY", "")
    monkeypatch.setattr(product_research.settings, "RESEARCH_CACHE_TTL_HOURS", 24)
    calls = {"search": 0, "fetch": 0, "synthesis": 0}

    async def search(query, client):
        _ = query, client
        calls["search"] += 1
        if fail_search:
            raise RuntimeError("provider unavailable")
        return [
            {"title": "Product review", "url": PRODUCT_URL, "content": "Display review and price."},
            {"title": "Seller profile", "url": SELLER_URL, "content": "Seller policies."},
            {"title": "Seller review", "url": SELLER_REVIEW_URL, "content": "Seller reputation."},
        ]

    async def fetch(url, client):
        _ = client
        calls["fetch"] += 1
        return f"Fetched content from {url}"

    async def public_host(host, port):
        _ = host, port
        return True

    async def synthesize(*args):
        _ = args
        calls["synthesis"] += 1
        return _synthesis()

    monkeypatch.setattr(product_research, "_search_web", search)
    monkeypatch.setattr(product_research, "_fetch_page", fetch)
    monkeypatch.setattr(product_research, "_is_public_host", public_host)
    monkeypatch.setattr(product_research, "_request_groq_synthesis", synthesize)
    product_research.clear_research_cache()
    return calls


def test_research_service_synthesizes_only_cited_sources(monkeypatch) -> None:
    calls = _mock_research(monkeypatch)
    report = asyncio.run(product_research.research_product(_subject()))

    assert report.status == "complete"
    assert report.overview == "A flagship Android phone based on the cited review."
    assert report.sources[0].url == PRODUCT_URL
    assert report.seller_report.name == "TechBazaar Official"
    assert report.seller_report.verdict == "trustworthy"
    assert report.price_comparison[0].url == PRODUCT_URL
    assert report.evidence["overview"] == [PRODUCT_URL]
    assert calls["search"] == 8
    assert calls["fetch"] == 3
    assert calls["synthesis"] == 1


def test_research_service_cache_hit_and_explicit_refresh(monkeypatch) -> None:
    calls = _mock_research(monkeypatch)

    first = asyncio.run(product_research.research_product(_subject()))
    cached = asyncio.run(product_research.research_product(_subject()))
    refreshed = asyncio.run(product_research.research_product(_subject(), refresh=True))

    assert first.generated_at == cached.generated_at
    assert refreshed.generated_at >= first.generated_at
    assert calls["synthesis"] == 2
    assert calls["search"] == 16


def test_research_service_provider_failure_returns_partial_without_claims(monkeypatch) -> None:
    calls = _mock_research(monkeypatch, fail_search=True)
    report = asyncio.run(product_research.research_product(_subject()))

    assert report.status == "partial"
    assert "no usable sources" in report.message.lower()
    assert report.overview is None
    assert report.seller_report.verdict == "unknown"
    assert report.sources == []
    assert calls["synthesis"] == 0


def test_research_without_seller_keeps_seller_verdict_unknown(monkeypatch) -> None:
    _mock_research(monkeypatch)
    report = asyncio.run(product_research.research_product(_subject(seller_name=None)))

    assert report.seller_report.name is None
    assert report.seller_report.verdict == "unknown"
    assert report.seller_report.reputation_signals == []
    assert all("seller" not in query for query in product_research._research_queries(_subject(seller_name=None)))


def test_research_response_schema_rejects_non_http_sources() -> None:
    with pytest.raises(ValidationError):
        ResearchSource(title="Invalid", url="javascript:alert(1)")

    report = ProductResearchOut(
        generated_at="2026-01-01T00:00:00Z",
        status="partial",
    )
    assert report.confidence == "low"
    assert report.seller_report.verdict == "unknown"


def test_single_seller_source_cannot_establish_trustworthy_verdict() -> None:
    raw = _synthesis()
    raw["evidence"]["seller_report"] = [SELLER_URL]
    sources = [
        ResearchSource(title="Product review", url=PRODUCT_URL),
        ResearchSource(title="Seller profile", url=SELLER_URL),
    ]

    report = product_research._validated_report(raw, _subject(), sources)

    assert report.seller_report.verdict == "unknown"


def test_research_endpoint_returns_cached_report_and_refreshes(auth_client, monkeypatch) -> None:
    calls = _mock_research(monkeypatch)

    first = auth_client.get(f"/api/v1/products/{PRODUCT_ID}/research")
    cached = auth_client.get(f"/api/v1/products/{PRODUCT_ID}/research")
    refreshed = auth_client.get(f"/api/v1/products/{PRODUCT_ID}/research?refresh=true")

    assert first.status_code == cached.status_code == refreshed.status_code == 200
    assert first.json()["overview"] == "A flagship Android phone based on the cited review."
    assert first.json()["generated_at"] == cached.json()["generated_at"]
    assert calls["synthesis"] == 2


def test_research_endpoint_reports_provider_failure_as_partial(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(product_research.settings, "SEARCH_PROVIDER", "tavily")
    monkeypatch.setattr(product_research.settings, "SEARCH_API_KEY", "")
    product_research.clear_research_cache()

    response = auth_client.get(f"/api/v1/products/{PRODUCT_ID}/research")

    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert response.json()["seller_report"]["verdict"] == "unknown"
    assert response.json()["overview"] is None


def test_research_endpoint_supports_explore_catalog_and_missing_seller(auth_client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.endpoints.products.product_repository.get_product",
        lambda product_id: {
            "id": product_id,
            "title": "Explore-only product",
            "category": "Accessories",
            "seller_name": "",
        },
    )
    monkeypatch.setattr(product_research.settings, "SEARCH_API_KEY", "")
    product_research.clear_research_cache()

    response = auth_client.get("/api/v1/products/explore-only/research")

    assert response.status_code == 200
    assert response.json()["seller_report"]["name"] is None
    assert response.json()["seller_report"]["verdict"] == "unknown"
