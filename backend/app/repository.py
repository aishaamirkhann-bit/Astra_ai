import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from app.data import PRODUCTS
from app.models.explore import ProductModel

_BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_DIR / ".env")
if not os.getenv("ASTRA_DATABASE_URL") and not os.getenv("DATABASE_URL"):
    load_dotenv(_BACKEND_DIR / ".env.example")


_DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / ".astra_ai.db"
DATABASE_PATH = Path(os.getenv("ASTRA_DB_PATH", _DEFAULT_DATABASE_PATH))
DATABASE_URL = os.getenv("ASTRA_DATABASE_URL") or os.getenv("DATABASE_URL")


class ProductRepository:
    def __init__(self, database_path: Path = DATABASE_PATH, database_url: str | None = None) -> None:
        self.database_path = database_path
        self.database_url = database_url

    def _connect(self) -> Any:
        if self.database_url:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as error:
                raise RuntimeError("Install psycopg[binary] to use PostgreSQL") from error
            return psycopg.connect(self.database_url, row_factory=dict_row)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            if self.database_url:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS products (
                        id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
                        price DOUBLE PRECISION NOT NULL, rating DOUBLE PRECISION NOT NULL,
                        total_reviews INTEGER NOT NULL, seller_name TEXT NOT NULL,
                        is_verified_seller BOOLEAN NOT NULL, badge TEXT, image_url TEXT NOT NULL,
                        semantic_tags TEXT NOT NULL, description TEXT NOT NULL, fit TEXT NOT NULL,
                        trust INTEGER NOT NULL, search_terms TEXT NOT NULL
                    )
                    """
                )
                count_row = connection.execute("SELECT COUNT(*) AS product_count FROM products").fetchone()
                product_count = count_row["product_count"]
                if product_count == 0:
                    with connection.cursor() as cursor:
                        cursor.executemany(
                            """
                            INSERT INTO products (
                                id, title, category, price, rating, total_reviews, seller_name,
                                is_verified_seller, badge, image_url, semantic_tags, description,
                                fit, trust, search_terms
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            self._seed_rows(),
                        )
                self._refresh_image_urls(connection, "%s")
                return
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    price REAL NOT NULL,
                    rating REAL NOT NULL,
                    total_reviews INTEGER NOT NULL,
                    seller_name TEXT NOT NULL,
                    is_verified_seller INTEGER NOT NULL,
                    badge TEXT,
                    image_url TEXT NOT NULL,
                    semantic_tags TEXT NOT NULL,
                    description TEXT NOT NULL,
                    fit TEXT NOT NULL,
                    trust INTEGER NOT NULL,
                    search_terms TEXT NOT NULL
                )
                """
            )
            product_count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            if product_count == 0:
                connection.executemany(
                    """
                    INSERT INTO products (
                        id, title, category, price, rating, total_reviews,
                        seller_name, is_verified_seller, badge, image_url,
                        semantic_tags, description, fit, trust, search_terms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._seed_rows(),
                )
            self._refresh_image_urls(connection, "?")

    def _refresh_image_urls(self, connection: Any, placeholder: str) -> None:
        update_sql = f"UPDATE products SET image_url = {placeholder} WHERE id = {placeholder}"
        image_rows = [(product["image_url"], product["id"]) for product in PRODUCTS]
        if placeholder == "%s":
            with connection.cursor() as cursor:
                cursor.executemany(update_sql, image_rows)
        else:
            connection.executemany(update_sql, image_rows)

    @staticmethod
    def _seed_rows() -> list[tuple[Any, ...]]:
        return [
            (
                product["id"], product["title"], product["category"], product["price"],
                product["rating"], product["total_reviews"], product["seller_name"],
                bool(product["is_verified_seller"]), product["badge"], product["image_url"],
                json.dumps(product["semantic_tags"]), product["description"], product["fit"],
                product["trust"], product["search_terms"],
            )
            for product in PRODUCTS
        ]

    @staticmethod
    def _deserialize(row: Any) -> ProductModel:
        product = dict(row)
        product["is_verified_seller"] = bool(product["is_verified_seller"])
        product["semantic_tags"] = json.loads(product["semantic_tags"])
        return product

    def list_products(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM products").fetchall()
        products = [self._deserialize(row) for row in rows]
        catalog_order = {product["id"]: index for index, product in enumerate(PRODUCTS)}
        return sorted(products, key=lambda product: catalog_order.get(product["id"], len(catalog_order)))

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            placeholder = "%s" if self.database_url else "?"
            row = connection.execute(f"SELECT * FROM products WHERE id = {placeholder}", (product_id,)).fetchone()
        return self._deserialize(row) if row else None


product_repository = ProductRepository(database_url=DATABASE_URL)
