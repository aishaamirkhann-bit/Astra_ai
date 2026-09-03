import { expect, test } from "@playwright/test";

// Auth comes from global-setup storageState (one API login for the whole
// suite) so we never trip the backend's sensitive-endpoint rate limit.

test.describe("ASTRA showcase widgets", () => {
  test("A2A live room streams agent rounds, progress bar, and settlement", async ({ page }) => {
    await page.goto("/product/samsung-galaxy-s25-ultra");
    await page.getByRole("button", { name: /AI Negotiate/i }).click();
    await expect(page.getByText("AI Negotiator", { exact: true })).toBeVisible();
    await expect(page.getByText("Agent-to-Agent Live Room")).toBeVisible();
    await page.getByRole("button", { name: /launch a2a negotiation/i }).click();
    await expect(page.getByText(/agreement proximity/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Buyer budget", { exact: false })).toBeVisible();
    await expect(page.getByText("Delay threshold", { exact: false })).toBeVisible();
    await expect(page.getByText(/DEAL SETTLED · Rs\./)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/Handshake complete in \d+ rounds/)).toBeVisible();
  });

  test("authenticity tab shows cryptographic stamp and 0% synthetic manipulation", async ({ page }) => {
    await page.goto("/product/samsung-galaxy-s25-ultra");
    await page.getByRole("button", { name: /Authenticity Audit/i }).click();
    await expect(page.getByText("Verified Cryptographic Stamp").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("AI Synthetic Image Scan")).toBeVisible();
    await expect(page.getByText(/0% manipulation/)).toBeVisible();
    await expect(page.getByText(/ZK Verification/i)).toBeVisible();
  });

  test("goals dashboard renders predictive restock alert cards", async ({ page }) => {
    await page.goto("/goals");
    await expect(page.getByText("Predictive Restock Alerts")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/AI purchase-interval engine/)).toBeVisible();
    await expect(page.getByText(/Restock by/i).first()).toBeVisible();
  });

  test("order drawer exposes collapsible ASTRA Swarm Log with parallel agents", async ({ page }) => {
    const deals = await page.request.get("http://localhost:8000/api/v1/deals?page_size=100");
    const deal = (await deals.json()).items.find((item: { price: number; stock_remaining: number }) => item.price <= 50_000 && item.stock_remaining > 0);
    expect(deal).toBeTruthy();
    const reserved = await page.request.post(`http://localhost:8000/api/v1/deals/${deal.id}/reserve`, { data: { quantity: 1 } });
    expect(reserved.ok()).toBeTruthy();
    const orderRef = (await reserved.json()).order_ref as string;
    const consent = await page.request.post("http://localhost:8000/api/v1/wallet/authorize-consent", {
      data: { amount: deal.price, auth_method: "Voice", order_ref: orderRef, voice_transcript: `I authorize payment of Rs. ${Math.trunc(deal.price)}` },
    });
    expect(consent.ok()).toBeTruthy();
    const consentId = (await consent.json()).consent_id as string;
    const approved = await page.request.post("http://localhost:8000/api/v1/approval/approve", { data: { order_ref: orderRef, consent_id: consentId } });
    expect(approved.ok()).toBeTruthy();

    await page.goto("/orders");
    await page.getByRole("button", { name: new RegExp(orderRef) }).click();
    const swarmToggle = page.getByRole("button", { name: /ASTRA Swarm Log/i });
    await expect(swarmToggle).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("pricing-agent")).toBeHidden();
    await swarmToggle.click();
    await expect(page.getByText("pricing-agent")).toBeVisible();
    await expect(page.getByText("risk-agent")).toBeVisible();
    await expect(page.getByText("logistics-agent")).toBeVisible();
    await swarmToggle.click();
    await expect(page.getByText("pricing-agent")).toBeHidden();

    // Cleanup: dispute refunds + cancels the order, restoring budget and stock.
    await page.getByRole("button", { name: /Initiate AI Dispute/i }).click();
    await expect(page.getByText(/escrow auto-refunded/i)).toBeVisible({ timeout: 15_000 });
  });
});
