import fs from "node:fs";
import path from "node:path";
import { expect, request, test, type Page } from "@playwright/test";

// Tests other than the login flow itself start authenticated via the
// global-setup storageState, keeping the suite under the backend's
// sensitive-endpoint rate limit (8 logins / 60s).

async function loginViaUi(page: Page) {
  await page.goto("/login");
  // Gate on hydration — an unhydrated page native-submits the form instead of calling the API.
  await page.waitForFunction(() => Boolean((window as unknown as { next?: { version?: string } }).next?.version), undefined, { timeout: 60_000 });
  await page.getByPlaceholder("you@example.com").fill("aisha@astra.ai");
  await page.getByPlaceholder("••••••••").fill("demo1234");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/verify-otp/);
  const digits = page.locator('input[inputmode="numeric"]');
  for (const [index, digit] of [..."123456"].entries()) await digits.nth(index).fill(digit);
  await page.getByRole("button", { name: /verify & continue/i }).click();
  // OTP completion preserves the authenticated user's role dashboard.
  await expect(page).toHaveURL(/\/buyer\/dashboard$/, { timeout: 20_000 });
}

test.describe("ASTRA core browser flows", () => {
  test("voice and image discovery stay in search and do not call financial actions", async ({ page }) => {
    await page.addInitScript(() => {
      class MockSpeechRecognition {
        lang = "en-US";
        interimResults = false;
        continuous = false;
        onresult: ((event: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null = null;
        onend: (() => void) | null = null;
        onerror: (() => void) | null = null;
        start() {
          setTimeout(() => {
            const result = Object.assign([{ transcript: "buy lenovo laptop" }], { isFinal: true });
            this.onresult?.({ resultIndex: 0, results: [result] });
            this.onend?.();
          }, 0);
        }
        stop() { this.onend?.(); }
      }
      Object.defineProperty(window, "SpeechRecognition", { value: MockSpeechRecognition });
    });
    await page.goto("/explore");

    const financialRequests: string[] = [];
    page.on("request", (request) => {
      const path = new URL(request.url()).pathname;
      if (/\/api\/v1\/(?:cart|checkout|wallet|negotiation|orders|approval|consent)(?:\/|$)/.test(path)) financialRequests.push(path);
    });
    const intentResponses: boolean[] = [];
    page.on("response", async (response) => {
      if (new URL(response.url()).pathname.endsWith("/explore/intent")) {
        const body = await response.json() as { auto_checkout: boolean };
        intentResponses.push(body.auto_checkout);
      }
    });

    const searchBox = page.getByLabel("Roman Urdu mein search karein");
    await searchBox.fill("wireless headphones");
    await searchBox.press("Enter");
    await expect(page.getByText("Sony WH-1000XM5").first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Voice search" }).click();
    await expect.poll(() => intentResponses.length).toBe(1);
    expect(intentResponses).toEqual([false]);
    await expect(page).toHaveURL(/\/explore(?:\?.*)?$/);

    await page.getByLabel("Image search").locator("input[type=file]").setInputFiles({
      name: "headphones-product.jpg",
      mimeType: "image/jpeg",
      buffer: fs.readFileSync(path.join(process.cwd(), "public/images/products/sony-headphones.jpg")),
    });
    await expect(page.getByText("headphones-product.jpg", { exact: true })).toBeVisible();
    expect(financialRequests).toEqual([]);
  });

  test("user login and OTP verification", async ({ page }) => {
    await page.addInitScript(() => localStorage.removeItem("astra:region"));
    await loginViaUi(page);
    await expect(page.getByRole("dialog", { name: "Select your country or region" })).toBeVisible();
    await expect(page.getByText(/recommended for you/i).first()).toBeVisible();
  });

  test("authenticated regional selector exposes country and language choices", async ({ page }) => {
    await page.addInitScript(() => localStorage.removeItem("astra:region"));
    await page.goto("/buyer/dashboard");
    const dialog = page.getByRole("dialog", { name: "Select your country or region" });
    await expect(dialog).toBeVisible();
    await dialog.getByRole("button", { name: /China/ }).click();
    await dialog.getByLabel("Preferred language").selectOption({ label: "Chinese (Mandarin / 中文)" });
    const savedPreferences = page.waitForResponse((response) =>
      response.url().includes("/api/v1/auth/me/preferences") && response.request().method() === "PATCH",
    );
    await dialog.getByRole("button", { name: "Continue" }).click();
    const preferencesResponse = await savedPreferences;
    expect(preferencesResponse.ok()).toBeTruthy();
    await expect(dialog).toBeHidden();

    await expect(page.getByLabel("Display currency")).toHaveValue("CNY");
    await expect(page.getByLabel("Interface and voice language")).toHaveValue("Chinese (Mandarin / 中文)");
    const regionButton = page.getByRole("button", { name: "Change country or region" });
    await expect(regionButton).toContainText("CN");
    await expect(regionButton).toContainText("CNY");

    await page.reload();
    await expect(dialog).toBeHidden();
    await expect(page.getByLabel("Display currency")).toHaveValue("CNY");
    await expect(page.getByLabel("Interface and voice language")).toHaveValue("Chinese (Mandarin / 中文)");
    await regionButton.click();
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText("Pakistan", { exact: true })).toBeVisible();
    await expect(dialog.getByText("China", { exact: true })).toBeVisible();
    await expect(dialog.getByLabel("Preferred language")).toHaveValue("Chinese (Mandarin / 中文)");
  });

  test("product detail opens AI Negotiator and receives a counter-offer", async ({ page }) => {
    await page.goto("/product/samsung-galaxy-s25-ultra");
    await page.getByRole("button", { name: /AI Negotiate/i }).click();
    await expect(page.getByText("AI Negotiator", { exact: true })).toBeVisible();
    await page.getByPlaceholder("Your offer (Rs.)").fill("100000");
    await page.getByRole("button", { name: /send offer/i }).click();
    await expect(page.getByText(/COUNTER|ACCEPTED/).first()).toBeVisible({ timeout: 15_000 });
  });

  test("buyer explicitly approves an accepted negotiation before checkout", async ({ page }) => {
    const slug = "jbl-flip-6";
    const productResponse = await page.request.get(`http://localhost:8000/api/v1/products/${slug}`);
    expect(productResponse.ok()).toBeTruthy();
    const product = await productResponse.json() as { price: number };
    const acceptedUnitPrice = Math.round(product.price * 0.93 * 100) / 100;

    await page.goto(`/product/${slug}`);
    await page.getByPlaceholder("Shipping address for Buy Now").fill("42 Negotiated Checkout Road, Lahore");
    await page.getByRole("button", { name: /AI Negotiate/i }).click();
    await page.getByPlaceholder("Your offer (Rs.)").fill(String(acceptedUnitPrice));
    await page.getByRole("button", { name: /send offer/i }).click();
    await expect(page.getByText("Accepted offer, pending your approval")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(new RegExp(`Rs\\. ${acceptedUnitPrice.toLocaleString()} per unit × 1`))).toBeVisible();

    await page.getByRole("button", { name: /Approve this price and continue to checkout/i }).click();
    await expect(page.getByRole("dialog").getByText("Financial consent required")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/Buyer-approved negotiated price reserved/)).toBeVisible();
    await expect(page.getByRole("dialog").getByText(`Rs. ${acceptedUnitPrice.toLocaleString()}`, { exact: false })).toBeVisible();
    await page.getByRole("button", { name: "Close" }).click();
  });

  test("order details initiates escrow dispute and refund", async ({ page }) => {
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

    // Verify the same approved order appears in its actual seller's workspace.
    // Use a separate API context so seller login cannot replace the buyer UI session.
    const sellerEmail = deal.seller === "TechBazaar Official"
      ? "seller@astra.ai"
      : `${deal.seller.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}@astra.ai`;
    const sellerContext = await request.newContext({ baseURL: "http://localhost:8000" });
    try {
      const sellerLogin = await sellerContext.post("/api/v1/auth/login", {
        data: { email: sellerEmail, password: "demo1234" },
      });
      expect(sellerLogin.ok()).toBeTruthy();
      const { otp_token: sellerOtp } = await sellerLogin.json() as { otp_token: string };
      const sellerVerify = await sellerContext.post("/api/v1/auth/verify-otp", {
        data: { otp_token: sellerOtp, code: "123456" },
      });
      expect(sellerVerify.ok()).toBeTruthy();
      const sellerOrders = await sellerContext.get("/api/v1/seller/orders");
      expect(sellerOrders.ok()).toBeTruthy();
      expect(await sellerOrders.json()).toContainEqual(expect.objectContaining({ order_ref: orderRef }));
    } finally {
      await sellerContext.dispose();
    }

    await page.goto("/orders");
    await page.getByRole("button", { name: new RegExp(orderRef) }).click();
    await page.getByRole("button", { name: /Initiate AI Dispute/i }).click();
    await expect(page.getByText(/escrow auto-refunded/i)).toBeVisible({ timeout: 15_000 });
  });
});
