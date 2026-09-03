"""
RecommendationEngine
---------------------
"Recommended For You" grid + AI Assistant's single best-match card.

NOTE: the shared `products` table (owned by the Explore backend) has no
`is_recommended` flag, so ranking is purely trust + rating based here.
Baad me collaborative-filtering / embeddings-based model isi ke andar plug hoga.
"""
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.wallet import Wallet
from app.services.finance_engine import FinanceEngine


class RecommendationEngine:
    @staticmethod
    def get_recommended(db: Session, limit: int = 4) -> list[Product]:
        return (
            db.query(Product)
            .order_by(Product.trust.desc(), Product.rating.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def best_match(db: Session, wallet: Wallet) -> Product | None:
        """Single top pick for the AI Assistant widget — highest trust score
        among products that currently fit the user's budget."""
        candidates = (
            db.query(Product)
            .order_by(Product.trust.desc(), Product.rating.desc())
            .limit(20)
            .all()
        )
        for product in candidates:
            if FinanceEngine.classify_fit(product.price, wallet) == "Fits your budget":
                return product
        return candidates[0] if candidates else None
