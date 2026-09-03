"""
ConsentOrchestrator
--------------------
Yeh "Trust & Consent Layer" ka core hai — Finance + Trust + Price Fairness
teeno engines ka result le kar ek single overall verdict deta hai.
Yehi function AstraCheckWidget aur Pipeline dono ke liye source of truth hai.
"""
from app.models.product import Product
from app.models.wallet import Wallet
from app.schemas.astra_check import AstraCheckOut, CheckItem
from app.services.finance_engine import FinanceEngine
from app.services.trust_engine import TrustEngine
from app.services.price_fairness_engine import PriceFairnessEngine


class ConsentOrchestrator:
    @staticmethod
    def run_astra_check(product: Product, wallet: Wallet) -> AstraCheckOut:
        fin_verdict, fin_detail = FinanceEngine.financial_fit_check(product.price, wallet)
        trust_verdict, trust_detail = TrustEngine.seller_trust_check(product)
        price_verdict, price_detail = PriceFairnessEngine.price_fairness_check(product)

        checks = [
            CheckItem(label="Financial Fit", detail=fin_detail, verdict=fin_verdict),
            CheckItem(label="Seller Trust", detail=trust_detail, verdict=trust_verdict),
            CheckItem(label="Price Fairness", detail=price_detail, verdict=price_verdict),
        ]

        verdicts = {c.verdict for c in checks}
        if "Bad" in verdicts:
            overall = "NOT RECOMMENDED"
        elif "Warning" in verdicts:
            overall = "REVIEW SUGGESTED"
        else:
            overall = "GOOD TO BUY"

        return AstraCheckOut(checks=checks, overall_verdict=overall, product_slug=product.id)
