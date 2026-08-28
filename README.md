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

Product and category photos are real photographs pulled from Picsum
(`https://picsum.photos/seed/<slug>/...`), seeded per item so each product
always shows the same photo. Brand marketing photography wasn't hotlinked
directly to avoid copyright/trademark issues — swap in your own product
photography or a licensed CDN when you have real listings.

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

## Notes / next steps

- Wallet balance, goals, orders, audit entries, and voice history in
  `lib/mockData.ts` are placeholders — connect to your FastAPI backend
  endpoints (`/api/v1/consent/evaluate`, wallet, goals, orders) to replace them.
- `components/b2b/PayloadSimulator.tsx` picks a random verdict client-side for
  demo purposes — point it at the real adapter endpoint when ready.
- Explore's semantic tag chips are currently cosmetic; wire them into
  `ExploreClient`'s filter logic the same way category and price are wired if
  you want them to actually narrow results.
