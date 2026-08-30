"""
Seed script — DB ko demo data se bharta hai, using the SAME `products` table
schema the Explore backend owns (id, title, badge, is_verified_seller,
semantic_tags, search_terms, fit, trust — all precomputed columns).

Run:  python -m app.db.seed
"""
from datetime import datetime, timedelta, timezone

from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.product import Product
from app.models.wallet import Wallet, WalletLedgerEntry
from app.models.goal import Goal
from app.models.order import Order, OrderStatus
from app.models.notification import Notification


PRODUCTS_SEED = [
    dict(
        id="samsung-galaxy-s25-ultra", title="Samsung Galaxy S25 Ultra", category="Mobiles",
        price=314999, rating=4.8, total_reviews=2300, seller_name="TechBazaar Official",
        is_verified_seller=True, badge="Bestseller",
        image_url="https://loremflickr.com/600/600/smartphone,samsung",
        semantic_tags="fits your budget,verified seller,flagship",
        description="Flagship Android phone with a 200MP camera system, titanium frame, "
                     "and on-device AI features.",
        fit="Fits your budget", trust=96,
        search_terms="samsung,galaxy,s25,ultra,mobile,phone,android",
    ),
    dict(
        id="lenovo-ideapad-slim-5", title="Lenovo IdeaPad Slim 5", category="Laptops & Computers",
        price=149999, rating=4.5, total_reviews=910, seller_name="LaptopHub PK",
        is_verified_seller=True, badge=None,
        image_url="https://loremflickr.com/600/600/laptop,lenovo",
        semantic_tags="fits your budget,everyday laptop",
        description="A lightweight everyday laptop — Ryzen 5, 16GB RAM, 512GB SSD.",
        fit="Fits your budget", trust=91,
        search_terms="lenovo,ideapad,slim,laptop,ryzen",
    ),
    dict(
        id="sony-wh-1000xm5", title="Sony WH-1000XM5", category="Audio & Wearables",
        price=59999, rating=4.9, total_reviews=1500, seller_name="AudioNest",
        is_verified_seller=True, badge=None,
        image_url="https://loremflickr.com/600/600/headphones,sony",
        semantic_tags="stretch manageable,noise cancelling",
        description="Industry-leading noise cancelling headphones.",
        fit="Stretch (Manageable)", trust=88,
        search_terms="sony,wh-1000xm5,headphones,noise cancelling",
    ),
    dict(
        id="apple-watch-series-9", title="Apple Watch Series 9", category="Wearables",
        price=134999, rating=4.6, total_reviews=1240, seller_name="iStore Lahore",
        is_verified_seller=True, badge=None,
        image_url="https://loremflickr.com/600/600/smartwatch,applewatch",
        semantic_tags="fits your budget,verified seller",
        description="Health and fitness tracking with a bright always-on display.",
        fit="Fits your budget", trust=94,
        search_terms="apple,watch,series 9,smartwatch",
    ),
    dict(
        id="xiaomi-14-civi", title="Xiaomi 14 Civi", category="Mobiles",
        price=124999, rating=4.3, total_reviews=210, seller_name="MobileWorld",
        is_verified_seller=False, badge="New",
        image_url="https://loremflickr.com/600/600/smartphone,xiaomi",
        semantic_tags="fits your budget,new listing",
        description="A camera-focused mid-flagship with a compact design.",
        fit="Fits your budget", trust=82,
        search_terms="xiaomi,14 civi,mobile,phone",
    ),
    dict(
        id="dell-xps-13", title="Dell XPS 13", category="Laptops & Computers",
        price=289999, rating=4.7, total_reviews=860, seller_name="ComputerCity",
        is_verified_seller=True, badge=None,
        image_url="https://loremflickr.com/600/600/laptop,dell",
        semantic_tags="stretch manageable,premium ultrabook",
        description="Premium ultrabook with an InfinityEdge display.",
        fit="Stretch (Manageable)", trust=93,
        search_terms="dell,xps,13,laptop,ultrabook",
    ),
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == "aisha@astra.ai").first():
            print("Seed data already exists — skipping.")
            return

        # --- User ---
        user = User(
            name="Aisha",
            email="aisha@astra.ai",
            hashed_password=hash_password("demo1234"),
            preferred_language="Roman Urdu",
            role="buyer",
        )
        db.add(user)
        db.flush()

        # A second demo account so seller-only endpoints/UI can be tested too.
        seller = User(
            name="Demo Seller",
            email="seller@astra.ai",
            hashed_password=hash_password("demo1234"),
            preferred_language="Roman Urdu",
            role="seller",
        )
        db.add(seller)
        db.flush()
        db.add(Wallet(user_id=seller.id, available_balance=0))

        # --- Wallet + ledger ---
        wallet = Wallet(user_id=user.id, available_balance=135000)
        db.add(wallet)
        db.flush()
        db.add_all([
            WalletLedgerEntry(wallet_id=wallet.id, description="Weekly contribution - Laptop Goal",
                               amount=8000, txn_type="Credit"),
            WalletLedgerEntry(wallet_id=wallet.id, description="Purchase - Apple Watch Series 9",
                               amount=134999, txn_type="Debit"),
            WalletLedgerEntry(wallet_id=wallet.id, description="Wallet top-up",
                               amount=200000, txn_type="Credit"),
        ])

        # --- Goal ---
        db.add(Goal(user_id=user.id, name="Laptop Goal", target_amount=180000, allocated_amount=45000))

        # --- Products (skip any that already exist, since Explore backend owns this table too) ---
        for p in PRODUCTS_SEED:
            if not db.query(Product).filter(Product.id == p["id"]).first():
                db.add(Product(**p))
        db.flush()

        # --- A pending order, so HumanApprovalWidget + PipelineBar have something to show ---
        featured = db.query(Product).filter(Product.id == "samsung-galaxy-s25-ultra").first()
        db.add(Order(
            order_ref="ORD-88213",
            user_id=user.id,
            product_id=featured.id,
            price=featured.price,
            status=OrderStatus.PENDING_APPROVAL,
            approval_deadline=datetime.now(timezone.utc) + timedelta(seconds=27),
        ))

        # --- Notification ---
        db.add(Notification(user_id=user.id, message="Your Samsung Galaxy S25 Ultra order needs approval."))

        db.commit()
        print("Seed complete.")
        print("Demo buyer login:  aisha@astra.ai / demo1234")
        print("Demo seller login: seller@astra.ai / demo1234")
        print("Both now require an emailed OTP after the password step (see /auth/login -> /auth/verify-otp).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
