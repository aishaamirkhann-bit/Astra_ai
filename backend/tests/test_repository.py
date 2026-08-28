from pathlib import Path

from app.repository import ProductRepository


def test_repository_seeds_and_reads_products(tmp_path: Path) -> None:
    repository = ProductRepository(tmp_path / "catalog.db")

    products = repository.list_products()
    product = repository.get_product("lenovo-ideapad-slim-5")

    assert len(products) == 7
    assert product is not None
    assert product["title"] == "Lenovo IdeaPad Slim 5"
    assert product["semantic_tags"] == ["Fits your budget", "Verified seller"]


def test_repository_keeps_existing_catalog_without_duplicate_seeds(tmp_path: Path) -> None:
    repository = ProductRepository(tmp_path / "catalog.db")

    repository.list_products()
    repository.list_products()

    with repository._connect() as connection:
        count = connection.execute("SELECT COUNT(*) AS product_count FROM products").fetchone()[0]

    assert count == 7
