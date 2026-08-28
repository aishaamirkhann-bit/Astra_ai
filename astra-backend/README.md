# ASTRA AI — Backend (Home Page Slice)

FastAPI backend jo ASTRA AI frontend (Next.js) ke **Home page** ko power karta hai.
Baaki pages (Explore, Goals, Orders, Wallet, Messages, B2B) isi structure pe extend honge.

---

## 1. Tech Stack

| Layer          | Choice                                  |
|----------------|------------------------------------------|
| Framework      | FastAPI                                  |
| DB (dev)       | SQLite (`astra.db`, zero setup)          |
| DB (prod)      | PostgreSQL (sirf `DATABASE_URL` badlo)   |
| ORM            | SQLAlchemy 2.0                           |
| Auth           | JWT (python-jose) + bcrypt (passlib)     |
| Validation     | Pydantic v2                              |
| Realtime       | WebSocket (pipeline live updates)        |

---

## 2. Folder Structure (A to Z)

```
astra-backend/
├── app/
│   ├── main.py                     # FastAPI app, CORS, startup hook
│   │
│   ├── core/                       # cross-cutting config
│   │   ├── config.py                #   env-driven Settings (.env se load hota hai)
│   │   ├── database.py              #   engine, SessionLocal, get_db(), Base
│   │   └── security.py              #   password hashing + JWT create/decode
│   │
│   ├── models/                     # SQLAlchemy tables (DB schema)
│   │   ├── user.py                  #   User (name, email, password, language)
│   │   ├── product.py               #   Product (price, rating, trust_score, seller...)
│   │   ├── wallet.py                #   Wallet + WalletLedgerEntry
│   │   ├── goal.py                  #   Goal (target/allocated amount)
│   │   ├── order.py                 #   Order + OrderStatus enum (approval/reversal window)
│   │   ├── pipeline.py              #   PipelineRun, PipelineStageLog, AuditLog
│   │   └── notification.py          #   Notification (TopBar bell)
│   │
│   ├── schemas/                    # Pydantic I/O shapes (API contracts)
│   │   ├── user.py, product.py, astra_check.py, ai_assistant.py,
│   │   │   approval.py, pipeline.py, goal.py, home.py
│   │   └── (each mirrors a shape already used in frontend/lib/mockData.ts)
│   │
│   ├── services/                   # business logic — the "engines"
│   │   ├── finance_engine.py        #   Financial Fit / budget classification
│   │   ├── trust_engine.py          #   Seller Trust scoring
│   │   ├── price_fairness_engine.py #   Price vs. category market average
│   │   ├── consent_orchestrator.py  #   combines 3 engines → Overall Verdict
│   │   ├── recommendation_engine.py #   "Recommended For You" + AI best-match
│   │   └── pipeline_engine.py       #   builds ASTRA Decision Pipeline node states
│   │
│   ├── api/
│   │   ├── deps.py                  #   get_current_user, shared dependencies
│   │   └── v1/
│   │       ├── router.py            #   combines every endpoint router
│   │       └── endpoints/
│   │           ├── auth.py           #   POST /login, GET /me
│   │           ├── home.py           #   GET /home  (single aggregate call)
│   │           ├── products.py       #   GET /products/recommended, /products/{slug}
│   │           ├── astra_check.py    #   GET /astra-check, /astra-check/{slug}
│   │           ├── ai_assistant.py   #   GET /ai-assistant/suggestion, POST /add-to-cart
│   │           ├── approval.py       #   GET /pending, POST /approve, POST /cancel
│   │           ├── pipeline.py       #   GET /pipeline/state
│   │           ├── goals.py          #   GET /goals/rail, GET /goals
│   │           └── notifications.py  #   GET /notifications/unread-count
│   │
│   ├── websockets/
│   │   └── pipeline_ws.py           #   WS /ws/pipeline?order_ref=... (live push)
│   │
│   ├── db/
│   │   └── seed.py                  #   demo data matching frontend mockData.ts
│   │
│   └── utils/
│       └── helpers.py               #   format_pkr(), generate_ref()
│
├── tests/                          # pytest tests (starter placed here)
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md                       # ← you are here
```

---

## 3. Setup (local dev)

```bash
cd astra-backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # edit SECRET_KEY at least

# Seed demo data (creates astra.db + Aisha user + products + wallet + goal + a pending order)
python -m app.db.seed

# Run
uvicorn app.main:app --reload
```

API docs auto-generate at: **http://localhost:8000/docs**

Demo login: `aisha@astra.ai` / `demo1234`
(Home page endpoints also work **without** logging in during dev — `get_current_user`
falls back to the seeded "Aisha" user when no token is sent. Remove that fallback
in `app/api/deps.py` before going to production.)

---

## 4. Home Page Endpoints

| Method | Path                              | Powers (frontend component)         |
|--------|-------------------------------------|--------------------------------------|
| GET    | `/api/v1/home`                     | **Whole page in one call**           |
| GET    | `/api/v1/products/recommended`     | `ProductGrid.tsx`                    |
| GET    | `/api/v1/products/{slug}`          | Product detail                       |
| GET    | `/api/v1/astra-check`              | `AstraCheckWidget.tsx`               |
| GET    | `/api/v1/ai-assistant/suggestion`  | `AiAssistantWidget.tsx`              |
| POST   | `/api/v1/ai-assistant/add-to-cart` | Widget's "Add to Cart" button        |
| GET    | `/api/v1/approval/pending`         | `HumanApprovalWidget.tsx` countdown  |
| POST   | `/api/v1/approval/approve`         | "Approve Transaction" button         |
| POST   | `/api/v1/approval/cancel`          | "Cancel & Refund" button             |
| GET    | `/api/v1/pipeline/state`           | `PipelineBar.tsx`                    |
| WS     | `/ws/pipeline?order_ref=...`       | Live pipeline push (optional)        |
| GET    | `/api/v1/goals/rail`               | `GoalsWalletRail.tsx`                |
| GET    | `/api/v1/notifications/unread-count`| TopBar bell red-dot                 |
| POST   | `/api/v1/auth/login`               | Login                                |
| GET    | `/api/v1/auth/me`                  | Current user                         |

`VoiceWidget.tsx` is UI-only mic toggle on Home (no network call) — actual
speech-to-text will be wired when the `/messages` page backend is built.

---

## 5. Connecting the Next.js Frontend

In `astra-ai/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

Example fetch (replace mock data import in `page.tsx` components):
```ts
const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/home`, {
  credentials: "include",
});
const data = await res.json();
```

Backend already has CORS enabled for `http://localhost:3000` (see `.env` → `FRONTEND_ORIGIN`).

---

## 6. Shared `products` Table (Home + Explore backend)

`app/models/product.py` matches the Explore backend's Postgres schema exactly
(`app/db/shared_products_table.sql` has the raw DDL for reference). Key points:

- **`id` is text** (e.g. `"samsung-galaxy-s25-ultra"`) — it doubles as the old
  "slug" used in frontend routes like `/product/[slug]`. No separate slug column.
- **No `is_recommended` flag** — "Recommended For You" ranks all products by
  `trust` + `rating` instead (see `recommendation_engine.py`).
- **`fit` and `trust` are stored columns**, precomputed on the Explore side.
  The Home page uses the *stored* `fit` for product cards, but recalculates a
  **live, wallet-specific** Financial Fit for the ASTRA Check widget via
  `FinanceEngine` — these are two different concepts that happen to share a name.
- Field renames vs. earlier drafts: `name`→`title`, `tag`→`badge`,
  `trust_score`→`trust`, `slug`→`id`. All mapped back to the original frontend
  field names in `app/utils/helpers.py::product_to_out()` — one function, used
  by every endpoint, so the two backends can never drift on how a row is shaped.
- **Run migrations/seeds against the SAME database** as the Explore backend
  (same `DATABASE_URL`). Seeding twice is safe — `seed.py` skips products that
  already exist by `id`.

## 7. Real-time Deals pipeline

Production uses PostgreSQL with pgvector plus Redis:

```bash
docker compose up --build
psql "$DATABASE_URL" -f migrations/20260829_deals_realtime_pipeline.sql
```

The AI Trust Agent evaluates the rolling 30-day market average every
`DEAL_SCAN_INTERVAL_SECONDS`. A deal is active only when its listing price is
at least 15% below that average and its weighted trust score is at least 75.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/deals` | Active paginated deal summaries |
| GET | `/api/v1/deals/{id}/details` | Modal data, variants, trust, price history |
| POST | `/api/v1/deals/{id}/reserve` | Row-locked stock reservation |
| WS | `/ws/deals` | Redis-backed deal and inventory events |

Redis channel `astra:deals` emits `deal_updated`, `stock_changed`, and
`deal_expired`. If Redis is unavailable in local development, the API keeps
working and broadcasts to WebSocket clients in-process. Apply the SQL migration
before deploying against an existing PostgreSQL/Supabase database.

The migration enables `vector`, stores `products.embedding` as
`vector(1536)`, and creates an HNSW cosine-similarity index. Supabase projects
must have the Vector extension enabled. Checkout obtains a Redis distributed
lock per deal and then a PostgreSQL `SELECT ... FOR UPDATE` row lock; both are
required in multi-instance production deployments. Every Trust Agent decision
and stock reservation is written to `deal_audit_logs` with its scoring inputs.

## 8. Next Steps (beyond Home page)

- Add Alembic for real migrations (`alembic init alembic`) once schema stabilizes.
- Build `/explore`, `/goals`, `/orders`, `/wallet`, `/messages`, `/b2b` endpoint modules
  the same way — one `endpoints/*.py` + matching `schemas/*.py` per page.
- Replace the dev-only "no token = demo user Aisha" fallback in `app/api/deps.py`
  with a proper login flow once the frontend has a login screen.
- Swap `CATEGORY_AVERAGE_PRICE` static dict in `price_fairness_engine.py` for a
  real market-data source.
- Add a `Cart` model + endpoints when the cart/checkout flow is built (currently
  `ai_assistant.add_to_cart` is a stub).
