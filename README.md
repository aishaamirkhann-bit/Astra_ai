# ASTRA AI — Frontend

Production-ready Next.js (App Router) + Tailwind CSS frontend for **ASTRA AI —
The Trust & Financial-Consent Layer for Agentic Commerce**.

## Run locally

```bash
npm install
npm run dev
```

Open http://localhost:3000

## What's included

**11 pages**, all reachable from the sidebar / mobile menu:

| Page | Route | Notes |
|---|---|---|
| Home | `/` | Hero, ASTRA Check, AI Assistant, product grid, Decision Pipeline, Human Approval, Voice, Goals/Wallet |
| Explore | `/explore` | Text/voice/image search, category chips, semantic tags, live filtering |
| Categories | `/categories` | Mobiles, Laptops, Audio & Wearables, **Jewelry, Clothing & Fashion, Makeup & Beauty**, Home Appliances, Home & Living |
| Deals | `/deals` | Listings flagged Bestseller / Deal / New |
| ASTRA Check | `/astra-check` | Rules-vs-LLM breakdown, contradiction monitor, trust inspection |
| Goals & Wallet | `/goals` | Goal creator, affordability analyzer |
| Wallet | `/wallet` | Balance, ledger history, contribution schedule |
| Orders | `/orders` | 30s reversal countdown, audit log |
| Messages | `/messages` | Voice Copilot conversation history + text fallback |
| B2B Adapter | `/b2b` | UCP/ACP payload simulator |
| Product detail | `/product/[slug]` | Every product card across the app links here |

## Theme

**Light is the default theme**, with a sun/moon toggle in the top bar (persists
via `localStorage`). All color tokens (`base-*`, `ink-*`, `astra-cyan`,
`signal-*`) are CSS variables defined in `app/globals.css` under `:root`
(light) and `[data-theme="dark"]` (dark) — components never hardcode a theme,
so switching is instant and covers every page automatically.

## Responsive / mobile

- Sidebar collapses to a hamburger drawer (`components/MobileNav.tsx`) below
  the `lg` breakpoint.
- `ASTRA Voice` is available as a floating action button on **every page**
  (`components/GlobalVoiceFab.tsx`), in addition to the detailed voice card on
  Home and the full history on `/messages`.
- The top search bar is part of `TopBar`, rendered on every page via
  `PageShell` (or directly on Home).
- Grids, cards, and the pipeline bar reflow from 1–2 columns on mobile up to
  4–6 on desktop.

## Images

Product and category photos are real photographs stored locally in
`public/images/products/` and referenced as `/images/products/<file>.jpg` by
the backend seed data — no external image CDN is required. New seller listings
without a photo fall back to `public/images/products/default-product.png`.
Swap in your own product photography when you have real listings.

## Structure

```
app/
  layout.tsx                 Root layout — ThemeProvider + GlobalVoiceFab
  globals.css                 Light/dark CSS variables + .glass surface system
  page.tsx                     PAGE 1 — Home / Main Dashboard
  explore/page.tsx             PAGE 2 — Explore & Categories (search)
  categories/page.tsx          Category grid (Jewelry, Clothing, Makeup, etc.)
  deals/page.tsx                 Deals
  astra-check/page.tsx          PAGE 3 — ASTRA Check & Decision Pipeline
  goals/page.tsx                  PAGE 4 — Goals & Wallet
  wallet/page.tsx                  Wallet ledger
  orders/page.tsx                   PAGE 5 — Orders & Reversible Checkout
  messages/page.tsx                  Voice Copilot history
  b2b/page.tsx                        PAGE 6 — B2B Adapter Mode (dev route)
  product/[slug]/page.tsx              Product detail (dynamic route)

components/
  Sidebar.tsx, TopBar.tsx, PageShell.tsx, MobileNav.tsx   Global nav / shared layout
  ThemeProvider.tsx, ThemeToggle.tsx                       Light/dark theme system
  GlobalVoiceFab.tsx                                        Floating voice assistant (all pages)
  HeroBanner, AstraCheckWidget, AiAssistantWidget,
  ProductGrid, PipelineBar, HumanApprovalWidget,
  VoiceWidget, GoalsWalletRail                              Home dashboard widgets
  explore/                                                   Multi-modal search, category chips, semantic filters, results grid
  astra-check/                                               Rules-vs-LLM panel, contradiction monitor, trust inspection
  goals/                                                     Goal manager, affordability analyzer
  orders/                                                    Active orders + reversal countdown, audit log
  b2b/                                                       UCP/ACP payload simulator

lib/
  mockData.ts     Shared placeholder data (products, categories, orders, wallet ledger, voice history)
  navItems.ts     Shared sidebar/mobile-nav item list
```

## Design system

Tokens live in `tailwind.config.ts`, values in `app/globals.css`:
- `base-950…500` — surface depth scale (page → card → border), theme-aware
- `ink-100…700` — text scale, theme-aware
- `astra-indigo / astra-violet` — brand gradient, constant across themes
- `astra-cyan`, `signal-good / hold / reject` — theme-aware (vivid neon in
  dark mode, deeper/accessible tones in light mode) — reserved strictly for
  live states and verdicts, never used decoratively
- `.glass` / `.glass-hover` — the glassmorphism surface used by every card

## Notes

Core home, catalog, deals, goals, wallet, orders, B2B, chat, notifications and
seller-dashboard flows call the FastAPI backend. `lib/mockData.ts` remains only
for static category/tag presentation data. Semantic search filters are handled
by `/api/v1/explore/search`.

## Current development architecture (August 2026)

The frontend now contains buyer and seller experiences. Canonical routes include
`/`, `/explore`, `/categories`, `/deals`, `/product/[slug]`, `/goals`, `/wallet`,
`/orders`, `/messages`, `/notifications`, `/astra-check`, `/b2b`, and
`/seller/dashboard`. The legacy `/my-goals` URL permanently redirects to `/goals`.

Set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env.local`. Authentication
uses an HttpOnly cookie set after password plus email OTP verification.

### Voice search / STT

`lib/useSpeechRecognition.ts` wraps the browser Web Speech API and supports both
`SpeechRecognition` and Chrome's `webkitSpeechRecognition`. Recognition is
performed by the browser; availability and language quality depend on the browser
and operating system. Uploaded audio can instead use backend `POST /api/v1/chat/stt`.

### Vector search status

Production catalog vectors are stored in PostgreSQL/pgvector (`vector(1536)` with
an HNSW cosine index). FAISS and Sentence-Transformers are not runtime dependencies
in this repository today. For an optional offline index, install
`faiss-cpu sentence-transformers`, encode catalog text with a selected model, and
keep model name/dimension alongside the index. Do not mix those vectors with the
1536-dimensional pgvector column unless their dimensions and embedding model match.

### Playwright E2E

The Chromium suite covers OTP login, product negotiation, and escrow dispute:

```powershell
npx playwright install chromium
npx playwright test
npx playwright show-report
```

`playwright.config.ts` starts the API and Next.js dev server when they are not
already running. Failure screenshots, videos, and traces are retained.
