from sqlalchemy import Engine, inspect, text


def apply_sqlite_compatibility_migrations(engine: Engine) -> None:
    """Keep the local SQLite database aligned with the PostgreSQL migration."""
    if engine.dialect.name != "sqlite":
        return

    if inspect(engine).has_table("users"):
        user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
        if "country" not in user_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN country VARCHAR(2) NOT NULL DEFAULT 'PK'"))
    if not inspect(engine).has_table("products"):
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
        product_metadata_columns = {
            "origin_country": "VARCHAR(2) NOT NULL DEFAULT 'PK'",
            "seller_price_floor": "FLOAT NOT NULL DEFAULT 0",
            "barcode": "VARCHAR(14)",
            "barcode_verified": "BOOLEAN NOT NULL DEFAULT 0",
            "listing_status": "VARCHAR(10) NOT NULL DEFAULT 'active'",
            "brand": "VARCHAR(120) NOT NULL DEFAULT ''",
            "subcategory": "VARCHAR(120) NOT NULL DEFAULT ''",
            "color": "VARCHAR(80) NOT NULL DEFAULT ''",
            "size": "VARCHAR(80) NOT NULL DEFAULT ''",
            "variant": "VARCHAR(120) NOT NULL DEFAULT ''",
            "specifications": "TEXT NOT NULL DEFAULT '{}'",
            "quality_tags": "TEXT NOT NULL DEFAULT '[]'",
        }
        for column, definition in product_metadata_columns.items():
            if column not in columns:
                connection.execute(text(f"ALTER TABLE products ADD COLUMN {column} {definition}"))
        connection.execute(text("UPDATE products SET seller_price_floor = base_price WHERE seller_price_floor <= 0"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_products_barcode ON products (barcode)"))
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

    if inspect(engine).has_table("deal_reservations"):
        reservation_columns = {column["name"] for column in inspect(engine).get_columns("deal_reservations")}
        with engine.begin() as connection:
            if "user_id" not in reservation_columns:
                connection.execute(text("ALTER TABLE deal_reservations ADD COLUMN user_id INTEGER REFERENCES users(id)"))
            if "size" not in reservation_columns:
                connection.execute(text("ALTER TABLE deal_reservations ADD COLUMN size TEXT NOT NULL DEFAULT ''"))
            if "color" not in reservation_columns:
                connection.execute(text("ALTER TABLE deal_reservations ADD COLUMN color TEXT NOT NULL DEFAULT ''"))

    if inspect(engine).has_table("orders"):
        order_columns = {column["name"] for column in inspect(engine).get_columns("orders")}
        with engine.begin() as connection:
            if "reservation_id" not in order_columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN reservation_id TEXT REFERENCES deal_reservations(id)"))
            if "quantity" not in order_columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1"))
            if "size" not in order_columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN size TEXT NOT NULL DEFAULT ''"))
            if "color" not in order_columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN color TEXT NOT NULL DEFAULT ''"))
            if "storage" not in order_columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN storage TEXT NOT NULL DEFAULT ''"))
            if "shipped_at" not in order_columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN shipped_at DATETIME"))
            if "delivered_at" not in order_columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN delivered_at DATETIME"))
            if "checkout_session_id" not in order_columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN checkout_session_id INTEGER"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_orders_checkout_session_id ON orders (checkout_session_id)"))
            if "negotiation_session_id" not in order_columns:
                connection.execute(text("ALTER TABLE orders ADD COLUMN negotiation_session_id INTEGER"))
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_negotiation_session_id ON orders (negotiation_session_id)"))

    if inspect(engine).has_table("order_return_requests"):
        return_columns = {column["name"] for column in inspect(engine).get_columns("order_return_requests")}
        if "request_type" not in return_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE order_return_requests ADD COLUMN request_type VARCHAR(16) NOT NULL DEFAULT 'return'"))

    if inspect(engine).has_table("negotiation_sessions"):
        negotiation_columns = {column["name"] for column in inspect(engine).get_columns("negotiation_sessions")}
        with engine.begin() as connection:
            columns_to_add = {
                "seller_id": "VARCHAR NOT NULL DEFAULT ''",
                "quantity": "INTEGER NOT NULL DEFAULT 1",
                "size": "TEXT NOT NULL DEFAULT ''",
                "color": "TEXT NOT NULL DEFAULT ''",
                "storage": "TEXT NOT NULL DEFAULT ''",
                "expires_at": "DATETIME",
                "buyer_approved_at": "DATETIME",
                "checkout_session_id": "INTEGER",
            }
            for column, definition in columns_to_add.items():
                if column not in negotiation_columns:
                    connection.execute(text(f"ALTER TABLE negotiation_sessions ADD COLUMN {column} {definition}"))
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_negotiation_sessions_checkout_session_id ON negotiation_sessions (checkout_session_id)"))

    if inspect(engine).has_table("cart_items"):
        cart_columns = {column["name"] for column in inspect(engine).get_columns("cart_items")}
        if "storage" not in cart_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE cart_items ADD COLUMN storage TEXT NOT NULL DEFAULT ''"))

    if inspect(engine).has_table("financial_consent_logs"):
        consent_columns = {column["name"] for column in inspect(engine).get_columns("financial_consent_logs")}
        with engine.begin() as connection:
            if "consumed_at" not in consent_columns:
                connection.execute(text("ALTER TABLE financial_consent_logs ADD COLUMN consumed_at DATETIME"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_financial_consent_order_status ON financial_consent_logs (reference_order_id, status, consumed_at)"))
            if "reference_checkout_id" not in consent_columns:
                connection.execute(text("ALTER TABLE financial_consent_logs ADD COLUMN reference_checkout_id INTEGER"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_financial_consent_checkout_status ON financial_consent_logs (reference_checkout_id, status, consumed_at)"))
            if "order_snapshot_hash" not in consent_columns:
                connection.execute(text("ALTER TABLE financial_consent_logs ADD COLUMN order_snapshot_hash VARCHAR(64)"))
            if "expires_at" not in consent_columns:
                connection.execute(text("ALTER TABLE financial_consent_logs ADD COLUMN expires_at DATETIME"))

    if inspect(engine).has_table("notifications"):
        with engine.begin() as connection:
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_user_created ON notifications (user_id, created_at)"))

    if inspect(engine).has_table("seller_verifications"):
        columns = {column["name"] for column in inspect(engine).get_columns("seller_verifications")}
        with engine.begin() as connection:
            if "business_name" not in columns:
                connection.execute(text("ALTER TABLE seller_verifications ADD COLUMN business_name TEXT NOT NULL DEFAULT ''"))
                connection.execute(text("UPDATE seller_verifications SET business_name = seller_name"))
            if "verification_status" not in columns:
                connection.execute(text("ALTER TABLE seller_verifications ADD COLUMN verification_status TEXT NOT NULL DEFAULT 'pending'"))
                connection.execute(text("UPDATE seller_verifications SET verification_status = CASE WHEN business_identity_verified = 1 THEN 'verified' ELSE 'pending' END"))
            if "dispute_rate" not in columns:
                connection.execute(text("ALTER TABLE seller_verifications ADD COLUMN dispute_rate FLOAT NOT NULL DEFAULT 0"))
            if "trust_index" not in columns:
                connection.execute(text("ALTER TABLE seller_verifications ADD COLUMN trust_index FLOAT NOT NULL DEFAULT 0"))

    if inspect(engine).has_table("trust_audit_logs"):
        columns = {column["name"] for column in inspect(engine).get_columns("trust_audit_logs")}
        with engine.begin() as connection:
            if "audit_id" not in columns:
                connection.execute(text("ALTER TABLE trust_audit_logs ADD COLUMN audit_id TEXT"))
                connection.execute(text("UPDATE trust_audit_logs SET audit_id = 'audit-' || id"))
            if "calculated_trust_score" not in columns:
                connection.execute(text("ALTER TABLE trust_audit_logs ADD COLUMN calculated_trust_score FLOAT NOT NULL DEFAULT 0"))
                connection.execute(text("UPDATE trust_audit_logs SET calculated_trust_score = final_score"))
            if "authenticity_flag" not in columns:
                connection.execute(text("ALTER TABLE trust_audit_logs ADD COLUMN authenticity_flag BOOLEAN NOT NULL DEFAULT 0"))
            if "price_anomaly_detected" not in columns:
                connection.execute(text("ALTER TABLE trust_audit_logs ADD COLUMN price_anomaly_detected BOOLEAN NOT NULL DEFAULT 0"))
            if "reasoning_summary" not in columns:
                connection.execute(text("ALTER TABLE trust_audit_logs ADD COLUMN reasoning_summary TEXT NOT NULL DEFAULT ''"))
                connection.execute(text("UPDATE trust_audit_logs SET reasoning_summary = reason"))
            if "inspected_at" not in columns:
                connection.execute(text("ALTER TABLE trust_audit_logs ADD COLUMN inspected_at DATETIME"))
                connection.execute(text("UPDATE trust_audit_logs SET inspected_at = created_at"))


def migrate_legacy_wallet_data(engine: Engine) -> None:
    """One-way local migration from the prototype wallet tables to the production ledger."""
    tables = set(inspect(engine).get_table_names())
    if engine.dialect.name != "sqlite" or not {"wallets", "user_wallets"}.issubset(tables):
        return
    with engine.begin() as connection:
        # SQLite may have been created with foreign_keys disabled. Mirror the
        # PostgreSQL ON DELETE SET NULL behavior before integer ids are reused.
        if {"wallet_transactions", "orders"}.issubset(tables):
            connection.execute(text(
                "UPDATE wallet_transactions SET reference_order_id = NULL "
                "WHERE reference_order_id IS NOT NULL AND reference_order_id NOT IN (SELECT id FROM orders)"
            ))
        if {"financial_consent_logs", "orders"}.issubset(tables):
            connection.execute(text(
                "UPDATE financial_consent_logs SET reference_order_id = NULL "
                "WHERE reference_order_id IS NOT NULL AND reference_order_id NOT IN (SELECT id FROM orders)"
            ))
        connection.execute(text(
            "INSERT OR IGNORE INTO user_wallets (wallet_id, user_id, currency, available_balance, frozen_balance, updated_at) "
            "SELECT id, user_id, 'PKR', MAX(available_balance, 0), 0, CURRENT_TIMESTAMP FROM wallets"
        ))
        if {"wallet_ledger_entries", "wallet_transactions"}.issubset(tables):
            connection.execute(text(
                "INSERT OR IGNORE INTO wallet_transactions (txn_id, wallet_id, amount, txn_type, description, created_at) "
                "SELECT 'legacy-' || id, wallet_id, ABS(amount), "
                "CASE WHEN entry_type = 'credit' THEN 'Credit' ELSE 'Debit' END, label, created_at "
                "FROM wallet_ledger_entries WHERE amount != 0"
            ))
