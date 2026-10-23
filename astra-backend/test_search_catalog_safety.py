"""Isolated search safety tests; deliberately outside tests/conftest.py.

These tests use temporary SQLite catalogues and do not import app.main or the
shared seeded buyer/wallet fixtures.
"""
import asyncio
import sqlite3
from pathlib import Path

from app.repository import ProductRepository
from app.schemas.requests import ExploreSearchRequest, QueryType
from app.services import explore


def test_catalogue_reads_do_not_create_database_or_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "not-created" / "catalog.db"
    repository = ProductRepository(database_path)

    assert repository.list_products() == []
    assert repository.get_product("missing") is None
    assert repository.list_categories() == []
    assert repository.list_category_products("mobiles", 0, 500000, 1, 10, "most_relevant") == ([], 0)
    assert not database_path.parent.exists()


def test_read_search_keeps_explicit_catalogue_price_and_rows_unchanged(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "catalog.db"
    repository = ProductRepository(database_path)
    repository.initialize()
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE explore_products SET price = 123456 WHERE id = ?", ("lenovo-ideapad-slim-5",))
        before = connection.execute("SELECT id, price FROM explore_products ORDER BY id").fetchall()

    monkeypatch.setattr(explore.product_repository, "list_products", repository.list_products)
    intent = explore.resolve_purchase_intent("buy lenovo laptop")
    result = asyncio.run(explore.execute_search(
        ExploreSearchRequest(query_type=QueryType.TEXT, text_query="lenovo laptop"), None, None,
    ))

    product = repository.get_product("lenovo-ideapad-slim-5")
    assert product is not None and product["price"] == 123456
    assert intent["auto_checkout"] is False
    assert intent["action"]["type"] == "search"
    assert result.results
    assert not hasattr(explore, "SessionLocal")
    with sqlite3.connect(database_path) as connection:
        after = connection.execute("SELECT id, price FROM explore_products ORDER BY id").fetchall()
    assert after == before


def test_search_excludes_known_inactive_and_empty_products_and_reports_known_stock(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.db"
    repository = ProductRepository(database_path)
    repository.initialize()
    with sqlite3.connect(database_path) as connection:
        connection.execute("ALTER TABLE explore_products ADD COLUMN listing_status TEXT")
        connection.execute("ALTER TABLE explore_products ADD COLUMN stock_count INTEGER")
        connection.execute("UPDATE explore_products SET listing_status='active', stock_count=0 WHERE id='lenovo-ideapad-slim-5'")
        connection.execute("UPDATE explore_products SET listing_status='inactive', stock_count=8 WHERE id='dell-xps-13'")
        connection.execute("UPDATE explore_products SET listing_status='active', stock_count=4, price=98765 WHERE id='sony-wh-1000xm5'")

    products = {product["id"]: product for product in repository.list_products()}
    assert "lenovo-ideapad-slim-5" not in products
    assert "dell-xps-13" not in products
    assert products["sony-wh-1000xm5"]["price"] == 98765
    assert products["sony-wh-1000xm5"]["availability"] == "in_stock"
    assert products["sony-wh-1000xm5"]["stock_count"] == 4
    assert products["apple-watch-series-9"]["availability"] == "unknown"
    category_items, total = repository.list_category_products("laptops-computers", 0, 500000, 1, 50, "most_relevant")
    assert total == len(category_items)
    assert {item["id"] for item in category_items}.isdisjoint({"lenovo-ideapad-slim-5", "dell-xps-13"})

