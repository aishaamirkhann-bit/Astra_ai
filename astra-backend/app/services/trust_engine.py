"""
TrustEngine
-----------
"Seller Trust" check. Combines product.trust_score + rating into a verdict.
Real system me isme order-history, return-rate, complaint-count wagera bhi
shamil honge — abhi trust_score column (0-100) hi source of truth hai.
"""
from app.models.product import Product


class TrustEngine:
    GOOD_THRESHOLD = 85
    WARNING_THRESHOLD = 60

    @staticmethod
    def seller_trust_check(product: Product) -> tuple[str, str]:
        score = product.trust
        if score >= TrustEngine.GOOD_THRESHOLD:
            return "Good", "Highly rated by buyers"
        if score >= TrustEngine.WARNING_THRESHOLD:
            return "Warning", "Trust score still building"
        return "Bad", "Limited buyer history — proceed with caution"
