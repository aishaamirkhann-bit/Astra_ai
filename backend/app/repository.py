import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from app.data import PRODUCTS
from app.models.explore import ProductModel
from app.models.category import CategoryModel

_BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_DIR / ".env")


_DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / ".astra_ai.db"
DATABASE_PATH = Path(os.getenv("ASTRA_DB_PATH", _DEFAULT_DATABASE_PATH))
DATABASE_URL = os.getenv("ASTRA_DATABASE_URL") or os.getenv("DATABASE_URL")
CATEGORY_NAMES = [
    "Mobiles", "Laptops & Computers", "Audio & Wearables", "Jewelry",
    "Clothing & Fashion", "Makeup & Beauty", "Home Appliances", "Households",
]


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
            self._initialize_categories(connection)
            if self.database_url:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS products (
                        id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
                        category_id TEXT REFERENCES categories(id),
                        price DOUBLE PRECISION NOT NULL, rating DOUBLE PRECISION NOT NULL,
                        total_reviews INTEGER NOT NULL, seller_name TEXT NOT NULL,
                        is_verified_seller BOOLEAN NOT NULL, badge TEXT, image_url TEXT NOT NULL,
                        semantic_tags TEXT NOT NULL, description TEXT NOT NULL, fit TEXT NOT NULL,
                        trust INTEGER NOT NULL, search_terms TEXT NOT NULL
                    )
                    """
                )
                self._ensure_product_category_column(connection, "%s")
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
                self._refresh_seed_metadata(connection, "%s")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price)")
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
            self._ensure_product_category_column(connection, "?")
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
            self._refresh_seed_metadata(connection, "?")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_products_price ON products(price)")

    def _initialize_categories(self, connection: Any) -> None:
        if self.database_url:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS categories (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE)"
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO categories (id, name, slug) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    self._category_rows(),
                )
            return
        connection.execute(
            "CREATE TABLE IF NOT EXISTS categories (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE)"
        )
        connection.executemany(
            "INSERT OR IGNORE INTO categories (id, name, slug) VALUES (?, ?, ?)",
            self._category_rows(),
        )

    def _ensure_product_category_column(self, connection: Any, placeholder: str) -> None:
        if self.database_url:
            connection.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS category_id TEXT REFERENCES categories(id)")
        else:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(products)").fetchall()}
            if "category_id" not in columns:
                connection.execute("ALTER TABLE products ADD COLUMN category_id TEXT")
        update_sql = f"UPDATE products SET category_id = {placeholder} WHERE category = {placeholder}"
        rows = [(category["id"], category["name"]) for category in self._category_models()]
        if placeholder == "%s":
            with connection.cursor() as cursor:
                cursor.executemany(update_sql, rows)
        else:
            connection.executemany(update_sql, rows)

    @staticmethod
    def _category_models() -> list[CategoryModel]:
        names = CATEGORY_NAMES
        return [{"id": name.lower().replace(" & ", "-").replace(" ", "-"), "name": name, "slug": name.lower().replace(" & ", "-").replace(" ", "-")} for name in names]

    @classmethod
    def _category_rows(cls) -> list[tuple[str, str, str]]:
        return [(category["id"], category["name"], category["slug"]) for category in cls._category_models()]

    def _refresh_image_urls(self, connection: Any, placeholder: str) -> None:
        update_sql = f"UPDATE products SET image_url = {placeholder} WHERE id = {placeholder}"
        image_rows = [(product["image_url"], product["id"]) for product in PRODUCTS]
        if placeholder == "%s":
            with connection.cursor() as cursor:
                cursor.executemany(update_sql, image_rows)
        else:
            connection.executemany(update_sql, image_rows)

    def _refresh_seed_metadata(self, connection: Any, placeholder: str) -> None:
        update_sql = f"UPDATE products SET semantic_tags = {placeholder} WHERE id = {placeholder}"
        tag_rows = [(json.dumps(product["semantic_tags"]), product["id"]) for product in PRODUCTS]
        if placeholder == "%s":
            with connection.cursor() as cursor:
                cursor.executemany(update_sql, tag_rows)
        else:
            connection.executemany(update_sql, tag_rows)

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

    def list_categories(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            if self.database_url:
                rows = connection.execute(
                    "SELECT c.id, c.name, c.slug, COUNT(p.id) AS product_count "
                    "FROM categories c LEFT JOIN products p ON p.category_id = c.id "
                    "GROUP BY c.id, c.name, c.slug ORDER BY c.name"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT c.id, c.name, c.slug, COUNT(p.id) AS product_count "
                    "FROM categories c LEFT JOIN products p ON p.category_id = c.id "
                    "GROUP BY c.id, c.name, c.slug ORDER BY c.name"
                ).fetchall()
        return [dict(row) for row in rows]

    def list_category_products(
        self, category_slug: str, min_price: float, max_price: float, page: int, limit: int, sort_by: str,
        verified_only: bool = False, min_rating: float = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        self.initialize()
        placeholder = "%s" if self.database_url else "?"
        order_by = {"price_low_high": "p.price ASC", "price_high_low": "p.price DESC", "rating": "p.rating DESC"}.get(sort_by, "p.rating DESC")
        filters = [f"c.slug = {placeholder}", f"p.price BETWEEN {placeholder} AND {placeholder}", f"p.rating >= {placeholder}"]
        params: list[Any] = [category_slug, min_price, max_price, min_rating]
        if verified_only:
            filters.append("p.is_verified_seller = TRUE" if self.database_url else "p.is_verified_seller = 1")
        where_clause = " AND ".join(filters)
        offset = (page - 1) * limit
        with self._connect() as connection:
            count_sql = (
                f"SELECT COUNT(*) AS total FROM products p JOIN categories c ON c.id = p.category_id "
                f"WHERE {where_clause}"
            )
            count_row = connection.execute(count_sql, tuple(params)).fetchone()
            total = count_row["total"] if self.database_url else count_row[0]
            query_sql = (
                f"SELECT p.* FROM products p JOIN categories c ON c.id = p.category_id "
                f"WHERE {where_clause} "
                f"ORDER BY {order_by} LIMIT {placeholder} OFFSET {placeholder}"
            )
            rows = connection.execute(query_sql, tuple(params + [limit, offset])).fetchall()
        return [self._deserialize(row) for row in rows], total


product_repository = ProductRepository(database_url=DATABASE_URL)
