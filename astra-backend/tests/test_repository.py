import sqlite3
from pathlib import Path

from sqlalchemy.engine import URL

from app.data import PRODUCTS
from app.core.database import resolve_database_url
from app.repository import ProductRepository


def test_repository_seeds_and_reads_products(tmp_path: Path) -> None:
    repository = ProductRepository(tmp_path / "catalog.db")

    repository.initialize()
    products = repository.list_products()
    expected_product = PRODUCTS[0]
    product = repository.get_product(expected_product["id"])

    assert len(products) == len(PRODUCTS)
    assert product is not None
    assert product["title"] == expected_product["title"]
    assert product["semantic_tags"] == expected_product["semantic_tags"]


def test_repository_keeps_existing_catalog_without_duplicate_seeds(tmp_path: Path) -> None:
    repository = ProductRepository(tmp_path / "catalog.db")

    repository.initialize()
    repository.list_products()

    with repository._connect() as connection:
        count = connection.execute("SELECT COUNT(*) AS product_count FROM explore_products").fetchone()[0]

    assert count == len(PRODUCTS)


def test_repository_uses_shared_database_url_without_touching_commerce_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "shared.db"
    database_url = URL.create("sqlite", database=str(database_path)).render_as_string(hide_password=False)
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE products (id TEXT PRIMARY KEY)")

    repository = ProductRepository(database_url=database_url)
    repository.initialize()
    assert len(repository.list_products()) == len(PRODUCTS)

    with repository._connect() as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    assert {"products", "explore_products", "explore_categories"}.issubset(tables)


def test_postgres_database_urls_use_psycopg_driver() -> None:
    assert resolve_database_url("postgres://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
    assert resolve_database_url("postgresql://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
