-- Shared `products` table — owned jointly by Home backend and Explore backend.
-- Both backends' SQLAlchemy models (app/models/product.py) map onto this exact
-- structure. If either side needs a new column, update BOTH the DDL here and
-- the SQLAlchemy model, and tell your partner before merging.

-- Table: public.products
-- DROP TABLE IF EXISTS public.products;
CREATE TABLE IF NOT EXISTS public.products
(
    id text COLLATE pg_catalog."default" NOT NULL,
    title text COLLATE pg_catalog."default" NOT NULL,
    category text COLLATE pg_catalog."default" NOT NULL,
    price double precision NOT NULL,
    rating double precision NOT NULL,
    total_reviews integer NOT NULL,
    seller_name text COLLATE pg_catalog."default" NOT NULL,
    is_verified_seller boolean NOT NULL,
    badge text COLLATE pg_catalog."default",
    image_url text COLLATE pg_catalog."default" NOT NULL,
    semantic_tags text COLLATE pg_catalog."default" NOT NULL,
    description text COLLATE pg_catalog."default" NOT NULL,
    fit text COLLATE pg_catalog."default" NOT NULL,
    trust integer NOT NULL,
    search_terms text COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT products_pkey PRIMARY KEY (id)
);
