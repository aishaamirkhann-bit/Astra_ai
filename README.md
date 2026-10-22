# Astra AI

**A multilingual commerce copilot with explicit buyer consent at the point of purchase.**

Astra AI is a Next.js and FastAPI commerce application for buyers and sellers in Pakistan and selected cross-border markets. It combines a catalogue, search and recommendations, product and order workflows, seller tools, optional AI-provider integrations, and a server-authoritative checkout flow. Its intended mission is to make product discovery more accessible while keeping purchase authorization under the buyer's control.

> **Implementation note:** This README describes the code currently in this repository. Several interfaces are prototypes, deterministic simulations, provider-dependent integrations, or English-first UI. In particular, this repository does not establish production-grade ML quality, a measured sub-500ms voice SLA, a live international settlement corridor, or complete native translation of every screen.

## Contents

- [At a glance](#at-a-glance)
- [Architecture and repository map](#architecture-and-repository-map)
- [Feature and language status](#feature-and-language-status)
- [Buyer experience](#buyer-experience)
- [Seller workspace](#seller-workspace)
- [AI and decision-support services](#ai-and-decision-support-services)
- [Financial architecture and safeguards](#financial-architecture-and-safeguards)
- [API and realtime surface](#api-and-realtime-surface)
- [Configuration and local development](#configuration-and-local-development)
- [Verification status](#verification-status)
- [Known limitations and production work](#known-limitations-and-production-work)

## At a glance

| Area | Current implementation |
|---|---|
| Web application | Next.js App Router, React, TypeScript, Tailwind CSS |
| API | FastAPI, Pydantic, SQLAlchemy |
| Persistence | PostgreSQL intended for deployment; SQLite supported by local/runtime migration paths |
| Catalogue | Shared product table, seller inventory operations, deterministic search/ranking, optional visual and vector signals |
| Authentication | JWT cookie/session flow, email OTP, optional Google OAuth |
| Commerce | Buyer cart, stock reservation, checkout sessions, consent authorization, PKR wallet ledger, reversible order window |
| Languages | Nine selectable/detectable locale families with partial phrase normalization and provider-assisted response translation |
| Integrations | Groq-compatible vision/STT/negotiation configuration, Meta WhatsApp Cloud API configuration, external display FX-rate feed |
| UI localization | English-first. The selector changes locale-aware behavior and selected copy; it does not translate every page |

Counts and test badges from older documentation were removed because they were not a reliable description of the current worktree. This README task inspected source and did not run the test suite.

## Architecture and repository map

```text
app/                         Next.js pages and layouts
components/                  Buyer, seller, product, chat, voice, and dashboard UI
lib/                         API client, shared types, region settings, voice helpers
astra-backend/app/api/       REST endpoints and API router
astra-backend/app/realtime/  WebSocket handlers
astra-backend/app/services/  Commerce, search, risk, localization, and AI adapters
astra-backend/app/models/    SQLAlchemy persistence models
astra-backend/app/schemas/   Pydantic request and response contracts
astra-backend/alembic/       PostgreSQL migrations
astra-backend/tests/         Backend tests
e2e/                         Playwright scenarios
```

The browser calls `/api/v1/*` REST routes and several WebSocket routes. `app/main.py` mounts the v1 router and realtime routers, exposes `/health` and `/metrics`, and configures database startup. The product table is shared by buyer catalogue and seller inventory; seller analytics, goals, and seller-wallet records use seller-scoped data/models.

### Main frontend routes

The sidebar/top bar provide navigation, account/role mode, region selection, language selection, display currency, theme, notifications, search, and voice entry. A country modal opens on first load if no country is stored (or a signed-in account country can be used). Currency selection is display-only: PKR is the checkout/base-wallet currency. The UI retrieves and caches indicative PKR conversion rates from a public exchange-rate endpoint; on missing rates it falls back to PKR display.

### Product detail and discovery panels (continued from above)

## Product Deep Research

### The problem and ASTRA's solution

Product research is scattered across separate product-specification pages, reviews, store listings, warranty pages, and seller-reputation searches. Buyers must gather and compare those sources themselves. ASTRA's **Product Deep Research** brings sourced product and seller findings together on the product detail page, so buyers can review one report before deciding.

### How it works

1. A buyer opens an ASTRA product detail page.
2. ASTRA looks up the product by its existing product ID/slug, then runs parallel searches for official specifications, expert reviews, user complaints, prices, alternatives, warranty/after-sales information, recalls, and (when listed) seller reputation and return policies.
3. ASTRA fetches and extracts text from a limited number of public search results. Search-result text is treated as untrusted data, not instructions.
4. The configured Groq model synthesizes a structured report and cites only URLs returned by the search provider. Unsupported claims remain empty or `null`; insufficient seller evidence produces an `unknown` verdict.
5. The product page presents overview, specifications, reviews, price comparison, alternatives, warranty, red flags/buying advice, and a cited seller report.

### Architecture

```text
Product detail (product ID/slug)
        │ authenticated GET /api/v1/products/{id}/research
        ▼
FastAPI product endpoint ── SQLAlchemy Product lookup
        │                     └─ existing Explore catalog fallback
        ▼
Parallel Tavily or Brave searches ── safe, bounded public-page extraction
        ▼
Existing Groq chat-completions setup ── Pydantic validation and source filtering
        ▼
Process-local TTL cache ── cited report in the product detail UI
```

The catalog lookup is compatible with both the SQLAlchemy commerce product and the existing Explore repository; it does not merge or rewrite either catalog. Research is cached in each backend process for the configured TTL. A deployment restart or another worker may have a separate cache.

### Setup

Configure the backend environment in `astra-backend/.env` (see [`astra-backend/.env.example`](./astra-backend/.env.example)):

```dotenv
SEARCH_PROVIDER=tavily
SEARCH_API_KEY=your-search-provider-key
RESEARCH_CACHE_TTL_HOURS=24
```

`SEARCH_PROVIDER` accepts `tavily` or `brave`. Keep the key on the backend only; do not put it in a `NEXT_PUBLIC_*` variable. AI synthesis reuses ASTRA's existing `GROQ_API_KEY` (or `VISION_API_KEY`) and `GROQ_MODEL` settings. Without search or synthesis credentials, the endpoint returns an explicit partial report instead of inventing facts.

### API

```http
GET /api/v1/products/samsung-galaxy-s25-ultra/research
GET /api/v1/products/samsung-galaxy-s25-ultra/research?refresh=true
Authorization: Bearer <ASTRA session token>
```

The endpoint also accepts a product slug as `{id}`; `refresh=true` bypasses the cached report.

### Limitations

- Results depend on public pages indexed by the selected search provider; private, login-only, or blocked pages may not be available.
- Report accuracy and coverage depend on the linked sources. Check those sources before relying on a price, product specification, warranty, recall, or review summary.
- Seller names can be ambiguous, and online evidence can be sparse. ASTRA leaves the verdict `unknown` rather than inferring a seller's reputation.
- The existing Groq key is needed for synthesis. If a provider fails, ASTRA returns a partial response with a clear message and does not substitute guesses.
- Research results are informational, not a guarantee of product authenticity, seller trustworthiness, price availability, or warranty coverage.

| Route | Purpose |
|---|---|
| `/` | Home catalogue, ASTRA Check summary, recommendations, pipeline/status cards, assistant, approval card, goals/wallet rail |
| `/buyer/dashboard` | Authenticated buyer home composed by `HomeClient`; redirects non-buyers to the seller dashboard |
| `/explore` | Search by text, voice, or image, with category and price filters |
| `/categories` and `/categories/[slug]` | Category browsing and matching product cards |
| `/product/[slug]` | Product detail, add-to-cart, consent checkout, negotiation, seller messaging, authenticity, trust, outfit and spatial-decor panels, AR preview |
| `/deals` | Active deals, reservations, and deal updates |
| `/orders` | Buyer orders, timelines, reversible actions, and dispute entry points |
| `/messages` | Buyer/seller messaging UI and chat surface |
| `/goals` | Buyer budget, shopping goals, matched deals, and restock estimates |
| `/wallet` | Buyer PKR balance, ledger, consent, top-up/withdrawal UI and display-only settlement context |
| `/astra-check` | Buyer trust, price and budget evaluation surface |
| `/b2b` | B2B payload evaluation/demo interface |
| `/seller/dashboard` | Seller overview and dashboard panels |
| `/seller/inventory`, `/seller/products` | Inventory creation/editing and listing management |
| `/seller/orders`, `/seller/fulfillment` | Seller-scoped order review and dispatch workflow |
| `/seller/astra-check` | Seller indicators and rule/compliance information |
| `/seller/sales-goals` | Seller targets and progress |
| `/seller/wallet` | Seller earnings view; payouts are disabled unless a real processor is configured |
| `/seller/messages`, `/seller/notifications` | Seller conversations and notifications |

## Feature and language status

### Locale support matrix

The locale set is English (`en`), Urdu (`ur`), Roman Urdu (`roman_urdu`), Punjabi (`pa`), Pashto (`ps`), Sindhi (`sd`), Persian/Farsi (`fa`), Simplified Chinese (`zh`), and Arabic (`ar`). The region selector offers Pakistan (PK), China (CN), Iran (IR), and UAE (AE); country choice filters the displayed language options. English is included in every region. Pakistan's list also includes Persian.

The table distinguishes phrase support from complete language support. `Partial` means there are selected aliases, phrase patterns, template entries, or provider prompts, not broad linguistic coverage or a language-quality guarantee.

| Language | NLU / voice recognition / TTS | Native UI translation | A2A negotiation / recovery | COD risk / voice-guard copy | Disputes / review trust | Financial awareness / purchase safeguards | Price-quality comparison / demand prediction |
|---|---|---|---|---|---|---|---|
| English | NLU rules and browser speech locale; optional server Whisper STT; no configured server TTS by default | English UI is the baseline | Rules negotiation; optional Groq reasoning; English copy available. 30-second reversal window is language-independent | English template and advisory score route | Deterministic dispute rule; review detector is heuristic and not wired to persisted review/photo evidence | Server checks consent ID, amount, ownership, expiry, and snapshot before debit | Static category price bands and seeded/interval-style forecasts |
| Urdu | Selected Urdu-script phrase mappings; browser locale and optional provider STT; no response TTS path | Mostly English; selector is not a full Urdu UI | Locale can be passed or inferred; generated translation requires configured Groq | Urdu entry exists; delivery provider is not configured by default | Same deterministic/limited evidence behavior | Same server safeguards; modal and most messages remain English | Same rule/seeded signals; no Urdu-specific model |
| Roman Urdu | Stronger selected commerce aliases for common budget, category, size, color and order phrases; browser recognition uses Urdu locale | Some Roman Urdu search/voice copy; most UI remains English | Roman Urdu locale can be requested; fallback translation depends on Groq | Roman Urdu entry exists; prompt preparation does not itself send a message | Selected Roman Urdu phrases normalize; review sentiment remains a small word-list heuristic | Same server safeguards; no consent bypass from Roman Urdu input | Same rule/seeded signals |
| Punjabi | Selected Roman Punjabi aliases and script detection/normalization | English-first | Locale prompt/translation path is conditional on Groq | Punjabi entry exists; no live voice/WhatsApp delivery by default | Limited normalization only | Same backend guards | Same rule/seeded signals |
| Pashto | Selected Pashto aliases and script cues; not broad dialect/accent recognition | English-first | Locale prompt/translation path is conditional on Groq | Pashto entry exists; no live delivery by default | Limited normalization only | Same backend guards | Same rule/seeded signals |
| Sindhi | Selected Sindhi aliases and script cues; not broad dialect/accent recognition | English-first | Locale prompt/translation path is conditional on Groq | Sindhi entry exists; no live delivery by default | Limited normalization only | Same backend guards | Same rule/seeded signals |
| Persian/Farsi | A limited set of Persian-script shopping phrases and locale detection | English-first; available in PK and IR selectors | Locale prompt/translation path is conditional on Groq | Persian entry exists; no live delivery by default | A few normalized terms only | Same backend guards | Same rule/seeded signals |
| Chinese | A limited set of Simplified Chinese shopping/order/review terms and script detection | English-first; Chinese option is offered for CN | Locale prompt/translation path is conditional on Groq | Chinese entry exists; no live delivery by default | A few normalized terms only | Same backend guards | Same rule/seeded signals |
| Arabic | A limited set of Arabic shopping/order/review terms and script detection | English-first; Arabic option is offered for AE | Locale prompt/translation path is conditional on Groq | Arabic entry exists; no live delivery by default | A few normalized terms only | Same backend guards | Same rule/seeded signals |

**Important language constraints**

- `app/services/shopping_nlu.py` and `localization.py` implement dictionaries, regular expressions, script checks, and phrase substitutions. They are not general-purpose machine translation or speech models.
- `TopBar.tsx` uses the selected locale for browser speech recognition and search copy. Most labels, forms, product content, dashboard copy, and system errors remain English.
- Server-side STT uses the configured Whisper-compatible Groq endpoint and does not pass an explicit target language parameter. In the browser, speech recognition depends on browser/platform support.
- `voice_service.synthesize()` currently returns `None`; `/voice/synthesize` responds with HTTP 501. The current UI has no `speechSynthesis.speak()` response path; voice helpers only cancel browser speech output if one is active. There is no functioning universal TTS response path or language/latency guarantee.
- Chat translation is a separate Groq text-model pass when `GROQ_API_KEY` is configured. If translation is unavailable, the code retains the source reply; it does not guarantee a translated fallback.
- Template entries exist for the nine locales, but template completeness, script encoding, dialect quality, accessibility, and legal/financial wording require native-speaker review before launch.

### Capability status at a glance

| Capability | Code status | Operational qualification |
|---|---|---|
| Catalogue search and product discovery | Implemented with deterministic filters/ranking and optional fusion signals | Search quality depends on catalogue metadata and configured providers; no universal NLU coverage |
| Voice interaction | Partial prototype | Browser speech, WebSocket events, and buffered audio-to-STT path; no end-to-end streaming STT/TTS latency SLA |
| WhatsApp adapter | Implemented adapter, provider-config dependent | Webhook signature/verification, text/photo/voice parsing and product links; outbound send requires Meta credentials; links open product pages, not an auto-checkout |
| COD risk panel | Advisory scoring and manual prompt preparation | Payment method, route-risk and verified-phone signals are not recorded by the current schema; high-risk trigger prepares a prompt but returns `not_sent_no_provider_configured` |
| Outfit stylist | Advisory catalogue matching | Metadata plus optional product embedding similarity; absent inventory categories produce no item |
| Trust detector | Heuristic service exists | Product trust-score route currently calls it with empty review/photo samples; seller score is the available evidence. It is not a live fake-review detection pipeline |
| Spatial room decorator | Read-only room-image and catalogue prototype | Groq vision is optional; visual layout cues are estimates, dimensions are not measured; results depend on decor inventory |
| Web-AR | Conditional | `<model-viewer>` is used where a supported seller-provided 3D model URL exists. Most catalog items may have no model; try-on sample assets are illustrative, not product-fit simulation |
| A2A price negotiation | REST and WebSocket flows exist | REST can use optional Groq reasoning; WebSocket A2A is deterministic. Negotiation acceptance is not checkout approval or payment |
| Demand prediction | Demonstration heuristic | Restock timing uses stable seeded intervals/fallback products, not a trained demand model |
| Review UI | Presentational/demo data in product detail | Product detail response synthesizes a sample review and rating breakdown from aggregate product fields; it is not a persisted review corpus |
| Cryptographic/ZK/deepfake showcase values | Demo outputs | Current helper derives stable hashes and seeded values; it does not perform a real Groth16 proof, Ed25519 signing, or trained image-manipulation inference |

### Phase 0–6 and showstopper progress report

The repository does not define a machine-readable phase registry or release checklist. The mapping below follows the feature sequence described in project requests and reports code evidence, not a claim that a phase passed acceptance testing.

| Phase / feature group | Status from code inspection |
|---|---|
| Phase 0 — Core application, authentication, catalogue and seller/buyer routes | Present: Next.js frontend, FastAPI API, database models, JWT/OTP and optional Google OAuth, shared catalogue, role-gated seller routes |
| Phase 1 — Commerce, budget and financial consent | Present: cart, checkout session, PKR wallet, hash-bound consent validation, idempotency checks, order lifecycle and a 30-second reversible window; consent voice UI has the limitation documented below |
| Phase 2 — Conversational NLU and memory | Partial: common phrase/constraint extraction and persisted explicit shopping preferences; language coverage is dictionary/rule based |
| Phase 3 — Multimodal catalogue/voice discovery | Partial: image validation and optional Groq vision, browser voice search, buffered WebSocket audio and optional STT; not continuous low-latency STT/TTS |
| Phase 4 — ASTRA Check, trust, dispute and decision support | Mixed: rule-based affordability/trust/price checks and dispute workflow exist; cryptographic/deepfake showcase fields are deterministic demo values and review evidence is not connected to persisted samples |
| Phase 5 — Streaming voice and interruption | Partial prototype: authenticated WebSocket accepts transcript/audio events and interrupt messages; audio is buffered until end-of-clip, server TTS streaming is absent, and no 0.23ms or sub-500ms benchmark is available |
| Phase 6 — Order operations and bundle offers | Present with limits: buyer-scoped order tracking/return-request validation, bundle advisory calculator, negotiation approval and normal checkout consent; returns require review and bundle quotes do not create orders |
| Showstopper 1 — COD Risk & Voice Guard | Advisory score and localized prompt preparation exist. Payment-method, phone-verification and delivery-route signals are incomplete; no auto-cancel; outbound confirmation provider is unconfigured |
| Showstopper 2 — AI Outfit Stylist | Advisory recommendation cards use product metadata and optional embeddings; outcome quality depends on category metadata and available in-stock items |
| Showstopper 3 — Fake Review & Seller Trust Detector | Heuristic scoring service exists, but the current product trust endpoint passes empty review/photo sets; it cannot currently substantiate a live authenticity percentage from buyer evidence |
| Showstopper 4 — WhatsApp Commerce Adapter | Webhook parsing, signature verification, media download restrictions, optional STT/vision and catalogue/product-page links exist; Meta credentials are required for actual send/receive deployment |
| Cross-border localization and spatial room decor | Partial/advisory: country-aware display and route estimates, locale prompts, room cues and product matching exist; UI translation, seller origin editing, actual duties, dimensions, and room-model inventory are incomplete |

## Buyer experience

### Home and buyer dashboard

`/buyer/dashboard` loads the authenticated user's home payload and renders `HomeClient`. It is a dashboard-like home composition rather than a tabbed analytics application. The visible sections are:

- **Hero banner and suggestions:** links into catalogue discovery.
- **ASTRA Check widget:** affordability, seller trust, and price-fairness verdicts; currently rule-based.
- **Recommended products:** ranked by seller trust and rating in `RecommendationEngine`, not collaborative filtering.
- **Pipeline bar:** order/pipeline status data when available.
- **AI assistant card:** best-match suggestion based on a simple affordability classification.
- **Human approval card:** pending approval/reversal actions.
- **Goals and wallet rail:** shopping goals, budget and wallet summary data.

```
Astra_ai/
├── app/                        # Next.js App Router pages
├── components/                 # React components
├── lib/                        # Typed API client, shared types, hooks
├── astra-backend/
│   ├── app/
│   │   ├── core/                # config, database, security, rate limiting
│   │   ├── models/               # SQLAlchemy table modules
│   │   ├── schemas/              # Pydantic request/response contracts
│   │   ├── services/             # Business-logic engines
│   │   ├── realtime/             # WebSocket managers
│   │   └── api/v1/endpoints/     # REST endpoint modules
│   ├── tests/                    # pytest suite
│   └── alembic/versions/         # Postgres migration revisions
├── e2e/                         # Playwright end-to-end specs
└── docker-compose.prod.yml
```

### Product detail and discovery panels

`/product/[slug]` and `ProductDetailClient` include product media, category-safe image fallback, price/stock/variant controls, seller/trust summary, review presentation, and these actions/panels:

- **Add to Cart:** adds the selected product/quantity/variant to the authenticated cart; it does not itself debit the wallet.
- **Buy Now:** requests a server checkout session, displays the server total and launches financial consent.
- **AI Negotiate:** starts offer/counter rounds; a buyer-accepted negotiation must be approved before the ordinary checkout route accepts it.
- **Save to Shopping Goal:** creates/updates a buyer goal; optional allocation is a separate wallet operation and must be treated as a money movement.
- **Message Seller:** opens the seller conversation drawer.
- **ASTRA Check & buyer reviews / Authenticity Audit:** the first tab includes aggregate and sample review UI; audit details include calculated listing hash and several demo/seeded indicators described above.
- **Trust badge:** advisory trust metrics. Current API evidence is mostly seller trust because review/photo evidence collections are empty at the endpoint.
- **Outfit Stylist:** suggests complementary products from active inventory using category, color, formality, pattern and optional embeddings. It can request a non-binding bundle estimate with seller floors; it does not add the bundle to cart.
- **Spatial Room Decorator:** accepts a room photo and optional text, queries visual cues and catalogue matches, displays a listed-price total and any cross-border notices. It does not reserve stock, mutate product data, create an order, or call checkout.
- **Cross-border shipping badge:** displays route-based ETA and a rough 10% planning duty allowance where origin differs from buyer region. These are advisory estimates, not a carrier/customs quote or checkout charge.
- **AR / 3D Preview:** `ARTryOnModal` loads `<model-viewer>` for configured example assets; sample apparel assets are marked illustrative. Room bundle cards expose AR placement only when inventory specifications include an HTTPS `.glb`/`.gltf` `model_url`.

The spatial photo service requests wall tone, lighting, visible layout, furniture aesthetic, and visible constraints. It explicitly does not estimate room dimensions/depth from a 2D image. Spatial matching is catalogue keyword/cue ranking, not a trained interior-design model. Missing model assets and missing inventory are shown as unavailable rather than fabricated.

### Orders, returns, wallet, and goals

- **Orders:** buyer-scoped list/detail/tracking endpoints show the current status and event timeline. Statuses include pending approval, reversible window, confirmed, shipped, delivered, and cancelled.
- **Returns/exchanges:** buyer ownership and eligibility window checks apply. The request endpoint records a request for review; it does not automatically issue a return refund or silently change an order.
- **Dispute:** a separate dispute endpoint exists. Within an order's active 30-second reversal window, its deterministic risk score can auto-refund when it reaches the configured threshold; lower scores are queued for human review. This behavior is specific to the dispute path and does not authorize purchases.
- **Wallet:** buyer balance and ledger are PKR-backed. Wallet top-up, withdrawal, consent, and ledger routes are server-side operations; display currency conversion does not change settlement currency.
- **Goals/budget:** buyer goals, budget caps, savings and matching recommendations use explicit server operations. Goal allocation can move money into a goal bucket and is not the same as a read-only recommendation.

## Seller workspace

Seller pages use `SellerRouteGuard` and seller API dependencies. The overview at `/seller/dashboard` provides:

- **Top actions:** Add New Listing and View Seller Rules.
- **Summary cards:** total settled seller revenue, pending order count, inventory value/active listing count, and average rating.
- **Seller trust/verification panel:** seller trust metrics and status indicators.
- **Revenue Growth chart:** plots the API's recent monthly revenue series.
- **Top Selling Products table:** product, price, stock, and a sales-velocity field. The displayed “views” metric is not a full analytics event pipeline.
- **Seller tools shortcuts:** inventory/barcode, orders, fulfillment, and messages.
- **Merchant Insights:** seller-scoped aggregates for negotiations, accepted prices, search trends, variant demand, and related summaries. The panel states that aggregates omit buyer identities; some search trend values are explanatory rather than individual event tracking.
- **COD Risk panel:** buyer/order risk factors, a manual prompt preparation action for high scores, and a manual-review action. The event is not sent through a voice/WhatsApp provider by default.
- **Astra Seller Assistant:** interactive text panel answering inventory, COD, price-floor, and order questions. The API reads seller-scoped records and returns rule-based summaries. It is explicitly read-only; suggested follow-up chips are static prompts.
- **Inline inventory form:** barcode lookup/scan, listing metadata, price, seller floor, stock, image and specifications. Use `model_url: https://…/model.glb` in specifications to enable spatial AR for a listing. The current form does not expose an origin-country control; seller-created products default to PK unless populated through another data path.

Google sign-in requires an OAuth 2.0 Web application client. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `astra-backend/.env`, and register the exact redirect URI `http://localhost:8000/api/v1/auth/google/callback` in Google Cloud Console. Keep `GOOGLE_REDIRECT_URI` and `FRONTEND_URL=http://localhost:3000` aligned with your local URLs. For deployments on separate subdomains, configure `AUTH_COOKIE_DOMAIN` to the shared parent domain so the browser can send the session cookie to both the frontend and API.

Seller workspace sections:

| Seller page | Functional behavior and current limits |
|---|---|
| Inventory | Create/update/delete seller-owned products; stock/status and price validation; barcode helper uses the sample/verified catalogue and manual entry for unknown barcodes |
| Products | Seller-scoped listing cards and active/inactive toggle; listings with order history cannot be deleted, so stock/status should be changed instead |
| Orders | Seller-owned order list and escrow/order actions through `SellerEscrowOrders` |
| Fulfillment | Dispatch confirmed orders; delivery confirmation belongs to the buyer flow |
| ASTRA Check | Seller verification/trust and business indicators; these should not be read as an external identity-provider guarantee unless configured |
| Sales Goals | Create and view seller targets/progress; progress comes from tracked order revenue/contributions |
| Wallet | Earnings summary and ledger placeholder; UI/API report payouts disabled until a verified payout provider is connected |
| Notifications | Seller notification list |
| Messages | Buyer/seller direct message panel with realtime updates |

**Seller bundle pricing:** seller inventory accepts `seller_price_floor`; the multi-item advisory bundle calculator respects the stored per-item floor. The single-item negotiation route uses a deterministic floor estimate derived from listing price and trust, not necessarily the seller-configured floor. Offers remain non-binding until buyer review/approval and checkout consent.

**Cross-border seller parameters:** product records include `origin_country`, but the visible seller inventory form does not currently provide an origin-country field. Existing defaults/data can support cross-border notices; seller self-service country maintenance remains incomplete.

## AI and decision-support services

| Service | Source area | Actual behavior |
|---|---|---|
| Shopping NLU and memory | `shopping_nlu.py`, `shopping_memory.py`, chat/explore | Deterministic extraction of common category, color, size and budget phrases; selected dialect aliases; authenticated account preference facets are stored and used for ranking. No autonomous purchase action is produced by parsing |
| Buyer tone | `buyer_tone.py` | Keyword rules for price sensitivity, hesitation and high intent; emits optional prompts. It is not a psychological/emotion model |
| Visual search | `vision.py`, `explore.py` | Image signature validation and optional Groq vision descriptor request; ranking fuses text/category/price and available image or vector signals. Provider absence degrades the visual path |
| Spatial decorator | `spatial_decorator.py` | Optional Groq room-photo JSON analysis plus read-only inventory lookup for sofas, rugs, curtains and lamps. No metric dimensions, placement coordinates, cart mutations, or checkout calls |
| Outfit stylist | `outfit_stylist.py` | Metadata/category matching with color, formality, pattern and optional embedding similarity; returns advisory look cards and cross-border estimates |
| Trust detector | `trust_detector.py` | Word-list sentiment/rating mismatch, duplicate text, timestamp clustering, and supplied photo evidence scoring. Current product endpoint does not load persisted review/photo samples, so scores there have limited confidence and rely mainly on seller trust |
| COD risk | `cod_risk_engine.py`, `cod_risk.py` | Transparent weighted score over recorded order history/returns, order total versus history, route risk and phone verification. The current schema has no validated route-risk or phone-verification field and does not record payment method, so those signals are unknown and `cod_applicability` is `not_recorded` |
| Deals / price fairness | `deals_pipeline.py`, `market_feed.py`, `price_fairness_engine.py` | Deal eligibility combines rolling observations, listing discount, seller metrics and stock. Competitor observations are initialized with deterministic multipliers; optional USD/PKR feed applies a bounded adjustment. ASTRA Check's category fairness engine uses a static category-average table |
| Restock / demand | `astra_agents.py`, `budget_agent.py` | Forecast intervals are deterministic, stable-seeded estimates based on limited order history or fallback products. They are product guidance, not a trained demand-prediction model |
| A2A negotiation | `negotiation.py`, `groq_negotiation.py`, `realtime/negotiation_ws.py` | REST rounds use a deterministic cap/floor and optionally request Groq JSON reasoning with validation. WebSocket agent rounds use deterministic arithmetic. Locale is passed to the optional reasoning/translation paths; numeric bounds are checked server-side |
| Authenticity showcase | `astra_agents.py`, product authenticity endpoint | SHA-256 listing fingerprint is computed, while ZK proof identifiers, cryptographic stamp fields, and synthetic-image scan scores are generated from deterministic seeds. The current code does not contain a cryptographic proof verifier, Ed25519 private-key signing flow, or actual image-forensics model |
| WhatsApp commerce | `whatsapp_adapter.py`, `whatsapp_webhook.py` | Meta webhook handshake/signature validation, text/image/audio parsing, optional image/STT processing, catalogue matching, product review links, and optional outbound text. A calling-code lookup is only a buyer-country hint. It does not create an order or direct wallet debit |

### Voice pipeline, latency, interruption, and TTS

The repository has two related paths:

1. Browser `SpeechRecognition` powers voice search in `TopBar`, `GlobalVoiceFab`, and `VoiceWidget`, using the selected browser locale where available.
2. `/ws/voice` accepts transcript events and binary audio chunks. Audio is buffered per socket and passed to the configured STT adapter on `audio_end`; it is not streamed chunk-by-chunk into a streaming transcription model. The interrupt event invalidates an output generation and reports an interrupted state, but the backend currently does not stream TTS audio frames. `MediaRecorder` chunking therefore does not establish sub-500ms conversational latency.

The `/voice/transcribe` endpoint uses the optional Groq Whisper-compatible STT request and otherwise returns a deterministic placeholder transcript. Server synthesis is not implemented (`synthesize()` returns `None`); the synthesis route responds with 501. The current UI has no `speechSynthesis.speak()` response path, so there is no functioning universal TTS path or language/latency guarantee.

There is **no measured “0.23ms WebSocket” benchmark in this repository**. `/metrics` measures aggregate HTTP request latencies and database health; it is not a WebSocket latency benchmark.

### B2B negotiation and recovery window

- WebSocket `/ws/negotiation/{product_id}` runs deterministic buyer/seller rounds for up to six rounds and persists a negotiated session. Despite demo event names such as `deal_settled`, this means the negotiation price was accepted; it is not payment settlement.
- REST `/api/v1/negotiation/{product_id}/offer` accepts offers, checks the buyer cap and computed floor, and can call Groq for structured reasoning. The provider response is parsed and counter values outside the floor/ask range are rejected.
- The buyer must call the explicit negotiated-offer approval action; checkout verifies buyer ownership, approved session, listing/quantity/price, and expiry. Financial consent remains a separate subsequent action.
- Negotiation sessions expire after 10 minutes by default. The **30-second recovery/reversal window** starts after checkout confirmation/debit, not during negotiation; deployment can change the interval through configuration.

## Financial architecture and safeguards

### Authoritative checkout path

`app/services/checkout_fsm.py` is the central checkout/order state machine. In broad terms:

1. Cart/session creation reloads and locks the buyer, cart, and product records; validates active listings, quantities, stock, and monthly budget; snapshots authoritative product prices; reserves stock; creates pending orders and a checkout session. This is a reservation, not a debit.
2. Checkout sessions expire after 600 seconds by default. Abandonment/expiry cancels pending reservations and restores cart items/stock.
3. Financial consent is requested for a specific buyer, exact amount, and checkout/order reference. Consent records include a one-time identifier, auth method, expiry/attempt state, and an order/checkout snapshot hash.
4. Confirmation locks the session and relevant records, revalidates prices, quantities, listing status and the snapshot hash, checks consent ownership/amount/expiry/non-consumption, verifies PKR wallet funds and budget capacity, then writes the debit ledger entry and updates order/session state in one server transaction.
5. The application marks consent consumed and opens the default 30-second reversal window. A buyer can cancel/refund only through allowed reversible state transitions. Finalization releases escrow according to the state machine.
6. Negotiated checkout repeats the ownership, buyer-approval, price, stock and expiry checks before it creates a checkout session. AI offers alone cannot commit a purchase.

Snapshot integrity is implemented as application-level SHA-256 binding and revalidation at confirmation. The schema stores the snapshot hash and single-use consent lifecycle fields; the repository does not show a database trigger that makes every snapshot row physically immutable. “Immutable snapshot” should therefore be understood as a hash-bound confirmation invariant, not as a claim about a DB-level append-only storage system.

### Consent and user control

- A chat, search, vision, WhatsApp, spatial, seller-assistant, recommendation, or risk-scoring route does not itself debit the buyer wallet or create a binding purchase.
- WhatsApp links open the official product page with a referral marker. Product review and normal checkout remain in the authenticated web flow.
- Bundle quotes and outfit suggestions are advisory. Seller-configured bundle floors are respected by the bundle quote service; the buyer must review and proceed through checkout.
- COD risk does not auto-cancel an order or change its payment method. In the current COD API, high risk enables a seller-triggered prompt record; actual voice/WhatsApp delivery reports `not_sent_no_provider_configured`. Buyer confirmation updates the risk event only.
- Return requests are buyer-scoped and queued for review; they are not automatic refunds.
- Dispute processing is distinct: a buyer-initiated dispute during the reversible window can trigger a rule-based refund at the configured risk threshold. Below threshold it queues for human review. This flow refunds an existing reversible order; it does not authorize a new purchase.

### Important consent UI qualification

The current consent modal's “hold to say” interaction requests microphone permission, but the frontend constructs the expected sentence from the displayed amount rather than transcribing the speaker. The server still validates the submitted consent record against the exact amount, checkout/order reference, snapshot and one-time token, but the UI is **not voice biometrics or verified speech recognition**. OTP is a separate consent method. Review this limitation before treating the voice button as a strong authentication factor.

The cross-border “micro-settlement” route shown in the UI is generated by deterministic demo data and fixed FX values; it is not a connected bank/custodian/FX clearing network. Display-currency conversion and customs allowances are advisory and do not change PKR checkout arithmetic.

## API and realtime surface

All REST API paths below are under `/api/v1` unless stated otherwise. The code is the source of truth; OpenAPI is available from the running FastAPI app.

| Endpoint group | Representative operations |
|---|---|
| Authentication | `/auth/register`, `/auth/login`, `/auth/verify-otp`, `/auth/google/start`, `/auth/google/callback`, `/auth/me`, `/auth/logout`, password recovery |
| Home/catalogue | `/home`, `/products/recommended`, `/products/{slug}`, product authenticity, outfit recommendations, trust score |
| Explore | `/explore/search`, `/explore/intent`, catalogue product/detail routes |
| Chat | `/chat/history`, `/chat/message`, streaming chat route; optional image upload and product/order/bundle card responses |
| Voice | `/voice/transcribe`, `/voice/synthesize` (currently returns 501 without an implementation/provider) |
| Spatial | `/spatial-decorator/recommendations` (authenticated, validated image upload, read-only inventory match) |
| Cart/checkout | `/cart`, `/cart/add`, `/checkout/session`, checkout confirm/abandon, financial consent authorization |
| Orders | `/orders`, `/orders/{ref}`, `/orders/track`, return request, buyer reversal, dispute and audit/detail routes |
| Negotiation | `/negotiation/{product_id}/offer`, bundle advisory, explicit negotiated-session buyer approval |
| Deals | `/deals`, deal reservation/release and deal details |
| Wallet | `/wallet`, ledger, top-up, withdrawal, consent, micro-settlement display data |
| Buyer goals | `/goals`, budget dashboard, matched deals and shopping-goal operations |
| Seller | `/seller/dashboard-stats`, analytics, `/seller/assistant`, inventory, orders, fulfillment, goals and wallet summary |
| COD risk | `/cod-risk/orders/{ref}`, confirmation prompt preparation, manual review, buyer confirmation |
| WhatsApp | `/webhooks/whatsapp` GET verification and signed POST webhook |
| B2B / pipeline / ASTRA Check | `/b2b/evaluate`, `/pipeline/state`, `/astra-check/*` |

Realtime channels mounted by `app/main.py` include:

| WebSocket route | Use |
|---|---|
| `/ws/voice` | Authenticated transcript/audio event protocol; buffered STT, NLU/tone events, interrupt signal |
| `/ws/negotiation/{product_id}` | Deterministic A2A offer/counter feed |
| `/ws/deals` | Deal update broadcasts |
| `/ws/wallet/{user_id}` | Wallet event updates with user checks |
| `/ws/notifications` and `/ws/orders` | Notification/order events |
| `/ws/messages/{conversation_id}` | Buyer/seller conversation updates |
| `/ws/pipeline` | Order/pipeline state updates |

## Configuration and local development

### Requirements

- Node.js and npm (see `package.json` for pinned Next.js/React/tool versions).
- Python version compatible with the backend dependencies.
- PostgreSQL for deployment. The backend has SQLite/local support for development and tests.

### Frontend

```powershell
npm install
npx tsc --noEmit
npm run dev
```

The frontend reads `NEXT_PUBLIC_API_URL` and defaults to `http://localhost:8000`. The normal API client includes browser credentials for the auth cookie. Display FX lookup uses `open.er-api.com` from the browser and is optional/fallback-safe.

### Backend

```powershell
Set-Location .\astra-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload
```

On non-Windows shells, activate with `source .venv/bin/activate`. Review the environment template before starting; set a unique `SECRET_KEY` and correct `DATABASE_URL`. PostgreSQL deployments should apply the migration chain in `astra-backend/alembic/versions/` before serving traffic. The worktree contains migrations through revision `20261021_19_cross_border_localization`; verify the actual Alembic head in the target checkout/database before deployment.

### Render + Vercel + Neon deployment

Create a Neon PostgreSQL database, a Render Web Service with root directory `astra-backend`, and a Vercel project using the repository root. Set the Render build command to `pip install -r requirements.txt` and the start command to `python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`. The migration runs before the API starts.

Required Render variables: `APP_ENV=production`, `SECRET_KEY` (a newly generated random secret), `DATABASE_URL` (the Neon connection string with `sslmode=require`), `FRONTEND_URL` (the Vercel site origin), and `REFRESH_PRODUCTS_ON_STARTUP=false`. `REDIS_URL` is optional; without Redis, realtime events use the in-process fallback. Configure `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`, and a verified `RESEND_FROM_EMAIL` to deliver production OTP emails. Keep all credentials in the provider dashboards, not in the repository.

Set the Vercel environment variable `NEXT_PUBLIC_API_URL` to the Render service origin, for example `https://your-api.onrender.com`. Redeploy the Vercel project after setting it. Vercel uses the native Next.js routing configuration; this project is not a static SPA and does not use an `/index.html` rewrite.

### Optional integrations

| Integration | Configuration area | Behavior when absent |
|---|---|---|
| Groq vision / text / negotiation | `VISION_PROVIDER`, `VISION_API_KEY` or `GROQ_API_KEY`, `VISION_MODEL`, `GROQ_MODEL` | Vision analysis can be unavailable; deterministic search/rules remain |
| Groq-compatible STT | `STT_PROVIDER=groq`, `STT_API_KEY` | No server transcript; some callers use a deterministic/browser fallback |
| TTS | `TTS_PROVIDER`, `TTS_API_KEY` | Current backend synthesizer is a stub and route returns 501 |
| Meta WhatsApp Cloud API | verify token, app secret, access token, phone number ID and API version settings | Verification/webhook send is disabled or outbound send reports false; no WhatsApp delivery occurs |
| Google OAuth | Google client ID/secret and callback/origin settings | Google sign-in unavailable |
| USD/PKR market feed | market-feed settings | Static seeded observations/rates are used where implemented |
| Seller payout processor | configured payout dependency/provider | Seller payout endpoints return unavailable; seller UI says payouts disabled |

Never commit `.env` values, credentials, OTPs, access tokens, or production connection strings.

## Verification status

This README was generated from source inspection of the current worktree: frontend routes/components, backend endpoints/services, schemas/models, realtime handlers, configuration and migrations. No tests, builds, or benchmarks were run for this documentation task. Existing tests and E2E specs are present under `astra-backend/tests/`, `astra-backend/test_*.py`, `lib/*.test.mjs`, and `e2e/`; their presence is not evidence that they currently pass.

Useful commands when you want to run verification:

```powershell
Set-Location .\astra-backend
.\.venv\Scripts\python.exe -m pytest
Set-Location ..
npx tsc --noEmit
npm run lint
npm run test:voice
npm run test:e2e
```

The repository worktree was already dirty during this audit, with numerous modified and untracked application files. This README change does not imply those other changes were reviewed as a clean commit or released build.

## Known limitations and production work

1. Add native-speaker review and complete UI string catalogs before advertising full multilingual UX.
2. Replace phrase-rule coverage with maintained locale-specific NLU, normalization and evaluation datasets; add genuine multilingual speech/streaming STT and TTS providers where needed.
3. Measure voice latency end-to-end under realistic network/provider conditions; do not quote 0.23ms or sub-500ms from the current implementation.
4. Connect persisted verified buyer reviews/photos to trust scoring and replace showcase hashes/seeded checks with verifiable cryptographic and image-analysis systems.
5. Populate and validate delivery-route, phone-verification and payment-method fields before treating COD risk scores as COD-specific operational signals.
6. Connect the confirmation payload to a configured, consented WhatsApp/voice provider; current action only prepares the prompt.
7. Add catalogued room/furniture 3D models and seller origin-country entry; current AR and origin support is conditional on product data.
8. Replace seeded market observations, static category averages and restock interval estimates with validated sources/models and confidence evaluation.
9. Integrate and audit a real seller payout/settlement provider before enabling payouts. The displayed cross-border settlement route is a simulation.
10. Review the consent voice UI as described above; use a real challenge-response speech/biometric design only after separate security and accessibility review.
