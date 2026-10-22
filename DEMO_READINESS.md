# ASTRA AI demo readiness

## Run locally

1. Start the backend from `astra-backend` with the configured Python environment and seeded database: `python -m app.db.seed`, then `uvicorn app.main:app --reload`.
2. In the repository root, run `npm install` and `npm run dev`.
3. Open `http://localhost:3000`, sign in with a seeded demo account, and use the buyer flow below.

The backend requires a valid secret and database configuration. OTP delivery and any optional Groq negotiation call depend on the corresponding environment configuration. Do not use production credentials in a demo.

## Buyer to seller walkthrough

1. As a buyer, open a product and launch the deterministic A2A negotiation. The agent uses the current listing, the buyer's wallet balance, a documented listing and trust based floor heuristic, and observed market history only when rows exist. It does not call an LLM. An offer can be rejected when the wallet cap cannot satisfy the floor estimate.
2. Add a product to the cart and create a checkout session. Review its backend calculated total and order details.
3. Authorize that exact checkout total using the configured consent flow, then confirm the session. The backend verifies the owner, amount, subject, current product prices, wallet balance, and one time consent before creating debits.
4. Switch to the seller demo account. Open seller orders, dispatch an eligible confirmed order, then return to the buyer account to confirm delivery or open a dispute.
5. Use the order timeline and wallet ledger to review state changes and any local refund.

## What is implemented

- Consent, wallet debit/refund, checkout, reservations, and seller order state use the application's database ledger. This is a local simulation; there is no bank, escrow provider, payment capture, or seller payout integration.
- The WebSocket A2A flow and the REST rules fallback are deterministic. The REST negotiator can optionally call Groq when `GROQ_API_KEY` is configured; returned status, reasoning, and counter offers are validated before use. It is not the same flow as the WebSocket demo.
- Market history is shown as unavailable when the database has no observations; it is not inferred from the listing price.
- Order approval and dispatch require the appropriate authenticated owner or seller access. Production email, OAuth, and other external-provider paths require their own credentials.

## Safety notes for demos

- Keep `APP_ENV=development` and demo-only OTP settings confined to local environments; production settings reject the development secret and disable debug OTP output.
- Use seeded demo users and test data. Do not use real card, bank, or seller payout credentials; those integrations are not implemented.
