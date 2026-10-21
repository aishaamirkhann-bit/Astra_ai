import { expect, request, test, type APIRequestContext } from "@playwright/test";

async function loginSupplier(email: string): Promise<APIRequestContext> {
  const context = await request.newContext({ baseURL: "http://localhost:8000" });
  const login = await context.post("/api/v1/auth/login", { data: { email, password: "demo1234" } });
  if (!login.ok()) {
    const body = await login.text();
    await context.dispose();
    throw new Error(`Supplier login failed: ${login.status()} ${body}`);
  }
  const { otp_token: otpToken } = await login.json() as { otp_token: string };
  const verify = await context.post("/api/v1/auth/verify-otp", { data: { otp_token: otpToken, code: "123456" } });
  if (!verify.ok()) {
    const body = await verify.text();
    await context.dispose();
    throw new Error(`Supplier OTP verification failed: ${verify.status()} ${body}`);
  }
  return context;
}

test("buyer publishes a wholesale request, compares supplier quotes, and awards without payment", async ({ page }) => {
  test.setTimeout(90_000);
  await page.addInitScript(() => {
    localStorage.setItem("astra:region", "PK");
    localStorage.setItem("astra:language", "English");
  });
  await page.goto("/b2b");

  const title = `Browser sourcing ${Date.now()}`;
  await page.locator('input[name="title"]').fill(title);
  await page.locator('input[name="category"]').fill("Apparel");
  await page.locator('textarea[name="description"]').fill("Synthetic browser test request");
  await page.locator('input[name="quantity"]').fill("50");
  await page.locator('input[name="budget"]').fill("30000");
  await page.locator('input[name="days"]').fill("20");
  await page.getByRole("button", { name: "Publish request" }).click();
  await expect(page.getByRole("status")).toContainText("Request published");

  const bid = await page.request.get("http://localhost:8000/api/v1/b2b/requests");
  expect(bid.ok()).toBeTruthy();
  const bidId = ((await bid.json()) as Array<{ id: number; title: string }>).find((item) => item.title === title)?.id;
  if (!bidId) throw new Error("The newly published browser test request was not returned by the buyer request list.");

  const supplierA = await loginSupplier("seller@astra.ai");
  const supplierB = await loginSupplier("threads-co@astra.ai");
  try {
    const standard = await supplierA.post("/api/v1/b2b/place-bid", {
      data: { bid_id: bidId, offered_price: 20_000, delivery_days: 12, is_featured: false },
    });
    const featured = await supplierB.post("/api/v1/b2b/place-bid", {
      data: { bid_id: bidId, offered_price: 23_000, delivery_days: 10, is_featured: true },
    });
    expect(standard.ok(), await standard.text()).toBeTruthy();
    expect(featured.ok(), await featured.text()).toBeTruthy();

    await page.reload();
    const requestCard = page.locator("article").filter({ hasText: title });
    await expect(requestCard).toContainText("TechBazaar Official");
    await expect(requestCard).toContainText("Threads & Co.");
    await expect(requestCard).toContainText("Platform commission estimate: Rs. 200 (1%). Vendor estimated net: Rs. 19,800.");
    await expect(requestCard).toContainText("Platform commission estimate: Rs. 460 (2%). Vendor estimated net: Rs. 22,540.");

    const awardResponse = page.waitForResponse((response) =>
      response.url().includes(`/api/v1/b2b/requests/${bidId}/award/`) && response.request().method() === "POST",
    );
    page.once("dialog", (dialog) => dialog.accept());
    const standardCard = requestCard.getByText("TechBazaar Official", { exact: true })
      .locator("xpath=ancestor::div[contains(@class, 'rounded-xl')][1]");
    await standardCard.getByRole("button", { name: "Select supplier" }).click();
    const awarded = await awardResponse;
    expect(awarded.ok()).toBeTruthy();
    const result = await awarded.json() as {
      status: string; bid_status: string; commission_rate: number; commission_amount: number;
      vendor_net_payout: number; order_created: boolean; payment_processed: boolean;
    };
    expect(result).toMatchObject({
      status: "awarded", bid_status: "awarded", commission_rate: 0.01,
      commission_amount: 200, vendor_net_payout: 19_800,
      order_created: false, payment_processed: false,
    });
    await expect(page.getByRole("status")).toContainText("No order or payment was created");
  } finally {
    await supplierA.dispose();
    await supplierB.dispose();
  }
});
