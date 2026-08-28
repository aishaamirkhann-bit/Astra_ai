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
