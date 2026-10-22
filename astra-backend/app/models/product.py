from sqlalchemy import Column, Text, Float, Integer, Boolean, String
from sqlalchemy.orm import synonym
from pgvector.sqlalchemy import Vector
from app.core.database import Base


class Product(Base):
    """
    Matches the partner's `public.products` table exactly (Explore backend
    reads/writes the same table) — this is the single shared products table
    for both the Home page and the Explore page.
    """
    __tablename__ = "products"

    id = Column(Text, primary_key=True, index=True)   # e.g. "samsung-galaxy-s25-ultra" — doubles as our old "slug"
    title = Column(Text, nullable=False)                # was `name`
    category = Column(Text, nullable=False)
    origin_country = Column(String(2), nullable=False, default="PK", server_default="PK")
    base_price = Column(Float, nullable=False)
    seller_price_floor = Column(Float, nullable=False, default=0, server_default="0")
    # Backwards-compatible domain alias used by Home/Explore services.
    price = synonym("base_price")
    slug = synonym("id")
    name = synonym("title")
    rating = Column(Float, nullable=False)
    total_reviews = Column(Integer, nullable=False, default=0)
    seller_name = Column(Text, nullable=False)
    is_verified_seller = Column(Boolean, nullable=False, default=False)
    badge = Column(Text, nullable=True)                 # was `tag`: "Bestseller" | "New" | "Deal" | None
    tag = synonym("badge")
    image_url = Column(Text, nullable=False)
    semantic_tags = Column(Text, nullable=False)        # comma-separated, e.g. "fits your budget,verified seller"
    description = Column(Text, nullable=False)
    fit = Column(Text, nullable=False)                  # precomputed generic fit label ("Fits your budget" etc.)
    trust = Column(Integer, nullable=False)             # was `trust_score`
    trust_score = synonym("trust")
    search_terms = Column(Text, nullable=False)         # comma-separated keywords for Explore search
    stock_count = Column(Integer, nullable=False, default=10)
    stock_level = synonym("stock_count")
    seller_id = Column(Text, nullable=False, index=True)
    embedding = Column(Vector(1536), nullable=True)
    barcode = Column(String(14), nullable=True, index=True)
    barcode_verified = Column(Boolean, nullable=False, default=False)
    listing_status = Column(String(10), nullable=False, default="active", server_default="active")
    brand = Column(String(120), nullable=False, default="")
    subcategory = Column(String(120), nullable=False, default="")
    color = Column(String(80), nullable=False, default="")
    size = Column(String(80), nullable=False, default="")
    variant = Column(String(120), nullable=False, default="")
    specifications = Column(Text, nullable=False, default="{}")
    quality_tags = Column(Text, nullable=False, default="[]")
