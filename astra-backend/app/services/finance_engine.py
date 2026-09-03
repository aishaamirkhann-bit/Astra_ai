"""
FinanceEngine
-------------
"Financial Fit" check + product "fit" tag (Fits your budget / Stretch / Over budget).
Abhi rule-based hai (simple thresholds) — kal ko yahi function ML model ya
statistical model se replace ho sakta hai bina baaki app chhue.
"""
from app.models.wallet import Wallet


class FinanceEngine:
    STRETCH_MULTIPLIER = 1.15   # 15% se zyada balance se upar ho to "Stretch"

    @staticmethod
    def classify_fit(price: float, wallet: Wallet) -> str:
        if price <= wallet.available_balance:
            return "Fits your budget"
        if price <= wallet.available_balance * FinanceEngine.STRETCH_MULTIPLIER:
            return "Stretch (Manageable)"
        return "Over budget"

    @staticmethod
    def financial_fit_check(price: float, wallet: Wallet) -> tuple[str, str]:
        """Returns (verdict, detail) for the ASTRA Check widget."""
        fit = FinanceEngine.classify_fit(price, wallet)
        if fit == "Fits your budget":
            return "Good", "Within your budget"
        if fit == "Stretch (Manageable)":
            return "Warning", "Slightly above your ideal weekly spend"
        return "Bad", "Exceeds your available balance"
