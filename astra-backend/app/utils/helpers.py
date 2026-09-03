from datetime import datetime, timezone


def as_aware_utc(dt: datetime) -> datetime:
    """
    SQLite doesn't persist tzinfo, so datetimes read back from it are naive
    even though we always write them in UTC. This normalizes any datetime
    to be UTC-aware before doing arithmetic with datetime.now(timezone.utc).
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def format_pkr(amount: float) -> str:
    """1234999 -> 'Rs. 1,234,999'"""
    return f"Rs. {amount:,.0f}"


def generate_ref(prefix: str, number: int) -> str:
    """('ORD', 88213) -> 'ORD-88213'"""
    return f"{prefix}-{number}"


def product_to_out(product, wallet=None):
    """
    Maps a Product row (partner's shared `products` table schema) to the
    ProductOut API shape the frontend expects. Central place so every
    endpoint (home, products, ai_assistant, astra_check) stays in sync.
    """
    from app.schemas.product import ProductOut
    from app.services.finance_engine import FinanceEngine

    fit = FinanceEngine.classify_fit(product.price, wallet) if wallet else product.fit

    return ProductOut(
        slug=product.id,
        name=product.title,
        price_display=format_pkr(product.price),
        price=product.price,
        rating=product.rating,
        total_reviews=product.total_reviews,
        tag=product.badge,
        fit=fit,
        seller=product.seller_name,
        verified_seller=product.is_verified_seller,
        trust=product.trust,
        category=product.category,
        image=product.image_url,
        description=product.description,
    )
