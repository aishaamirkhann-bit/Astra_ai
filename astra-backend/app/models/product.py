from sqlalchemy import Column, Text, Float, Integer, Boolean
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
    price = Column(Float, nullable=False)
    rating = Column(Float, nullable=False)
    total_reviews = Column(Integer, nullable=False, default=0)
    seller_name = Column(Text, nullable=False)
    is_verified_seller = Column(Boolean, nullable=False, default=False)
    badge = Column(Text, nullable=True)                 # was `tag`: "Bestseller" | "New" | "Deal" | None
    image_url = Column(Text, nullable=False)
    semantic_tags = Column(Text, nullable=False)        # comma-separated, e.g. "fits your budget,verified seller"
    description = Column(Text, nullable=False)
    fit = Column(Text, nullable=False)                  # precomputed generic fit label ("Fits your budget" etc.)
    trust = Column(Integer, nullable=False)             # was `trust_score`
    search_terms = Column(Text, nullable=False)         # comma-separated keywords for Explore search
