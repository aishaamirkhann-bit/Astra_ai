from sqlalchemy import Engine, inspect, text


def apply_sqlite_compatibility_migrations(engine: Engine) -> None:
    """Keep the local SQLite database aligned with the PostgreSQL migration."""
    if engine.dialect.name != "sqlite" or not inspect(engine).has_table("products"):
        return

    columns = {column["name"] for column in inspect(engine).get_columns("products")}
    with engine.begin() as connection:
        if "price" in columns and "base_price" not in columns:
            connection.execute(text("ALTER TABLE products RENAME COLUMN price TO base_price"))
            columns.remove("price")
            columns.add("base_price")
        if "stock_count" not in columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN stock_count INTEGER NOT NULL DEFAULT 10"))
        if "seller_id" not in columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN seller_id TEXT NOT NULL DEFAULT 'unknown'"))
        if "embedding" not in columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN embedding VECTOR(1536)"))
        connection.execute(
            text(
                "UPDATE products SET seller_id = lower(replace(replace(seller_name, ' ', '-'), '&', 'and')) "
                "WHERE seller_id = 'unknown' OR seller_id = ''"
            )
        )

    if inspect(engine).has_table("deals"):
        deal_columns = {column["name"] for column in inspect(engine).get_columns("deals")}
        if "stock_remaining" not in deal_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE deals ADD COLUMN stock_remaining INTEGER NOT NULL DEFAULT 0"))
