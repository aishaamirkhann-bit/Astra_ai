BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- Extend the existing shared catalog without dropping application data.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'products' AND column_name = 'price'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'products' AND column_name = 'base_price'
    ) THEN
        ALTER TABLE products RENAME COLUMN price TO base_price;
    END IF;
END $$;

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS stock_count INTEGER NOT NULL DEFAULT 10 CHECK (stock_count >= 0),
    ADD COLUMN IF NOT EXISTS seller_id TEXT,
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

UPDATE products
SET seller_id = lower(regexp_replace(seller_name, '[^a-zA-Z0-9]+', '-', 'g'))
WHERE seller_id IS NULL;

ALTER TABLE products ALTER COLUMN seller_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS ix_products_seller_id ON products (seller_id);
CREATE INDEX IF NOT EXISTS ix_products_embedding_hnsw
    ON products USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS seller_metrics (
    seller_id TEXT PRIMARY KEY,
    seller_name TEXT NOT NULL UNIQUE,
    seller_rating DOUBLE PRECISION NOT NULL CHECK (seller_rating BETWEEN 0 AND 100),
    fulfillment_rate DOUBLE PRECISION NOT NULL CHECK (fulfillment_rate BETWEEN 0 AND 100),
    authenticity_sentiment DOUBLE PRECISION NOT NULL CHECK (authenticity_sentiment BETWEEN 0 AND 100),
    price_stability DOUBLE PRECISION NOT NULL CHECK (price_stability BETWEEN 0 AND 100),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS market_price_history (
    id BIGSERIAL PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    competitor TEXT NOT NULL,
    price NUMERIC(14,2) NOT NULL CHECK (price > 0),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_market_price_product_observed
    ON market_price_history (product_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS deals (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    product_id TEXT NOT NULL UNIQUE REFERENCES products(id) ON DELETE CASCADE,
    listing_price NUMERIC(14,2) NOT NULL CHECK (listing_price > 0),
    market_avg_price NUMERIC(14,2) NOT NULL CHECK (market_avg_price > 0),
    discount_pct NUMERIC(6,2) NOT NULL CHECK (discount_pct BETWEEN 0 AND 100),
    trust_score NUMERIC(5,2) NOT NULL CHECK (trust_score BETWEEN 0 AND 100),
    seller_fulfillment_score NUMERIC(5,2) NOT NULL CHECK (seller_fulfillment_score BETWEEN 0 AND 100),
    authenticity_sentiment_score NUMERIC(5,2) NOT NULL CHECK (authenticity_sentiment_score BETWEEN 0 AND 100),
    price_stability_score NUMERIC(5,2) NOT NULL CHECK (price_stability_score BETWEEN 0 AND 100),
    badge_type TEXT NOT NULL CHECK (badge_type IN ('Bestseller', 'New', 'Mega Deal')),
    stock_remaining INTEGER NOT NULL DEFAULT 0 CHECK (stock_remaining >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    deal_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE deals
    ADD COLUMN IF NOT EXISTS stock_remaining INTEGER NOT NULL DEFAULT 0 CHECK (stock_remaining >= 0);
CREATE INDEX IF NOT EXISTS ix_deals_active_trust_discount
    ON deals (is_active, trust_score DESC, discount_pct DESC);

CREATE TABLE IF NOT EXISTS seller_verifications (
    seller_id TEXT PRIMARY KEY,
    seller_name TEXT NOT NULL UNIQUE,
    business_name TEXT NOT NULL,
    verification_status TEXT NOT NULL CHECK (verification_status IN ('pending', 'verified', 'rejected', 'suspended')),
    business_identity_verified BOOLEAN NOT NULL DEFAULT FALSE,
    fulfillment_rate DOUBLE PRECISION NOT NULL CHECK (fulfillment_rate BETWEEN 0 AND 100),
    return_rate DOUBLE PRECISION NOT NULL CHECK (return_rate BETWEEN 0 AND 100),
    dispute_rate DOUBLE PRECISION NOT NULL CHECK (dispute_rate BETWEEN 0 AND 100),
    trust_index DOUBLE PRECISION NOT NULL CHECK (trust_index BETWEEN 0 AND 100),
    review_sentiment_score DOUBLE PRECISION NOT NULL CHECK (review_sentiment_score BETWEEN 0 AND 100),
    price_stability_score DOUBLE PRECISION NOT NULL CHECK (price_stability_score BETWEEN 0 AND 100),
    is_flagged BOOLEAN NOT NULL DEFAULT FALSE,
    last_verified_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE seller_verifications
    ADD COLUMN IF NOT EXISTS business_name TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS verification_status TEXT NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS dispute_rate DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS trust_index DOUBLE PRECISION NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS trust_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    audit_id TEXT NOT NULL UNIQUE DEFAULT gen_random_uuid()::text,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    seller_id TEXT NOT NULL,
    action TEXT NOT NULL,
    previous_score DOUBLE PRECISION,
    computed_score DOUBLE PRECISION NOT NULL CHECK (computed_score BETWEEN 0 AND 100),
    final_score DOUBLE PRECISION NOT NULL CHECK (final_score BETWEEN 0 AND 100),
    calculated_trust_score DOUBLE PRECISION NOT NULL CHECK (calculated_trust_score BETWEEN 0 AND 100),
    authenticity_flag BOOLEAN NOT NULL DEFAULT FALSE,
    price_anomaly_detected BOOLEAN NOT NULL DEFAULT FALSE,
    reasoning_summary TEXT NOT NULL,
    components JSONB NOT NULL,
    reason TEXT NOT NULL,
    actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    inspected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE trust_audit_logs
    ADD COLUMN IF NOT EXISTS audit_id TEXT DEFAULT gen_random_uuid()::text,
    ADD COLUMN IF NOT EXISTS calculated_trust_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS authenticity_flag BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS price_anomaly_detected BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS reasoning_summary TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS inspected_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE UNIQUE INDEX IF NOT EXISTS uq_trust_audit_logs_audit_id ON trust_audit_logs (audit_id);
CREATE INDEX IF NOT EXISTS ix_trust_audit_product_created ON trust_audit_logs (product_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_trust_audit_seller_created ON trust_audit_logs (seller_id, created_at DESC);

CREATE TABLE IF NOT EXISTS platform_trust_metrics (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    verified_sellers_count INTEGER NOT NULL DEFAULT 0,
    flagged_listings_count INTEGER NOT NULL DEFAULT 0,
    avg_trust_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    active_ai_scans INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deal_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    deal_id TEXT REFERENCES deals(id) ON DELETE SET NULL,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    decision TEXT NOT NULL,
    reasoning JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_deal_audit_product_created
    ON deal_audit_logs (product_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_deal_audit_deal_id ON deal_audit_logs (deal_id);

CREATE TABLE IF NOT EXISTS deal_reservations (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    deal_id TEXT NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    status TEXT NOT NULL DEFAULT 'reserved',
    reserved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_deal_reservations_deal_id ON deal_reservations (deal_id);

ALTER TABLE deal_reservations
    ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS size TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS color TEXT NOT NULL DEFAULT '';

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS reservation_id TEXT REFERENCES deal_reservations(id),
    ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS size TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS color TEXT NOT NULL DEFAULT '';
CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_reservation_id
    ON orders (reservation_id) WHERE reservation_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS cart_items (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    size TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_cart_user_product_variant UNIQUE (user_id, product_id, size, color)
);
CREATE INDEX IF NOT EXISTS ix_cart_items_user_id ON cart_items (user_id);

CREATE TABLE IF NOT EXISTS user_budgets (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    monthly_limit NUMERIC(14,2) NOT NULL CHECK (monthly_limit >= 0),
    current_spent NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (current_spent >= 0),
    rollover_savings NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (rollover_savings >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS shopping_goals (
    goal_id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_title TEXT NOT NULL,
    target_price NUMERIC(14,2) NOT NULL CHECK (target_price > 0),
    saved_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (saved_amount >= 0),
    category TEXT NOT NULL,
    priority_level TEXT NOT NULL CHECK (priority_level IN ('Low', 'Medium', 'High')),
    status TEXT NOT NULL CHECK (status IN ('Active', 'Completed', 'Paused')),
    deadline DATE,
    image_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_shopping_goals_user_status ON shopping_goals (user_id, status);

CREATE TABLE IF NOT EXISTS budget_alerts (
    alert_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    goal_id BIGINT REFERENCES shopping_goals(goal_id) ON DELETE CASCADE,
    deal_id TEXT REFERENCES deals(id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL CHECK (alert_type IN ('Deal_Matched', 'Budget_Warning')),
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_budget_alert_match UNIQUE (user_id, goal_id, deal_id, alert_type)
);
CREATE INDEX IF NOT EXISTS ix_budget_alerts_user_created ON budget_alerts (user_id, created_at DESC);

-- PostgreSQL emits a durable database-side notification for external writers.
-- The FastAPI bridge converts the same domain events to Redis channel astra:deals.
CREATE OR REPLACE FUNCTION notify_deal_change() RETURNS trigger AS $$
DECLARE
    event_type TEXT;
BEGIN
    event_type := CASE
        WHEN TG_OP = 'INSERT' THEN 'deal_updated'
        WHEN NEW.is_active = FALSE AND OLD.is_active = TRUE THEN 'deal_expired'
        ELSE 'deal_updated'
    END;
    PERFORM pg_notify(
        'deal_events',
        json_build_object('type', event_type, 'deal_id', NEW.id, 'product_id', NEW.product_id)::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS deals_change_notify ON deals;
CREATE TRIGGER deals_change_notify
AFTER INSERT OR UPDATE ON deals
FOR EACH ROW EXECUTE FUNCTION notify_deal_change();

COMMIT;
