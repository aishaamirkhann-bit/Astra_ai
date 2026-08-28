// Keyword-matched real photos (Creative Commons, via LoremFlickr) — the
// keyword string decides *what* the photo shows, so it can be made to match
// each product/category instead of being a random unrelated placeholder.
const img = (keywords: string, size = 600) => `https://loremflickr.com/${size}/${size}/${keywords}`;

export const PRODUCTS = [
  {
    slug: "samsung-galaxy-s25-ultra",
    name: "Samsung Galaxy S25 Ultra",
    price: "Rs. 314,999",
    rating: 4.8,
    tag: "Bestseller",
    fit: "Fits your budget",
    seller: "TechBazaar Official",
    trust: 96,
    category: "Mobiles",
    image: img("smartphone,samsung"),
    description:
      "Flagship Android phone with a 200MP camera system, titanium frame, and on-device AI features — evaluated against your budget and this seller's trust history before ASTRA recommends it.",
  },
  {
    slug: "lenovo-ideapad-slim-5",
    name: "Lenovo IdeaPad Slim 5",
    price: "Rs. 149,999",
    rating: 4.5,
    tag: null,
    fit: "Fits your budget",
    seller: "LaptopHub PK",
    trust: 91,
    category: "Laptops & Computers",
    image: img("laptop,lenovo"),
    description:
      "A lightweight everyday laptop — Ryzen 5, 16GB RAM, 512GB SSD. Priced below the market average for this configuration according to ASTRA's cross-marketplace check.",
  },
  {
    slug: "sony-wh-1000xm5",
    name: "Sony WH-1000XM5",
    price: "Rs. 59,999",
    rating: 4.9,
    tag: null,
    fit: "Stretch (Manageable)",
    seller: "AudioNest",
    trust: 88,
    category: "Audio & Wearables",
    image: img("headphones,sony"),
    description:
      "Industry-leading noise cancelling headphones. Sits slightly above your ideal weekly spend, but well within a manageable stretch per ASTRA's affordability analyzer.",
  },
  {
    slug: "apple-watch-series-9",
    name: "Apple Watch Series 9",
    price: "Rs. 134,999",
    rating: 4.6,
    tag: null,
    fit: "Fits your budget",
    seller: "iStore Lahore",
    trust: 94,
    category: "Audio & Wearables",
    image: img("smartwatch,applewatch"),
    description:
      "Health and fitness tracking with a bright always-on display. Verified seller, strong buyer ratings, and comfortably within your available balance.",
  },
  {
    slug: "xiaomi-14-civi",
    name: "Xiaomi 14 Civi",
    price: "Rs. 124,999",
    rating: 4.3,
    tag: "New",
    fit: "Fits your budget",
    seller: "MobileWorld",
    trust: 82,
    category: "Mobiles",
    image: img("smartphone,xiaomi"),
    description:
      "A camera-focused mid-flagship with a compact design. New listing — trust score still building as more verified buyers check in.",
  },
  {
    slug: "dell-xps-13",
    name: "Dell XPS 13",
    price: "Rs. 289,999",
    rating: 4.7,
    tag: null,
    fit: "Stretch (Manageable)",
    seller: "ComputerCity",
    trust: 93,
    category: "Laptops & Computers",
    image: img("laptop,dell"),
    description:
      "Premium ultrabook with an InfinityEdge display. A stretch against your weekly cap, but manageable if spread across an installment plan.",
  },
  {
    slug: "anker-soundcore-q45",
    name: "Anker Soundcore Q45",
    price: "Rs. 24,999",
    rating: 4.4,
    tag: "Deal",
    fit: "Fits your budget",
    seller: "GadgetVault",
    trust: 85,
    category: "Audio & Wearables",
    image: img("headphones,wireless"),
    description:
      "Budget noise-cancelling headphones flagged as a deal — priced meaningfully below the market average for this model.",
  },
  {
    slug: "samsung-galaxy-watch-6",
    name: "Samsung Galaxy Watch 6",
    price: "Rs. 78,999",
    rating: 4.5,
    tag: null,
    fit: "Fits your budget",
    seller: "TechBazaar Official",
    trust: 96,
    category: "Audio & Wearables",
    image: img("smartwatch,wearable"),
    description:
      "Wear OS smartwatch with body composition tracking. Same highly-trusted seller as your S25 Ultra listing.",
  },
  {
    slug: "gold-plated-jhumka-earrings",
    name: "Gold-Plated Jhumka Earrings",
    price: "Rs. 8,499",
    rating: 4.6,
    tag: "Bestseller",
    fit: "Fits your budget",
    seller: "Zeenat Jewels",
    trust: 90,
    category: "Jewelry",
    image: img("earrings,goldjewelry"),
    description:
      "Handcrafted gold-plated jhumkas with antique finish. Verified artisan seller with strong repeat-buyer ratings.",
  },
  {
    slug: "embroidered-lawn-3pc-suit",
    name: "Embroidered Lawn 3-Piece Suit",
    price: "Rs. 6,990",
    rating: 4.4,
    tag: "New",
    fit: "Fits your budget",
    seller: "Threads & Co.",
    trust: 87,
    category: "Clothing & Fashion",
    image: img("embroidery,fabric"),
    description:
      "Unstitched lawn 3-piece with digital print and embroidered neckline. Seasonal bestseller, priced at market average.",
  },
  {
    slug: "matte-liquid-lipstick-set",
    name: "Matte Liquid Lipstick Set (6-Pack)",
    price: "Rs. 3,299",
    rating: 4.5,
    tag: "Deal",
    fit: "Fits your budget",
    seller: "GlowBox Cosmetics",
    trust: 84,
    category: "Makeup & Beauty",
    image: img("lipstick,cosmetics"),
    description:
      "Long-wear matte finish, 6 everyday shades. Flagged as a deal — priced below the market average for comparable sets.",
  },
] as const;

export type Product = (typeof PRODUCTS)[number];

export const CATEGORIES = [
  { slug: "mobiles", name: "Mobiles", image: img("smartphone"), count: 214 },
  { slug: "laptops-computers", name: "Laptops & Computers", image: img("laptop"), count: 132 },
  { slug: "audio-wearables", name: "Audio & Wearables", image: img("headphones"), count: 176 },
  { slug: "jewelry", name: "Jewelry", image: img("jewelry,gold"), count: 98 },
  { slug: "clothing", name: "Clothing & Fashion", image: img("fashion,clothing"), count: 341 },
  { slug: "makeup-beauty", name: "Makeup & Beauty", image: img("makeup,cosmetics"), count: 187 },
  { slug: "home-appliances", name: "Home Appliances", image: img("kitchenappliance"), count: 156 },
  { slug: "households", name: "Households", image: img("household,home"), count: 0 },
  { slug: "home-living", name: "Home & Living", image: img("homedecor,interior"), count: 122 },
] as const;

export const EXPLORE_CATEGORY_TAGS = [
  "Mobiles",
  "Laptops & Computers",
  "Audio & Wearables",
  "Jewelry",
  "Clothing & Fashion",
  "Makeup & Beauty",
  "Home Appliances",
  "Households",
] as const;

export const PIPELINE_STAGES = [
  { key: "intent", label: "Intent Received", ms: 12 },
  { key: "finance", label: "Finance Rules", ms: 42 },
  { key: "contradiction", label: "Contradiction Check", ms: 31 },
  { key: "trust", label: "Trust Engine", ms: 68 },
  { key: "approval", label: "Human Approval", ms: null },
  { key: "checkout", label: "Reversible Checkout", ms: null },
] as const;

export const ORDERS = [
  {
    id: "ORD-88213",
    item: "Samsung Galaxy S25 Ultra",
    slug: "samsung-galaxy-s25-ultra",
    price: "Rs. 314,999",
    status: "Reversal window open",
    secondsLeft: 18,
  },
  {
    id: "ORD-88190",
    item: "Sony WH-1000XM5",
    slug: "sony-wh-1000xm5",
    price: "Rs. 59,999",
    status: "Confirmed",
    secondsLeft: 0,
  },
  {
    id: "ORD-88176",
    item: "Apple Watch Series 9",
    slug: "apple-watch-series-9",
    price: "Rs. 134,999",
    status: "Confirmed",
    secondsLeft: 0,
  },
] as const;

export const AUDIT_LOG = [
  {
    id: "EVT-4471",
    type: "consent.evaluate",
    endpoint: "/api/v1/consent/evaluate",
    verdict: "approve",
    actor: "orchestrator-agent",
    time: "14:02:11.203",
  },
  {
    id: "EVT-4470",
    type: "human.approval",
    endpoint: "/api/v1/approval/confirm",
    verdict: "approved",
    actor: "user:aisha.k",
    time: "14:01:58.010",
  },
  {
    id: "EVT-4469",
    type: "trust.score",
    endpoint: "/api/v1/trust/evaluate",
    verdict: "hold",
    actor: "trust-engine",
    time: "14:01:44.876",
  },
  {
    id: "EVT-4468",
    type: "consent.evaluate",
    endpoint: "/api/v1/consent/evaluate",
    verdict: "reject",
    actor: "orchestrator-agent",
    time: "13:57:02.512",
  },
] as const;

export const WALLET_LEDGER = [
  { id: "TXN-9012", label: "Weekly contribution — Laptop Goal", amount: 8000, type: "credit", date: "Aug 14, 2026" },
  { id: "TXN-9011", label: "Purchase — Apple Watch Series 9", amount: -134999, type: "debit", date: "Aug 10, 2026" },
  { id: "TXN-9010", label: "Wallet top-up", amount: 200000, type: "credit", date: "Aug 5, 2026" },
  { id: "TXN-9009", label: "Weekly contribution — Umrah Fund", amount: 25000, type: "credit", date: "Aug 1, 2026" },
  { id: "TXN-9008", label: "Purchase — Anker Soundcore Q45", amount: -24999, type: "debit", date: "Jul 27, 2026" },
] as const;

export const VOICE_HISTORY = [
  {
    id: "conv-1",
    time: "Today, 2:02 PM",
    you: "ASTRA, laptop 150k ke under dikhao",
    astra:
      "Found 3 laptops under Rs. 150,000 that fit your budget — the Lenovo IdeaPad Slim 5 is the best-rated verified option.",
  },
  {
    id: "conv-2",
    time: "Today, 11:40 AM",
    you: "Is this seller trustworthy?",
    astra:
      "TechBazaar Official has a 96% trust score with 4.8★ average across 2,300+ verified orders — no red flags on file.",
  },
  {
    id: "conv-3",
    time: "Yesterday, 6:15 PM",
    you: "Mera budget check karo",
    astra:
      "Rs. 135,000 available to spend this month, with your Laptop Goal 25% funded. You're within your weekly spend cap.",
  },
] as const;
