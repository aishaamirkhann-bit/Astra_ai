"""
Seed script — DB ko demo data se bharta hai, using the SAME `products` table
schema the Explore backend owns (id, title, badge, is_verified_seller,
semantic_tags, search_terms, fit, trust — all precomputed columns).

Run:  python -m app.db.seed
"""
import re
from datetime import datetime, timedelta, timezone

from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.product import Product
from app.models.wallet import Wallet
from app.models.goal import Goal
from app.models.order import Order, OrderStatus
from app.models.notification import Notification
from app.models.budget import ShoppingGoal, UserBudget
from app.models.seller_profile import SellerProfile
from app.models.seller_wallet import SellerWallet
from app.models.sales_goal import SalesGoal
from app.data import PRODUCTS as EXPLORE_PRODUCTS
from app.repository import product_repository


PRODUCTS_SEED = [
    dict(
        id="samsung-galaxy-s25-ultra", title="Samsung Galaxy S25 Ultra", category="Mobiles",
        price=314999, rating=4.8, total_reviews=2300, seller_name="TechBazaar Official",
        is_verified_seller=True, badge="Bestseller",
        image_url="/images/products/samsung-phone.jpg",
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
        image_url="/images/products/lenovo-laptop.jpg",
        semantic_tags="fits your budget,everyday laptop",
        description="A lightweight everyday laptop — Ryzen 5, 16GB RAM, 512GB SSD.",
        fit="Fits your budget", trust=91,
        search_terms="lenovo,ideapad,slim,laptop,ryzen",
    ),
    dict(
        id="sony-wh-1000xm5", title="Sony WH-1000XM5", category="Audio & Wearables",
        price=59999, rating=4.9, total_reviews=1500, seller_name="AudioNest",
        is_verified_seller=True, badge=None,
        image_url="/images/products/sony-headphones.jpg",
        semantic_tags="stretch manageable,noise cancelling",
        description="Industry-leading noise cancelling headphones.",
        fit="Stretch (Manageable)", trust=88,
        search_terms="sony,wh-1000xm5,headphones,noise cancelling",
    ),
    dict(
        id="apple-watch-series-9", title="Apple Watch Series 9", category="Wearables",
        price=134999, rating=4.6, total_reviews=1240, seller_name="iStore Lahore",
        is_verified_seller=True, badge=None,
        image_url="/images/products/apple-watch.jpg",
        semantic_tags="fits your budget,verified seller",
        description="Health and fitness tracking with a bright always-on display.",
        fit="Fits your budget", trust=94,
        search_terms="apple,watch,series 9,smartwatch",
    ),
    dict(
        id="xiaomi-14-civi", title="Xiaomi 14 Civi", category="Mobiles",
        price=124999, rating=4.3, total_reviews=210, seller_name="MobileWorld",
        is_verified_seller=False, badge="New",
        image_url="/images/products/xiaomi-phone.jpg",
        semantic_tags="fits your budget,new listing",
        description="A camera-focused mid-flagship with a compact design.",
        fit="Fits your budget", trust=82,
        search_terms="xiaomi,14 civi,mobile,phone",
    ),
    dict(
        id="dell-xps-13", title="Dell XPS 13", category="Laptops & Computers",
        price=289999, rating=4.7, total_reviews=860, seller_name="ComputerCity",
        is_verified_seller=True, badge=None,
        image_url="/images/products/lenovo-laptop.jpg",
        semantic_tags="stretch manageable,premium ultrabook",
        description="Premium ultrabook with an InfinityEdge display.",
        fit="Stretch (Manageable)", trust=93,
        search_terms="dell,xps,13,laptop,ultrabook",
    ),
]

EXTRA_PRODUCT_ROWS = [
    ("apple-iphone-15", "Apple iPhone 15", "Mobiles", 249999, "iStore Lahore", "apple-watch.jpg", 4.7, "Dynamic Island, 48MP camera and all-day battery."),
    ("samsung-galaxy-a35", "Samsung Galaxy A35 5G", "Mobiles", 89999, "TechBazaar Official", "samsung-phone.jpg", 4.6, "5G smartphone with a vivid AMOLED display and dependable battery."),
    ("xiaomi-redmi-note-13", "Xiaomi Redmi Note 13", "Mobiles", 54999, "MobileWorld", "xiaomi-phone.jpg", 4.4, "Large AMOLED display, fast charging and a high-resolution camera."),
    ("google-pixel-8a", "Google Pixel 8a", "Mobiles", 154999, "TechBazaar Official", "samsung-phone.jpg", 4.7, "Clean Android experience with smart photography features."),
    ("hp-pavilion-15", "HP Pavilion 15", "Laptops & Computers", 174999, "LaptopHub PK", "lenovo-laptop.jpg", 4.4, "Everyday laptop with a bright display and fast solid-state storage."),
    ("asus-vivobook-16", "ASUS VivoBook 16", "Laptops & Computers", 189999, "ComputerCity", "lenovo-laptop.jpg", 4.5, "Large-screen laptop for study, work and entertainment."),
    ("lenovo-legion-5", "Lenovo Legion 5", "Laptops & Computers", 329999, "LaptopHub PK", "lenovo-laptop.jpg", 4.8, "Performance laptop with discrete graphics for gaming and creation."),
    ("apple-macbook-air-m2", "Apple MacBook Air M2", "Laptops & Computers", 339999, "iStore Lahore", "lenovo-laptop.jpg", 4.8, "Lightweight notebook with Apple silicon and quiet all-day performance."),
    ("sony-wf-1000xm5", "Sony WF-1000XM5 Earbuds", "Audio & Wearables", 79999, "AudioNest", "sony-headphones.jpg", 4.7, "Compact noise-cancelling earbuds with clear calls."),
    ("jbl-flip-6", "JBL Flip 6 Speaker", "Audio & Wearables", 32999, "AudioNest", "sony-headphones.jpg", 4.5, "Portable waterproof Bluetooth speaker with rich sound."),
    ("apple-airpods-pro-2", "Apple AirPods Pro 2", "Audio & Wearables", 74999, "iStore Lahore", "sony-headphones.jpg", 4.8, "Wireless earbuds with active noise cancellation and adaptive audio."),
    ("samsung-galaxy-watch-6", "Samsung Galaxy Watch 6", "Audio & Wearables", 57999, "TechBazaar Official", "apple-watch.jpg", 4.4, "Smartwatch with fitness insights and a bright AMOLED screen."),
    ("silver-chain-classic", "Classic Sterling Silver Chain", "Jewelry", 12999, "StyleHouse PK", "apple-watch.jpg", 4.3, "Everyday sterling-silver chain with a polished finish."),
    ("gold-plated-hoop-earrings", "Gold-Plated Hoop Earrings", "Jewelry", 4999, "StyleHouse PK", "apple-watch.jpg", 4.2, "Lightweight hoops for everyday and occasion wear."),
    ("cotton-kurta-classic", "Classic Cotton Kurta", "Clothing & Fashion", 6499, "StyleHouse PK", "xiaomi-phone.jpg", 4.4, "Breathable cotton kurta with a comfortable regular fit."),
    ("everyday-running-sneakers", "Everyday Running Sneakers", "Clothing & Fashion", 11999, "StyleHouse PK", "lenovo-laptop.jpg", 4.5, "Lightweight cushioned shoes for walks, training and daily use."),
    ("hydrating-face-serum", "Hydrating Face Serum", "Makeup & Beauty", 3499, "BeautyHub PK", "apple-watch.jpg", 4.3, "Daily hydration serum for a simple skincare routine."),
    ("daily-sunscreen-spf50", "Daily Sunscreen SPF 50", "Makeup & Beauty", 2299, "BeautyHub PK", "apple-watch.jpg", 4.5, "Lightweight broad-spectrum sun protection for daily wear."),
    ("air-fryer-5l", "Digital Air Fryer 5L", "Home Appliances", 24999, "SmartLiving PK", "lenovo-laptop.jpg", 4.6, "Five-litre digital air fryer with easy temperature controls."),
    ("robot-vacuum-compact", "Compact Robot Vacuum", "Home Appliances", 49999, "SmartLiving PK", "xiaomi-phone.jpg", 4.2, "Scheduled floor cleaning with a compact docking station."),
    ("desk-lamp-led", "Adjustable LED Desk Lamp", "Home & Living", 3999, "SmartLiving PK", "apple-watch.jpg", 4.4, "Dimmable desk lamp with adjustable lighting modes."),
    ("ergonomic-office-chair", "Ergonomic Office Chair", "Furniture", 38999, "ComputerCity", "lenovo-laptop.jpg", 4.5, "Supportive adjustable chair for a home office setup."),
    ("anker-power-bank-20k", "Anker Power Bank 20,000mAh", "Electronics & Accessories", 13999, "TechBazaar Official", "samsung-phone.jpg", 4.7, "High-capacity portable charging with fast USB-C output."),
    ("logitech-mx-master-3s", "Logitech MX Master 3S Mouse", "Accessories", 29999, "ComputerCity", "lenovo-laptop.jpg", 4.8, "Quiet ergonomic wireless mouse for work and creative tasks."),
    ("wireless-charging-stand", "Wireless Charging Stand", "Electronics & Accessories", 7999, "MobileWorld", "samsung-phone.jpg", 4.2, "Convenient stand charger for compatible phones and earbuds."),
    ("portable-ssd-1tb", "Portable SSD 1TB", "Electronics & Accessories", 24999, "LaptopHub PK", "lenovo-laptop.jpg", 4.6, "Fast portable storage for backups, photos and project files."),
    ("embroidered-formal-lawn-suit", "Embroidered Formal Lawn Suit", "Dresses & Fashion", 18999, "Threads & Co.", "lawn-fabric.jpg", 4.8, "Three-piece embroidered lawn suit with a printed shirt, dyed trouser and chiffon dupatta."),
    ("elegant-party-wear-maxi", "Elegant Party Wear Maxi Dress", "Dresses & Fashion", 12499, "StyleHouse PK", "default-product.png", 4.7, "Flowing party-wear maxi with detailed neckline embroidery and a comfortable lining."),
    ("casual-cotton-kurti", "Casual Cotton Kurti", "Dresses & Fashion", 3499, "Threads & Co.", "lawn-fabric.jpg", 4.5, "Breathable everyday cotton kurti with a relaxed fit and subtle print."),
    ("oversized-aesthetic-hoodie", "Oversized Aesthetic Hoodie", "Dresses & Fashion", 5999, "StyleHouse PK", "default-product.png", 4.6, "Soft fleece-lined oversized hoodie for casual daily wear."),
    ("minimalist-leather-crossbody-bag", "Minimalist Leather Cross-Body Bag", "Dresses & Fashion", 4499, "StyleHouse PK", "default-product.png", 4.5, "Compact cross-body bag with adjustable strap and multiple organizer pockets."),
    ("matte-liquid-lipstick-set", "Matte Liquid Lipstick Set", "Makeup & Beauty", 2499, "BeautyHub PK", "lipstick-set.jpg", 4.6, "Long-wear matte liquid lipstick set with multiple everyday and occasion shades."),
    ("professional-eyeshadow-palette-24", "24-Color Professional Eyeshadow Palette", "Makeup & Beauty", 5999, "GlowBox Cosmetics", "default-product.png", 4.7, "Twenty-four blendable matte and shimmer shades for professional eye looks."),
    ("vitamin-c-glow-facial-serum", "Vitamin C Glow Facial Serum", "Makeup & Beauty", 3299, "BeautyHub PK", "default-product.png", 4.5, "Lightweight vitamin C facial serum for a bright, hydrated skincare routine."),
    ("minimalist-wooden-coffee-table", "Minimalist Wooden Coffee Table", "Furniture", 28999, "SmartLiving PK", "default-product.png", 4.7, "Compact engineered-wood coffee table with a durable finish and lower storage shelf."),
    ("ergonomic-velvet-office-chair", "Ergonomic Velvet Office Chair", "Furniture", 45999, "ComputerCity", "default-product.png", 4.6, "Height-adjustable velvet office chair with lumbar support and smooth-rolling wheels."),
    ("3d-self-adhesive-wall-stickers", "3D Self-Adhesive Wall Stickers", "Wallpapers", 1999, "SmartLiving PK", "default-product.png", 4.4, "Peel-and-stick 3D wall panels for quick, renter-friendly room refreshes."),
    ("bohemian-woven-tapestry", "Bohemian Woven Tapestry", "Home & Living", 3499, "Threads & Co.", "default-product.png", 4.6, "Decorative woven tapestry for bedrooms and living spaces."),
    ("compact-capsule-coffee-machine", "Compact Capsule Coffee Machine", "Home Appliances", 22999, "SmartLiving PK", "air-fryer.jpg", 4.5, "Countertop capsule coffee machine with one-touch brewing and a removable water tank."),
]


def _seller_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _ensure_wallet(db, user: User, balance: float = 0) -> Wallet:
    wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
    if wallet is None:
        wallet = Wallet(user_id=user.id, available_balance=balance)
        db.add(wallet)
        db.flush()
    return wallet


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        demo_buyers = [
            ("Aisha", "aisha@astra.ai", 135000),
            ("Hassan Ali", "hassan@astra.ai", 85000),
            ("Sara Ahmed", "sara@astra.ai", 62000),
            ("Omar Khan", "omar@astra.ai", 94000),
        ]
        buyer_users: list[User] = []
        for name, email, balance in demo_buyers:
            buyer = db.query(User).filter(User.email == email).first()
            if buyer is None:
                buyer = User(
                    name=name, email=email, hashed_password=hash_password("demo1234"),
                    preferred_language="Roman Urdu", role="buyer",
                )
                db.add(buyer)
                db.flush()
            buyer_users.append(buyer)
            _ensure_wallet(db, buyer, balance)

        # Keep a handful of realistic demo accounts for the Seller workspace.
        seller_names = {product["seller_name"] for product in PRODUCTS_SEED}
        seller_names.update(row[4] for row in EXTRA_PRODUCT_ROWS)
        seller_names.update(product["seller_name"] for product in EXPLORE_PRODUCTS)
        seller_emails: dict[str, str] = {}
        for seller_name in sorted(seller_names):
            slug = _seller_slug(seller_name)
            email = "seller@astra.ai" if seller_name == "TechBazaar Official" else f"{slug}@astra.ai"
            seller_emails[seller_name] = email
            seller = db.query(User).filter(User.email == email).first()
            if seller is None:
                seller = User(
                    name=seller_name, email=email, hashed_password=hash_password("demo1234"),
                    preferred_language="Roman Urdu", role="seller",
                )
                db.add(seller)
                db.flush()
            seller.role = "seller"
            _ensure_wallet(db, seller)
            profile = db.query(SellerProfile).filter(SellerProfile.user_id == seller.id).first()
            if profile is None:
                profile = SellerProfile(
                    user_id=seller.id, role="seller", trust_score=88,
                    compliance_status="verified", authenticity_score=91, total_revenue=0,
                    seller_key=slug,
                )
                db.add(profile)
                db.flush()
            elif profile.seller_key is None:
                profile.seller_key = slug
            if db.query(SellerWallet).filter(SellerWallet.seller_id == seller.id).first() is None:
                db.add(SellerWallet(seller_id=seller.id, available_balance=0, pending_payouts=0))

        product_rows = list(PRODUCTS_SEED)
        for index, (slug, title, category, price, seller_name, image, rating, description) in enumerate(EXTRA_PRODUCT_ROWS):
            product_rows.append({
                "id": slug,
                "title": title,
                "category": category,
                "price": price,
                "rating": rating,
                "total_reviews": 60 + index * 17,
                "seller_name": seller_name,
                "is_verified_seller": True,
                "badge": "Popular" if index % 4 == 0 else None,
                "image_url": f"/images/products/{image}",
                "semantic_tags": f"{category.lower()},verified seller,ASTRA Check",
                "description": description,
                "fit": "Fits your budget",
                "trust": 85 + (index * 5 % 14),
                "search_terms": f"{title.lower()}, {category.lower()}, {seller_name.lower()}",
                "stock_count": 4 + (index * 3 % 34),
                "brand": title.split()[0],
                "listing_status": "active",
            })

        known_product_ids = {product["id"] for product in product_rows}
        for index, product in enumerate(EXPLORE_PRODUCTS):
            if product["id"] in known_product_ids:
                continue
            product_rows.append({
                **product,
                "stock_count": 6 + (index * 5 % 30),
                "brand": product["title"].split()[0],
                "listing_status": "active",
                "semantic_tags": ", ".join(product["semantic_tags"]),
            })
            known_product_ids.add(product["id"])

        for product in product_rows:
            product["trust"] = min(98, max(85, int(product["trust"])))

        for p in product_rows:
            existing_product = db.query(Product).filter(Product.id == p["id"]).first()
            if existing_product is None:
                db.add(Product(**p, seller_id=_seller_slug(p["seller_name"])))
            else:
                existing_product.category = p["category"]
                existing_product.base_price = p["price"]
                existing_product.trust_score = p["trust"]
                existing_product.search_terms = p["search_terms"]
                existing_product.semantic_tags = p["semantic_tags"]
                existing_product.stock_count = p.get("stock_count", existing_product.stock_count)
        db.flush()
        db.commit()

        # The category browser uses the lightweight Explore catalog store.
        # Keep it populated from the same rows so seeded listings are visible
        # in buyer category pages as well as Seller Inventory.
        known_explore_ids = {product["id"] for product in EXPLORE_PRODUCTS}
        for product in product_rows:
            if product["id"] in known_explore_ids:
                continue
            EXPLORE_PRODUCTS.append({
                **product,
                "semantic_tags": [tag.strip() for tag in product["semantic_tags"].split(",") if tag.strip()],
            })
            known_explore_ids.add(product["id"])
        product_repository.initialize()

        # Add sample purchases and fulfillment states without moving wallet funds.
        now = datetime.now(timezone.utc)
        statuses = (OrderStatus.DELIVERED, OrderStatus.PENDING_APPROVAL, OrderStatus.SHIPPED, OrderStatus.CONFIRMED)
        for index, product_seed in enumerate(product_rows, start=1):
            product = db.get(Product, product_seed["id"])
            if product is None:
                continue
            for copy_index in range(2):
                order_ref = f"DEMO-26-{index:04d}-{copy_index + 1}"
                if db.query(Order).filter(Order.order_ref == order_ref).first():
                    continue
                order_status = statuses[(index + copy_index) % len(statuses)]
                quantity = 1 + (index + copy_index) % 2
                created_at = now - timedelta(days=(index * 3 + copy_index * 5) % 75)
                db.add(Order(
                    order_ref=order_ref,
                    user_id=buyer_users[(index + copy_index) % len(buyer_users)].id,
                    product_id=product.id,
                    quantity=quantity,
                    price=product.base_price * quantity,
                    status=order_status,
                    escrow_status="RELEASED" if order_status == OrderStatus.DELIVERED else "HELD",
                    approval_deadline=now + timedelta(days=2) if order_status == OrderStatus.PENDING_APPROVAL else None,
                    created_at=created_at,
                    shipped_at=created_at + timedelta(days=1) if order_status in {OrderStatus.SHIPPED, OrderStatus.DELIVERED} else None,
                    delivered_at=created_at + timedelta(days=3) if order_status == OrderStatus.DELIVERED else None,
                ))

        buyer = buyer_users[0]
        if db.query(Goal).filter(Goal.user_id == buyer.id, Goal.name == "Laptop Goal").first() is None:
            db.add(Goal(user_id=buyer.id, name="Laptop Goal", target_amount=180000, allocated_amount=45000))
        if db.query(UserBudget).filter(UserBudget.user_id == buyer.id).first() is None:
            db.add(UserBudget(user_id=buyer.id, monthly_limit=150000, current_spent=42000, rollover_savings=5000))

        sample_goals = [
            ("Samsung Galaxy S25 Ultra", 314999, "Mobiles", "/images/products/samsung-phone.jpg"),
            ("Lenovo IdeaPad Slim 5", 149999, "Laptops & Computers", "/images/products/lenovo-laptop.jpg"),
            ("Sony WH-1000XM5", 59999, "Audio & Wearables", "/images/products/sony-headphones.jpg"),
            ("Apple Watch Series 9", 134999, "Audio & Wearables", "/images/products/apple-watch.jpg"),
        ]
        for index, (title, target, category, image_url) in enumerate(sample_goals):
            if db.query(ShoppingGoal).filter(
                ShoppingGoal.user_id == buyer.id, ShoppingGoal.target_title == title,
            ).first() is None:
                db.add(ShoppingGoal(
                    user_id=buyer.id, target_title=title, target_price=target,
                    saved_amount=(index + 1) * 7500, category=category,
                    priority_level=("High" if index == 0 else "Medium"),
                    status="Active", image_url=image_url,
                ))

        for seller_name, email in seller_emails.items():
            seller = db.query(User).filter(User.email == email).first()
            if seller is None:
                continue
            for title, target, progress, deadline in (
                ("Monthly Revenue Target", 500000, 185000, "2026-11-30"),
                ("Verified Listing Growth", 20, 8, "2026-12-31"),
            ):
                if db.query(SalesGoal).filter(
                    SalesGoal.seller_id == seller.id, SalesGoal.target_title == title,
                ).first() is None:
                    db.add(SalesGoal(
                        seller_id=seller.id, target_title=title,
                        target_amount=target, current_amount=progress, deadline=deadline,
                    ))

        for user in buyer_users:
            message = "Welcome to ASTRA AI demo shopping. Explore verified listings and save products to My Goals."
            if db.query(Notification).filter(
                Notification.user_id == user.id, Notification.message == message,
            ).first() is None:
                db.add(Notification(user_id=user.id, message=message))

        db.commit()
        print(f"Demo seed complete: {len(product_rows)} catalog listings; two sample orders per demo product; four buyer accounts and {len(seller_emails)} seller accounts.")
        print("Demo buyer login:  aisha@astra.ai / demo1234")
        for seller_name, email in seller_emails.items():
            print(f"Demo seller login ({seller_name}): {email} / demo1234")
        print("Local OTP verification code: 123456. Demo purchases do not debit wallet balances.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
