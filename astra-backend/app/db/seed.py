"""
Seed script — DB ko demo data se bharta hai, using the SAME `products` table
schema the Explore backend owns (id, title, badge, is_verified_seller,
semantic_tags, search_terms, fit, trust — all precomputed columns).

Run:  python -m app.db.seed
"""
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

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

# A deterministic, repeatable catalog for local demos. Each template carries a
# category-specific image and seller; variants provide 1,000 unique listings
# without copying misleading product photos between unrelated categories.
_GENERATED_TEMPLATES = [
    ("Audio & Wearables", "Headphones", "Sony Studio Wireless Headphones", "AudioNest", 28999, "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=85", "Wireless over-ear headphones with cushioned ear cups and balanced everyday sound."),
    ("Audio & Wearables", "Earbuds", "Soundcore True Wireless Earbuds", "AudioNest", 12999, "https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?auto=format&fit=crop&w=900&q=85", "Compact Bluetooth earbuds with a pocket charging case and clear call microphones."),
    ("Audio & Wearables", "Smartwatches", "Astra Fit AMOLED Smartwatch", "GadgetVault", 18999, "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=85", "Fitness smartwatch with an always-on display, activity tracking and interchangeable strap."),
    ("Audio & Wearables", "Speakers", "JBL Portable Bluetooth Speaker", "AudioNest", 15999, "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=900&q=85", "Portable Bluetooth speaker with room-filling sound and a durable travel-ready body."),
    ("Electronics & Computing", "Laptops", "Lenovo IdeaPad Everyday Laptop", "LaptopHub PK", 139999, "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=85", "Everyday laptop configured for study, office work and video calls."),
    ("Electronics & Computing", "Tablets", "Samsung Galaxy Wi-Fi Tablet", "TechBazaar Official", 64999, "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?auto=format&fit=crop&w=900&q=85", "Lightweight tablet for reading, streaming and everyday productivity."),
    ("Electronics & Computing", "Monitors", "Dell IPS Full HD Monitor", "ComputerCity", 42999, "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=900&q=85", "Slim-bezel IPS monitor with a clear Full HD panel for work and home setups."),
    ("Electronics & Computing", "Keyboards", "Logitech Mechanical Keyboard", "ComputerCity", 16999, "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=900&q=85", "Comfortable mechanical keyboard with responsive keys for work and gaming."),
    ("Electronics & Computing", "Phones", "Xiaomi Redmi 5G Smartphone", "MobileWorld", 74999, "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=900&q=85", "5G smartphone with a vivid display, capable camera and fast-charging battery."),
    ("Electronics & Computing", "Accessories", "Anker USB-C Power Bank", "GadgetVault", 8999, "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?auto=format&fit=crop&w=900&q=85", "High-capacity USB-C power bank for dependable charging while travelling."),
    ("Clothing & Fashion", "Shalwar Kameez", "Gul Ahmed Cotton Shalwar Kameez", "Threads & Co.", 8999, "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=900&q=85", "Breathable cotton shalwar kameez with a neat everyday cut and soft finish."),
    ("Clothing & Fashion", "Kurtas", "Khaadi Printed Cotton Kurta", "StyleHouse PK", 5499, "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=900&q=85", "Printed cotton kurta designed for comfortable daily and semi-formal wear."),
    ("Clothing & Fashion", "Jackets", "Outfitters Lightweight Jacket", "StyleHouse PK", 11999, "https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=900&q=85", "Lightweight layered jacket with practical pockets and a versatile fit."),
    ("Clothing & Fashion", "Dresses", "Sapphire Occasion Dress", "Threads & Co.", 14999, "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=900&q=85", "Occasion dress with a flowing silhouette and carefully finished details."),
    ("Clothing & Fashion", "Shoes", "Servis Everyday Walking Shoes", "StyleHouse PK", 6999, "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85", "Lightweight cushioned shoes for everyday walking and casual outfits."),
    ("Home Decor", "Rugs", "Handwoven Persian-Style Area Rug", "Bazaar Living", 28999, "https://images.unsplash.com/photo-1600166898405-da9535204843?auto=format&fit=crop&w=900&q=85", "Decorative woven area rug with a detailed pattern for living spaces."),
    ("Home Decor", "Lamps", "Modern Ceramic Table Lamp", "Bazaar Living", 9999, "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=85", "Warm ambient table lamp with a simple shade for bedside or lounge use."),
    ("Home Decor", "Curtains", "Linen Blend Room Curtains", "SmartLiving PK", 7999, "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=900&q=85", "Linen-blend curtains that soften daylight and complement neutral interiors."),
    ("Home Decor", "Wall Art", "Framed Minimalist Wall Art Set", "Bazaar Living", 5999, "https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?auto=format&fit=crop&w=900&q=85", "Ready-to-hang framed art prints for a coordinated home display."),
    ("Home Decor", "Vases", "Handcrafted Ceramic Table Vase", "Bazaar Living", 4499, "https://images.unsplash.com/photo-1578500494198-246f612d3b3d?auto=format&fit=crop&w=900&q=85", "Hand-finished ceramic vase suited to shelves, consoles and dining tables."),
    ("Furniture", "Chairs", "Ergonomic Mesh Office Chair", "SmartLiving PK", 32999, "https://images.unsplash.com/photo-1505797149-43b006a668e0?auto=format&fit=crop&w=900&q=85", "Adjustable office chair with breathable mesh and supportive seating."),
    ("Furniture", "Tables", "Solid Wood Coffee Table", "Bazaar Living", 25999, "https://images.unsplash.com/photo-1499933374294-4584851497cc?auto=format&fit=crop&w=900&q=85", "Compact wood coffee table with a smooth finish for lounge areas."),
    ("Furniture", "Sofas", "Modern Three-Seat Fabric Sofa", "SmartLiving PK", 114999, "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=900&q=85", "Three-seat sofa with supportive cushions and durable woven upholstery."),
    ("Furniture", "Beds", "Upholstered Queen Bed Frame", "SmartLiving PK", 89999, "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=85", "Queen bed frame with a padded headboard and sturdy support structure."),
    ("Furniture", "Shelving", "Modular Wooden Bookcase", "Bazaar Living", 21999, "https://images.unsplash.com/photo-1594620302200-9a762244a156?auto=format&fit=crop&w=900&q=85", "Modular shelving for books, storage baskets and display pieces."),
    ("Jewelry", "Earrings", "Zeenat Gold-Plated Jhumka Earrings", "Zeenat Jewels", 6999, "https://images.unsplash.com/photo-1617038220319-276d3cfab638?auto=format&fit=crop&w=900&q=85", "Occasion-ready gold-plated earrings with a detailed traditional finish."),
    ("Jewelry", "Necklaces", "Sterling Silver Pendant Necklace", "Zeenat Jewels", 8999, "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?auto=format&fit=crop&w=900&q=85", "Polished sterling silver pendant necklace for everyday styling."),
    ("Jewelry", "Bracelets", "Classic Gold-Tone Chain Bracelet", "Zeenat Jewels", 4999, "https://images.unsplash.com/photo-1611591437281-460bfbe1220a?auto=format&fit=crop&w=900&q=85", "Lightweight chain bracelet with a secure clasp and polished finish."),
    ("Jewelry", "Rings", "Minimal Sterling Silver Ring", "Zeenat Jewels", 3499, "https://images.unsplash.com/photo-1605100804763-247f67b3557e?auto=format&fit=crop&w=900&q=85", "Simple sterling silver ring with a smooth, comfortable band."),
    ("Accessories", "Bags", "Leather Crossbody Shoulder Bag", "StyleHouse PK", 10999, "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85", "Compact crossbody bag with an adjustable strap and organized interior."),
    ("Accessories", "Wallets", "Slim Leather Card Wallet", "StyleHouse PK", 3999, "https://images.unsplash.com/photo-1627123424574-724758594e93?auto=format&fit=crop&w=900&q=85", "Slim leather wallet with practical card slots and a compact profile."),
    ("Accessories", "Belts", "Reversible Leather Belt", "StyleHouse PK", 4999, "https://images.unsplash.com/photo-1624222247344-550fb8ed6f8d?auto=format&fit=crop&w=900&q=85", "Reversible belt with a clean buckle for formal and casual outfits."),
    ("Accessories", "Scarves", "Soft Woven Modal Scarf", "Threads & Co.", 2999, "https://images.unsplash.com/photo-1601924994987-69e26d50dc26?auto=format&fit=crop&w=900&q=85", "Soft woven scarf with a lightweight drape for year-round layering."),
]

_DEMO_SELLERS = [
    "TechBazaar Official", "LaptopHub PK", "AudioNest", "GadgetVault",
    "MobileWorld", "ComputerCity", "Threads & Co.", "StyleHouse PK",
    "Bazaar Living", "SmartLiving PK", "Zeenat Jewels", "Persian Craft House",
]
_DEMO_ORIGINS = ("PK", "CN", "IR", "AE")
_DEMO_VARIANTS = (
    "Classic", "Graphite", "Pearl", "Sand", "Forest", "Midnight", "Stone",
    "Rose", "Indigo", "Olive", "Cloud", "Copper", "Sage", "Cobalt", "Ivory",
    "Slate", "Amber", "Burgundy", "Silver", "Teal",
)


def _build_generated_products(count: int = 1000) -> list[dict]:
    rows: list[dict] = []
    for index in range(count):
        category, subcategory, model, default_seller, base_price, image_url, description = _GENERATED_TEMPLATES[index % len(_GENERATED_TEMPLATES)]
        edition = index // len(_GENERATED_TEMPLATES)
        variant = _DEMO_VARIANTS[edition % len(_DEMO_VARIANTS)]
        title = f"{model} {variant} Series {edition // len(_DEMO_VARIANTS) + 1:02d}"
        seller_name = default_seller if edition % 3 else _DEMO_SELLERS[(index // len(_GENERATED_TEMPLATES) + index) % len(_DEMO_SELLERS)]
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        rows.append({
            "id": f"astra-demo-{slug}-{index + 1:04d}",
            "title": title,
            "category": category,
            "subcategory": subcategory,
            "origin_country": _DEMO_ORIGINS[index % len(_DEMO_ORIGINS)],
            "price": round(base_price * (0.84 + (index % 33) * 0.01), 2),
            "seller_price_floor": round(base_price * (0.84 + (index % 33) * 0.01) * 0.88, 2),
            "rating": round(4.0 + (index % 10) * 0.1, 1),
            "total_reviews": 18 + (index * 37 % 880),
            "seller_name": seller_name,
            "is_verified_seller": True,
            "badge": ("Popular" if index % 11 == 0 else None),
            "image_url": image_url,
            "semantic_tags": f"{category.lower()},{subcategory.lower()},verified seller,demo catalog",
            "description": f"{description} Variant: {variant.lower()} finish, selected from the Astra demo catalog.",
            "fit": "Fits your budget",
            "trust": 85 + index % 14,
            "search_terms": f"{title.lower()}, {category.lower()}, {subcategory.lower()}, {seller_name.lower()}",
            "stock_count": 5 + index % 40,
            "brand": model.split()[0],
            "listing_status": "active",
        })
    return rows


GENERATED_PRODUCT_ROWS = _build_generated_products()

_SEEDED_IMAGE_RULES = [
    ("speaker", "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=900&q=85"),
    ("soundbar", "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=900&q=85"),
    ("headphone", "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=85"),
    ("earbud", "https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?auto=format&fit=crop&w=900&q=85"),
    ("airpod", "https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?auto=format&fit=crop&w=900&q=85"),
    ("watch", "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=85"),
    ("tablet", "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?auto=format&fit=crop&w=900&q=85"),
    ("monitor", "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=900&q=85"),
    ("keyboard", "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=900&q=85"),
    ("laptop", "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=85"),
    ("computer", "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=85"),
    ("phone", "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=900&q=85"),
    ("smartphone", "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=900&q=85"),
    ("earring", "https://images.unsplash.com/photo-1617038220319-276d3cfab638?auto=format&fit=crop&w=900&q=85"),
    ("jhumka", "https://images.unsplash.com/photo-1617038220319-276d3cfab638?auto=format&fit=crop&w=900&q=85"),
    ("necklace", "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?auto=format&fit=crop&w=900&q=85"),
    ("bracelet", "https://images.unsplash.com/photo-1611591437281-460bfbe1220a?auto=format&fit=crop&w=900&q=85"),
    ("ring", "https://images.unsplash.com/photo-1605100804763-247f67b3557e?auto=format&fit=crop&w=900&q=85"),
    ("sofa", "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=900&q=85"),
    ("couch", "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=900&q=85"),
    ("chair", "https://images.unsplash.com/photo-1505797149-43b006a668e0?auto=format&fit=crop&w=900&q=85"),
    ("table", "https://images.unsplash.com/photo-1499933374294-4584851497cc?auto=format&fit=crop&w=900&q=85"),
    ("desk", "https://images.unsplash.com/photo-1499933374294-4584851497cc?auto=format&fit=crop&w=900&q=85"),
    ("rug", "https://images.unsplash.com/photo-1600166898405-da9535204843?auto=format&fit=crop&w=900&q=85"),
    ("carpet", "https://images.unsplash.com/photo-1600166898405-da9535204843?auto=format&fit=crop&w=900&q=85"),
    ("lamp", "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=85"),
    ("curtain", "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=900&q=85"),
    ("dress", "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=900&q=85"),
    ("kurta", "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=900&q=85"),
    ("lawn", "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=900&q=85"),
    ("suit", "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=900&q=85"),
    ("shirt", "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=900&q=85"),
    ("jacket", "https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=900&q=85"),
    ("shoe", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85"),
    ("sneaker", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=85"),
    ("bag", "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85"),
    ("wallet", "https://images.unsplash.com/photo-1627123424574-724758594e93?auto=format&fit=crop&w=900&q=85"),
    ("belt", "https://images.unsplash.com/photo-1624222247344-550fb8ed6f8d?auto=format&fit=crop&w=900&q=85"),
    ("scarf", "https://images.unsplash.com/photo-1601924994987-69e26d50dc26?auto=format&fit=crop&w=900&q=85"),
    ("lipstick", "https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=900&q=85"),
    ("serum", "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?auto=format&fit=crop&w=900&q=85"),
    ("beauty", "https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=900&q=85"),
    ("makeup", "https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=900&q=85"),
    ("air fryer", "https://images.unsplash.com/photo-1585515320310-259814833e62?auto=format&fit=crop&w=900&q=85"),
    ("appliance", "https://images.unsplash.com/photo-1585515320310-259814833e62?auto=format&fit=crop&w=900&q=85"),
    ("coffee machine", "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=900&q=85"),
]


def _seed_image_url(title: str, category: str) -> str:
    text = f"{title} {category}".lower()
    if "wh-1000" in text or "soundcore" in text:
        return "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=85"
    for keyword, image_url in _SEEDED_IMAGE_RULES:
        if keyword in text:
            return image_url
    category_images = {
        "audio & wearables": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=900&q=85",
        "wearables": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=85",
        "mobiles": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=900&q=85",
        "laptops & computers": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=85",
        "electronics & computing": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=900&q=85",
        "electronics & accessories": "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?auto=format&fit=crop&w=900&q=85",
        "clothing & fashion": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=900&q=85",
        "dresses & fashion": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=900&q=85",
        "home decor": "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=900&q=85",
        "home & living": "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=900&q=85",
        "furniture": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=900&q=85",
        "jewelry": "https://images.unsplash.com/photo-1617038220319-276d3cfab638?auto=format&fit=crop&w=900&q=85",
        "accessories": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85",
        "home appliances": "https://images.unsplash.com/photo-1585515320310-259814833e62?auto=format&fit=crop&w=900&q=85",
        "makeup & beauty": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?auto=format&fit=crop&w=900&q=85",
        "wallpapers": "https://images.unsplash.com/photo-1600210492486-724fe5c67fb0?auto=format&fit=crop&w=900&q=85",
    }
    return category_images.get(category.lower(), "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=900&q=85")


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
        seller_names.update(product["seller_name"] for product in GENERATED_PRODUCT_ROWS)
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
                )
                db.add(profile)
                db.flush()
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

        product_rows.extend(GENERATED_PRODUCT_ROWS)
        for product in product_rows:
            if str(product.get("image_url", "")).startswith("/images/products/"):
                product["image_url"] = _seed_image_url(product["title"], product["category"])

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

        # Explore-only rows are copied after the initial normalization pass;
        # normalize their legacy local placeholders as well before persistence.
        for product in product_rows:
            if str(product.get("image_url", "")).startswith("/images/products/"):
                product["image_url"] = _seed_image_url(product["title"], product["category"])

        origins_by_id = {item["id"]: item.get("origin_country", "PK") for item in EXPLORE_PRODUCTS}
        for product in product_rows:
            product.setdefault("origin_country", origins_by_id.get(product["id"], "PK"))

        for product in product_rows:
            product["trust"] = min(98, max(85, int(product["trust"])))

        for p in product_rows:
            existing_product = db.query(Product).filter(Product.id == p["id"]).first()
            if existing_product is None:
                db.add(Product(**p, seller_id=_seller_slug(p["seller_name"])))
            else:
                existing_product.title = p["title"]
                existing_product.category = p["category"]
                existing_product.origin_country = p.get("origin_country", "PK")
                existing_product.base_price = p["price"]
                existing_product.seller_price_floor = p.get("seller_price_floor", existing_product.seller_price_floor)
                existing_product.rating = p["rating"]
                existing_product.total_reviews = p["total_reviews"]
                existing_product.seller_name = p["seller_name"]
                existing_product.image_url = p["image_url"]
                existing_product.trust_score = p["trust"]
                existing_product.search_terms = p["search_terms"]
                existing_product.semantic_tags = p["semantic_tags"]
                existing_product.stock_count = p.get("stock_count", existing_product.stock_count)
                existing_product.subcategory = p.get("subcategory", existing_product.subcategory)
                existing_product.brand = p.get("brand", existing_product.brand)
                existing_product.listing_status = p.get("listing_status", existing_product.listing_status)
        db.flush()

        # The category browser uses the lightweight Explore catalog store.
        # Keep it populated from the same rows so seeded listings are visible
        # in buyer category pages as well as Seller Inventory.
        known_explore_ids = {product["id"] for product in EXPLORE_PRODUCTS}
        for product in product_rows:
            if product["id"] in known_explore_ids:
                existing_explore_product = next((item for item in EXPLORE_PRODUCTS if item["id"] == product["id"]), None)
                if existing_explore_product is not None:
                    existing_explore_product["image_url"] = product["image_url"]
                    existing_explore_product["origin_country"] = product.get("origin_country", "PK")
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
        demo_order_products = product_rows[: len(PRODUCTS_SEED) + len(EXTRA_PRODUCT_ROWS)]
        for index, product_seed in enumerate(demo_order_products, start=1):
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
        seeded_ids = [row["id"] for row in product_rows]
        seeded_count = db.query(Product).filter(Product.id.in_(seeded_ids)).count()
        database_count = db.query(Product).count()
        print(f"Demo seed complete: {seeded_count} of {database_count} database catalog listings are in the seed set; {len(demo_order_products)} curated products receive sample orders; four buyer accounts and {len(seller_emails)} seller accounts.")
        print("Seeded catalog rows by category (database rows / distinct image URLs):")
        category_stats = db.query(
            Product.category,
            func.count(Product.id),
            func.count(func.distinct(Product.image_url)),
        ).filter(Product.id.in_(seeded_ids)).group_by(Product.category).order_by(Product.category).all()
        for category, count, image_count in category_stats:
            print(f"  {category}: {count} / {image_count}")
        print("Demo buyer login:  aisha@astra.ai / demo1234")
        for seller_name, email in seller_emails.items():
            print(f"Demo seller login ({seller_name}): {email} / demo1234")
        print("Local OTP verification code: 123456. Demo purchases do not debit wallet balances.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
