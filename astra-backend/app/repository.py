import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

from app.data import PRODUCTS
from app.core.config import settings
from app.core.database import resolve_database_url
from app.models.explore import ProductModel
from app.models.category import CategoryModel

DATABASE_PATH = Path(__file__).resolve().parents[1] / "astra.db"
DATABASE_URL = resolve_database_url(settings.DATABASE_URL)
CATEGORIES_TABLE = "explore_categories"
PRODUCTS_TABLE = "explore_products"
CATEGORY_NAMES = [
    "Mobiles", "Laptops & Computers", "Audio & Wearables", "Wearables", "Accessories",
    "Electronics & Accessories", "Jewelry", "Clothing & Fashion", "Dresses & Fashion",
    "Electronics & Computing", "Makeup & Beauty", "Home Appliances", "Home & Living",
    "Home Decor", "Furniture", "Wallpapers",
]


class ProductRepository:
    def __init__(self, database_path: Path = DATABASE_PATH, database_url: str | None = None) -> None:
        self.database_path = database_path
        self.database_url = database_url

    @property
    def is_postgres(self) -> bool:
        return bool(self.database_url and make_url(self.database_url).get_backend_name() == "postgresql")

    def _connect(self) -> Any:
        if self.is_postgres:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as error:
                raise RuntimeError("Install psycopg[binary] to use PostgreSQL") from error
            postgres_url = make_url(self.database_url).set(drivername="postgresql")
            return psycopg.connect(postgres_url.render_as_string(hide_password=False), row_factory=dict_row)
        sqlite_url = make_url(self.database_url) if self.database_url else None
        sqlite_path = Path(sqlite_url.database) if sqlite_url and sqlite_url.database not in (None, ":memory:") else self.database_path
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(sqlite_path if not sqlite_url or sqlite_url.database != ":memory:" else ":memory:")
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connect_readonly(self):
        """Open the existing catalogue without creating files or tables."""
        if self.database_url:
            connection = self._connect()
            try:
                connection.execute("SET TRANSACTION READ ONLY")
                yield connection
            finally:
                connection.close()
            return
        if not self.database_path.is_file():
            yield None
            return
        uri = f"{self.database_path.resolve().as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _table_columns(self, connection: Any, table_name: str) -> set[str]:
        if self.database_url:
            rows = connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = %s",
                (table_name,),
            ).fetchall()
            return {row["column_name"] for row in rows}
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row["name"] for row in rows}

    def _table_exists(self, connection: Any, table_name: str) -> bool:
        return bool(self._table_columns(connection, table_name))

    @staticmethod
    def _visible(product: dict[str, Any]) -> bool:
        listing_status = product.get("listing_status")
        stock_count = product.get("stock_count")
        if listing_status is not None and str(listing_status).lower() != "active":
            return False
        if stock_count is not None and int(stock_count) <= 0:
            return False
        return True

    def initialize(self) -> None:
        with self._connect() as connection:
            self._initialize_categories(connection)
            if self.is_postgres:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS explore_products (
                        id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
                        category_id TEXT REFERENCES explore_categories(id),
                        origin_country TEXT NOT NULL DEFAULT 'PK',
                        price DOUBLE PRECISION NOT NULL, rating DOUBLE PRECISION NOT NULL,
                        total_reviews INTEGER NOT NULL, seller_name TEXT NOT NULL,
                        is_verified_seller BOOLEAN NOT NULL, badge TEXT, image_url TEXT NOT NULL,
                        semantic_tags TEXT NOT NULL, description TEXT NOT NULL, fit TEXT NOT NULL,
                        trust INTEGER NOT NULL, search_terms TEXT NOT NULL
                    )
                    """
                )
                self._ensure_product_category_column(connection, "%s")
                self._ensure_product_origin_column(connection)
                self._migrate_legacy_categories(connection, "%s")
                with connection.cursor() as cursor:
                    cursor.executemany(
                        """
                        INSERT INTO explore_products (
                            id, title, category, price, rating, total_reviews, seller_name,
                            is_verified_seller, badge, image_url, semantic_tags, description,
                            fit, trust, search_terms, origin_country
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            category = EXCLUDED.category,
                            price = EXCLUDED.price,
                            rating = EXCLUDED.rating,
                            total_reviews = EXCLUDED.total_reviews,
                            seller_name = EXCLUDED.seller_name,
                            is_verified_seller = EXCLUDED.is_verified_seller,
                            badge = EXCLUDED.badge,
                            image_url = EXCLUDED.image_url,
                            semantic_tags = EXCLUDED.semantic_tags,
                            description = EXCLUDED.description,
                            fit = EXCLUDED.fit,
                            trust = EXCLUDED.trust,
                            search_terms = EXCLUDED.search_terms,
                            origin_country = EXCLUDED.origin_country
                        """,
                        self._seed_rows(),
                    )
                self._refresh_image_urls(connection, "%s")
                self._refresh_origin_countries(connection, "%s")
                self._refresh_seed_metadata(connection, "%s")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_explore_products_category_id ON explore_products(category_id)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_explore_products_price ON explore_products(price)")
                return
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS explore_products (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    origin_country TEXT NOT NULL DEFAULT 'PK',
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
            self._ensure_product_origin_column(connection)
            self._migrate_legacy_categories(connection, "?")
            connection.executemany(
                """
                INSERT INTO explore_products (
                    id, title, category, price, rating, total_reviews,
                    seller_name, is_verified_seller, badge, image_url,
                    semantic_tags, description, fit, trust, search_terms, origin_country
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    category = excluded.category,
                    price = excluded.price,
                    rating = excluded.rating,
                    total_reviews = excluded.total_reviews,
                    seller_name = excluded.seller_name,
                    is_verified_seller = excluded.is_verified_seller,
                    badge = excluded.badge,
                    image_url = excluded.image_url,
                    semantic_tags = excluded.semantic_tags,
                    description = excluded.description,
                    fit = excluded.fit,
                    trust = excluded.trust,
                    search_terms = excluded.search_terms,
                    origin_country = excluded.origin_country
                """,
                self._seed_rows(),
            )
            self._refresh_image_urls(connection, "?")
            self._refresh_origin_countries(connection, "?")
            self._refresh_seed_metadata(connection, "?")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_explore_products_category_id ON explore_products(category_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_explore_products_price ON explore_products(price)")

    def _initialize_categories(self, connection: Any) -> None:
        if self.is_postgres:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS explore_categories (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE)"
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO explore_categories (id, name, slug) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    self._category_rows(),
                )
            return
        connection.execute(
            "CREATE TABLE IF NOT EXISTS explore_categories (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, slug TEXT NOT NULL UNIQUE)"
        )
        connection.executemany(
            "INSERT OR IGNORE INTO explore_categories (id, name, slug) VALUES (?, ?, ?)",
            self._category_rows(),
        )

    def _ensure_product_category_column(self, connection: Any, placeholder: str) -> None:
        if self.is_postgres:
            connection.execute("ALTER TABLE explore_products ADD COLUMN IF NOT EXISTS category_id TEXT REFERENCES explore_categories(id)")
        else:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(explore_products)").fetchall()}
            if "category_id" not in columns:
                connection.execute("ALTER TABLE explore_products ADD COLUMN category_id TEXT")
        update_sql = f"UPDATE explore_products SET category_id = {placeholder} WHERE category = {placeholder}"
        rows = [(category["id"], category["name"]) for category in self._category_models()]
        if placeholder == "%s":
            with connection.cursor() as cursor:
                cursor.executemany(update_sql, rows)
        else:
            connection.executemany(update_sql, rows)

    def _ensure_product_origin_column(self, connection: Any) -> None:
        if self.database_url:
            connection.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS origin_country TEXT NOT NULL DEFAULT 'PK'")
        else:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(products)").fetchall()}
            if "origin_country" not in columns:
                connection.execute("ALTER TABLE products ADD COLUMN origin_country TEXT NOT NULL DEFAULT 'PK'")

    def _refresh_origin_countries(self, connection: Any, placeholder: str) -> None:
        update_sql = f"UPDATE products SET origin_country = {placeholder} WHERE id = {placeholder}"
        origin_rows = [(product.get("origin_country", "PK"), product["id"]) for product in PRODUCTS]
        if placeholder == "%s":
            with connection.cursor() as cursor:
                cursor.executemany(update_sql, origin_rows)
        else:
            connection.executemany(update_sql, origin_rows)

    def _migrate_legacy_categories(self, connection: Any, placeholder: str) -> None:
        legacy_name = "Households"
        canonical_name = "Home & Living"
        legacy = connection.execute(
            f"SELECT id FROM explore_categories WHERE name = {placeholder}", (legacy_name,)
        ).fetchone()
        canonical = connection.execute(
            f"SELECT id FROM explore_categories WHERE name = {placeholder}", (canonical_name,)
        ).fetchone()
        if legacy is None or canonical is None:
            return

        legacy_id = legacy["id"] if self.database_url else legacy[0]
        canonical_id = canonical["id"] if self.database_url else canonical[0]
        connection.execute(
            f"UPDATE explore_products SET category = {placeholder}, category_id = {placeholder} "
            f"WHERE category = {placeholder} OR category_id = {placeholder}",
            (canonical_name, canonical_id, legacy_name, legacy_id),
        )
        connection.execute(
            f"DELETE FROM explore_categories WHERE id = {placeholder}", (legacy_id,)
        )

    @staticmethod
    def _category_models() -> list[CategoryModel]:
        names = CATEGORY_NAMES
        return [{"id": name.lower().replace(" & ", "-").replace(" ", "-"), "name": name, "slug": name.lower().replace(" & ", "-").replace(" ", "-")} for name in names]

    @classmethod
    def _category_rows(cls) -> list[tuple[str, str, str]]:
        return [(category["id"], category["name"], category["slug"]) for category in cls._category_models()]

    def _refresh_image_urls(self, connection: Any, placeholder: str) -> None:
        update_sql = f"UPDATE explore_products SET image_url = {placeholder} WHERE id = {placeholder}"
        image_rows = [(product["image_url"], product["id"]) for product in PRODUCTS]
        if placeholder == "%s":
            with connection.cursor() as cursor:
                cursor.executemany(update_sql, image_rows)
        else:
            connection.executemany(update_sql, image_rows)

    def _refresh_seed_metadata(self, connection: Any, placeholder: str) -> None:
        update_sql = f"UPDATE explore_products SET semantic_tags = {placeholder} WHERE id = {placeholder}"
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
                product["trust"], product["search_terms"], product.get("origin_country", "PK"),
            )
            for product in PRODUCTS
        ]

    @staticmethod
    def _deserialize(row: Any) -> ProductModel:
        product = dict(row)
        product["is_verified_seller"] = bool(product["is_verified_seller"])
        product["semantic_tags"] = json.loads(product["semantic_tags"])
        stock_count = product.get("stock_count")
        listing_status = product.get("listing_status")
        product["stock_count"] = int(stock_count) if stock_count is not None else None
        product["availability"] = (
            "unavailable" if listing_status is not None and str(listing_status).lower() != "active"
            else "out_of_stock" if stock_count is not None and int(stock_count) <= 0
            else "in_stock" if listing_status is not None and str(listing_status).lower() == "active" and stock_count is not None
            else "unknown"
        )
        return product

    def list_products(self) -> list[dict[str, Any]]:
        with self._connect_readonly() as connection:
            if connection is None or not self._table_exists(connection, "products"):
                return []
            rows = connection.execute("SELECT * FROM products").fetchall()
        products = [product for product in map(self._deserialize, rows) if self._visible(product)]
        catalog_order = {product["id"]: index for index, product in enumerate(PRODUCTS)}
        return sorted(products, key=lambda product: catalog_order.get(product["id"], len(catalog_order)))

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        with self._connect_readonly() as connection:
            if connection is None or not self._table_exists(connection, "products"):
                return None
            placeholder = "%s" if self.database_url else "?"
            row = connection.execute(f"SELECT * FROM products WHERE id = {placeholder}", (product_id,)).fetchone()
        return self._deserialize(row) if row else None

    def list_categories(self) -> list[dict[str, Any]]:
        with self._connect_readonly() as connection:
            if connection is None or not self._table_exists(connection, "categories") or not self._table_exists(connection, "products"):
                return []
            product_columns = self._table_columns(connection, "products")
            visibility = []
            if "listing_status" in product_columns:
                visibility.append("p.listing_status = 'active'")
            if "stock_count" in product_columns:
                visibility.append("p.stock_count > 0")
            join = "p.category_id = c.id" + (" AND " + " AND ".join(visibility) if visibility else "")
            rows = connection.execute(
                "SELECT c.id, c.name, c.slug, COUNT(p.id) AS product_count "
                f"FROM categories c LEFT JOIN products p ON {join} "
                "GROUP BY c.id, c.name, c.slug ORDER BY c.name"
            ).fetchall()
        return [dict(row) for row in rows]

    def list_category_products(
        self, category_slug: str, min_price: float, max_price: float, page: int, limit: int, sort_by: str,
        verified_only: bool = False, min_rating: float = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        placeholder = "%s" if self.database_url else "?"
        order_by = {"price_low_high": "p.price ASC", "price_high_low": "p.price DESC", "rating": "p.rating DESC"}.get(sort_by, "p.rating DESC")
        filters = [f"c.slug = {placeholder}", f"p.price BETWEEN {placeholder} AND {placeholder}", f"p.rating >= {placeholder}"]
        params: list[Any] = [category_slug, min_price, max_price, min_rating]
        if verified_only:
            filters.append("p.is_verified_seller = TRUE" if self.is_postgres else "p.is_verified_seller = 1")
        where_clause = " AND ".join(filters)
        offset = (page - 1) * limit
        with self._connect_readonly() as connection:
            if connection is None or not self._table_exists(connection, "products") or not self._table_exists(connection, "categories"):
                return [], 0
            columns = self._table_columns(connection, "products")
            if "listing_status" in columns:
                filters.append("p.listing_status = 'active'")
            if "stock_count" in columns:
                filters.append("p.stock_count > 0")
            where_clause = " AND ".join(filters)
            count_sql = (
                f"SELECT COUNT(*) AS total FROM explore_products p JOIN explore_categories c ON c.id = p.category_id "
                f"WHERE {where_clause}"
            )
            count_row = connection.execute(count_sql, tuple(params)).fetchone()
            total = count_row["total"] if self.is_postgres else count_row[0]
            query_sql = (
                f"SELECT p.* FROM explore_products p JOIN explore_categories c ON c.id = p.category_id "
                f"WHERE {where_clause} "
                f"ORDER BY {order_by} LIMIT {placeholder} OFFSET {placeholder}"
            )
            rows = connection.execute(query_sql, tuple(params + [limit, offset])).fetchall()
        return [self._deserialize(row) for row in rows], total


product_repository = ProductRepository(database_url=DATABASE_URL)
