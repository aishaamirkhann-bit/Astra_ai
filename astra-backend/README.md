# ASTRA AI — Backend (Home Page Slice)

FastAPI backend jo ASTRA AI frontend (Next.js) ke **Home page** ko power karta hai.
Baaki pages (Explore, Goals, Orders, Wallet, Messages, B2B) isi structure pe extend honge.

---

## 1. Tech Stack

| Layer          | Choice                                  |
|----------------|------------------------------------------|
| Framework      | FastAPI                                  |
| DB (dev)       | SQLite fallback (`DATABASE_URL`)         |
| DB (prod)      | PostgreSQL 18 + pgvector 0.8.x           |
| Migrations     | Alembic (Postgres schema authority)      |
| ORM            | SQLAlchemy 2.0                           |
| Auth           | JWT (python-jose) + bcrypt (passlib) + email OTP |
| Validation     | Pydantic v2                              |
| Realtime       | WebSocket + Redis pub/sub (in-process fallback) |
| Tests          | pytest (70 tests; `python -m pytest -q`) |

---

## 2. Folder Structure (A to Z)

```
astra-backend/
├── app/
│   ├── main.py                     # FastAPI app, CORS, lifespan, /health, /metrics
│   ├── data.py                     # catalog seed data (Unsplash image URLs)
│   │
│   ├── core/                       # cross-cutting config
│   │   ├── config.py                #   env-driven Settings (production safety guards)
│   │   ├── database.py              #   engine, SessionLocal, get_db(), Base
│   │   ├── rate_limit.py            #   in-process rate limiting (auth, consent, OTP)
│   │   └── security.py              #   password hashing + JWT create/decode
│   │
│   ├── models/                     # SQLAlchemy tables (DB schema)
│   │   ├── user.py, product.py, category.py, explore.py   #   catalog + users
│   │   ├── wallet.py, budget.py, goal.py                  #   money: ledger, budgets, goals
│   │   ├── deal.py                  #   Deal, DealReservation, MarketPriceHistory, SellerMetric
│   │   ├── order.py, cart.py        #   escrow orders + variant cart items
│   │   ├── trust.py                 #   seller verification + trust audit logs
│   │   ├── negotiation.py, chat.py, messaging.py          #   AI negotiation + DMs
│   │   └── pipeline.py, notification.py                   #   pipeline state + alerts
│   │
│   ├── schemas/                    # Pydantic I/O shapes (API contracts)
│   │
│   ├── services/                   # business logic — the "engines"
│   │   ├── deals_pipeline.py        #   deal evaluation, stock locks, market history
│   │   ├── astra_check_service.py   #   live inspection + trust scoring
│   │   ├── finance_engine.py, trust_engine.py, price_fairness_engine.py
│   │   ├── consent_orchestrator.py  #   combines engines → Overall Verdict
│   │   ├── recommendation_engine.py, explore.py           #   ranking + search
│   │   ├── budget.py, budget_agent.py                     #   budget alerts + goal matches
│   │   ├── pipeline_engine.py       #   builds ASTRA Decision Pipeline node states
│   │   ├── groq_negotiation.py      #   optional LLM seller agent (rules fallback)
│   │   ├── email_service.py         #   OTP delivery (Resend/SMTP; console in dev)
│   │   ├── deal_events.py           #   Redis/in-process deal event fan-out
│   │   └── audit.py                 #   immutable audit trail writes
│   │
│   ├── realtime/                   # WebSocket managers
│   │   └── deals_ws.py, pipeline_ws.py, wallet_ws.py, notifications_ws.py, messaging_ws.py
│   │
│   ├── api/
│   │   ├── deps.py                  #   strict JWT get_current_user, require_role()
│   │   └── v1/
│   │       ├── router.py            #   combines every endpoint router
│   │       └── endpoints/           #   auth, home, products, explore, deals, cart,
│   │                                #   wallet, goals, approval, orders, astra_check,
│   │                                #   negotiation, b2b, chat, messaging, seller,
│   │                                #   ai_assistant, pipeline, notifications
│   │
│   ├── db/
│   │   ├── seed.py                  #   idempotent demo data (users, products, wallets, sellers)
│   │   └── runtime_migrations.py    #   deals SQL migration runner (SQLite/dev path)
│   │
│   └── utils/
│       └── helpers.py               #   format_pkr(), product_to_out(), time helpers
│
├── alembic/ + alembic.ini          # Postgres migration authority (upgrade head at startup)
├── migrations/                     # hand-written SQL (deals realtime pipeline)
├── scripts/
│   └── validate_postgres.py         #   wallet/index/concurrency validation on Postgres
├── tests/                          # 70 pytest tests (auth, deals, wallet consent, messaging...)
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml              # local dev stack (postgres + redis + api)
└── README.md                       # ← you are here
```

---

## 3. Setup (local dev)

```bash
cd astra-backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # set DATABASE_URL + SECRET_KEY at least

# Migrations + seed (idempotent)
python -m alembic upgrade head  # PostgreSQL only; SQLite uses runtime migrations
python -m app.db.seed

# Run
uvicorn app.main:app --reload
```

API docs auto-generate at: **http://localhost:8000/docs**

Demo login: `aisha@astra.ai` / `demo1234`. Auth is strict JWT everywhere
(no anonymous fallback). Login returns an OTP challenge; in development
(`APP_ENV != production`) the code `123456` is accepted and the real OTP is
printed to the server console (`OTP_DEBUG_LOG`). Both conveniences are
force-disabled when `APP_ENV=production`, which also refuses to boot with the
default `SECRET_KEY`.

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

Deal checkout persists variant-aware `cart_items`. `POST /deals/{id}/reserve`
atomically reserves stock and creates a user-owned `pending_approval` order. An
approval expiry or cancellation releases the reservation exactly once and
restores inventory; approval moves the order into the reversible checkout
window. In production set `APP_ENV=production`, use a PostgreSQL `DATABASE_URL`
and TLS Redis `REDIS_URL`, apply the SQL migration, then run the API. SQLite and
the in-process WebSocket fan-out are development fallbacks only.

## 8. ASTRA Check verification module

ASTRA Check persists seller verification profiles, immutable trust decisions,
and cached aggregate metrics in `seller_verifications`, `trust_audit_logs`, and
`platform_trust_metrics`. The live inspection formula is
seller verification 40%, buyer-review authenticity sentiment 40%, and price
stability 20%. Scores below 75 immediately deactivate the associated Deal and
emit `deal_expired` through the same Redis/WebSocket channel used by Deals.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/astra-check/stats` | Platform trust and scan metrics |
| POST | `/api/v1/astra-check/inspect` | Product ID/seller live inspection |
| GET | `/api/v1/astra-check/seller/{id}` | Seller profile and audit history |
| POST | `/api/v1/astra-check/override` | Audited admin score override |
| POST | `/api/v1/astra-check/actions/flagged` | Flag and unlist a product |
| POST | `/api/v1/astra-check/actions/approved_for_deals` | Clear flag and push an eligible Deal |

Verification actions require the `admin` role when `APP_ENV=production`; the
seeded demo user is allowed only in development so the local dashboard remains
fully interactive.

## 9. Goals & Budget Agent

The Budget Agent stores monthly limits, financial shopping goals, and deduplicated
AI alerts in `user_budgets`, `shopping_goals`, and `budget_alerts`. Only active
Deals with an ASTRA Check score of 75 or higher can match a goal. Matches that
would exceed the remaining monthly balance also create a `Budget_Warning` with
an installment suggestion and are broadcast over `/ws/deals`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/goals/budget` | Budget overview, goals, savings, and alerts |
| PUT | `/api/v1/goals/budget` | Adjust the monthly spending limit |
| POST | `/api/v1/goals/create` | Create a financial shopping goal |
| PUT | `/api/v1/goals/{id}/update` | Deposit funds or adjust a goal |
| GET | `/api/v1/goals/matched-deals` | Verified, budget-aware Deal matches |

## 10. Next Steps

- Move the in-process authentication rate limiter to Redis for multi-instance enforcement.
- Wire managed observability (ship the JSON logs + `/metrics` to a collector) and schedule `scripts/backup_db.py` (e.g. cron) with off-site retention.
- Add a frontend Stripe Elements top-up flow consuming `/api/v1/payments/card/topup`.
- Configure real email/STT/SMS credentials (`RESEND_API_KEY` or SMTP, `STT_PROVIDER`) per deployment.
- The live market feed uses a free USD→PKR reference; a licensed per-category price feed can replace `app/services/market_feed.py` behind the same interface.

## 11. Current production architecture (August 2026)

The Docker stack targets **PostgreSQL 18 with pgvector**, Redis 7.4, FastAPI and
Next.js. PostgreSQL is the production schema authority; SQLite remains a local
compatibility/test option. On every deployment run migrations before API startup:

```powershell
python -m alembic current
python -m alembic upgrade head
python -m app.db.seed
```

Create migrations with `python -m alembic revision -m "description"` and review
generated DDL before applying it. The API refuses to start on PostgreSQL when its
revision is behind Alembic head. Back up production before downgrade operations.

Catalog semantic vectors use pgvector (`products.embedding vector(1536)`) and an
HNSW cosine index. FAISS/Sentence-Transformers are an optional offline alternative,
not an enabled backend path: install `faiss-cpu sentence-transformers` only for an
offline index job and record model/dimension metadata. The currently deployed
query path uses PostgreSQL and semantic tags, so documentation does not claim a
FAISS service is running.

### API groups

- `/api/v1/auth`: register, login, OTP, reset, profile, logout
- `/api/v1/products`, `/explore`, `/deals`, `/cart`: catalog and commerce
- `/api/v1/goals`, `/wallet`, `/approval`, `/orders`: finance and escrow
- `/api/v1/astra-check`, `/negotiation`, `/b2b`: trust and agent decisions
- `/api/v1/chat`, `/messaging`, `/notifications`: conversations and alerts
- `/api/v1/payments`: payment methods, Stripe card top-ups, webhook settlement
- `/api/v1/seller/inventory`: seller product CRUD
- `/api/v1/seller/orders`: seller escrow monitor and dispatch
- `/health`, `/metrics`: database health and latency diagnostics
- `/ws/deals`, `/ws/pipeline`, `/ws/wallet`, `/ws/notifications`, `/ws/messaging`: realtime events

### Environment variables

Required production values are `APP_ENV`, `SECRET_KEY`, `DATABASE_URL`,
`REDIS_URL`, and `FRONTEND_ORIGIN`. Email uses either `RESEND_API_KEY` or
`SMTP_HOST`, `SMTP_USER`/`SMTP_USERNAME`, and `SMTP_PASSWORD`. Optional Groq
negotiation uses `GROQ_API_KEY`, `GROQ_MODEL`, and `GROQ_TIMEOUT_SECONDS`.
Disable `OTP_DEBUG_LOG` in production. Optional server STT uses `STT_PROVIDER`
and `STT_API_KEY`; browser Web Speech STT requires no backend credential.

Backend verification: `python -m pytest -q`. Full browser verification is run
from the frontend root with `npx playwright test`.
