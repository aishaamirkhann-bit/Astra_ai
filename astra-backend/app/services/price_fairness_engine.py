"""
PriceFairnessEngine
--------------------
"Price Fairness" check — is product ka price market average se compare karta hai.
Abhi category-wise ek static average table hai (demo data); production me yeh
ek scraping/aggregation service se live market average lega.
"""
from app.models.product import Product

# Demo category-average table (PKR). Replace with a live market-data service later.
CATEGORY_AVERAGE_PRICE = {
    "Mobiles": 160000,
    "Laptops & Computers": 190000,
    "Audio & Wearables": 70000,   # headphones-style price band
    "Wearables": 130000,          # smartwatches — separate band, was wrongly lumped with headphones
    "Jewelry": 9000,
    "Clothing & Fashion": 7500,
    "Makeup & Beauty": 3500,
    "Home Appliances": 40000,
    "Home & Living": 25000,
}


class PriceFairnessEngine:
    @staticmethod
    def price_fairness_check(product: Product) -> tuple[str, str]:
        avg = CATEGORY_AVERAGE_PRICE.get(product.category)
        if not avg:
            return "Warning", "Not enough market data for this category"

        if product.price <= avg * 0.95:
            return "Good", "Better than market avg."
        if product.price <= avg * 1.1:
            return "Warning", "Around market average"
        return "Bad", "Priced above market average"
