from pathlib import Path

from app.data import PRODUCTS
from app.repository import ProductRepository


def test_repository_seeds_and_reads_products(tmp_path: Path) -> None:
    repository = ProductRepository(tmp_path / "catalog.db")

    products = repository.list_products()
    expected_product = PRODUCTS[0]
    product = repository.get_product(expected_product["id"])

    assert len(products) == len(PRODUCTS)
    assert product is not None
    assert product["title"] == expected_product["title"]
    assert product["semantic_tags"] == expected_product["semantic_tags"]


def test_repository_keeps_existing_catalog_without_duplicate_seeds(tmp_path: Path) -> None:
    repository = ProductRepository(tmp_path / "catalog.db")

    repository.list_products()
    repository.list_products()

    with repository._connect() as connection:
        count = connection.execute("SELECT COUNT(*) AS product_count FROM products").fetchone()[0]

    assert count == len(PRODUCTS)
