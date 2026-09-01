import { expect, test, type Page } from "@playwright/test";

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
  await expect(page).toHaveURL(/localhost:3000\/$/);
}

test.describe("ASTRA core browser flows", () => {
  test("user login and OTP verification", async ({ page }) => {
    await loginViaUi(page);
    await expect(page.getByText(/recommended for you/i).first()).toBeVisible();
  });

  test("product detail opens AI Negotiator and receives a counter-offer", async ({ page }) => {
    await page.goto("/product/samsung-galaxy-s25-ultra");
    await page.getByRole("button", { name: /AI Negotiate/i }).click();
    await expect(page.getByText("AI Negotiator", { exact: true })).toBeVisible();
    await page.getByPlaceholder("Your offer (Rs.)").fill("100000");
    await page.getByRole("button", { name: /send offer/i }).click();
    await expect(page.getByText(/COUNTER|ACCEPTED/).first()).toBeVisible({ timeout: 15_000 });
  });

  test("order details initiates escrow dispute and refund", async ({ page }) => {
    const deals = await page.request.get("http://localhost:8000/api/v1/deals?page_size=100");
    const deal = (await deals.json()).items.find((item: { price: number; stock_remaining: number }) => item.price <= 50_000 && item.stock_remaining > 0);
    expect(deal).toBeTruthy();
    const reserved = await page.request.post(`http://localhost:8000/api/v1/deals/${deal.id}/reserve`, { data: { quantity: 1 } });
    expect(reserved.ok()).toBeTruthy();
    const orderRef = (await reserved.json()).order_ref as string;
    const approved = await page.request.post("http://localhost:8000/api/v1/approval/approve", { data: { order_ref: orderRef } });
    expect(approved.ok()).toBeTruthy();
    await page.goto("/orders");
    await page.getByRole("button", { name: new RegExp(orderRef) }).click();
    await page.getByRole("button", { name: /Initiate AI Dispute/i }).click();
    await expect(page.getByText(/escrow auto-refunded/i)).toBeVisible({ timeout: 15_000 });
  });
});
