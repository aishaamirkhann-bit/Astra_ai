import { expect, test } from "@playwright/test";

// Auth comes from global-setup storageState (one API login for the whole
// suite) so we never trip the backend's sensitive-endpoint rate limit.

test("home renders catalog with locally hosted images", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/recommended for you/i).first()).toBeVisible();
  const home = await page.request.get("http://localhost:8000/api/v1/home");
  const payload = await home.json();
  const image = payload.recommended_products?.[0]?.image as string | undefined;
  expect(image).toMatch(/^\/images\/products\//);
  const asset = await page.request.get(`http://localhost:3000${image}`);
  expect(asset.ok()).toBeTruthy();
  expect(asset.headers()["content-type"]).toContain("image");
});

test("deals page lists active deals with trust scores", async ({ page }) => {
  await page.goto("/deals");
  await expect(page.getByText(/mega deal|bestseller|new/i).first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/trust/i).first()).toBeVisible();
});
