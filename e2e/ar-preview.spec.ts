import { expect, test } from "@playwright/test";

test.describe("read-only AR preview", () => {
  test("opens a fallback preview without commerce requests", async ({ page }) => {
    await page.goto("/product/lenovo-ideapad-slim-5");
    await expect(page.getByRole("heading", { name: "Lenovo IdeaPad Slim 5" })).toBeVisible();

    const commerceRequests: string[] = [];
    page.on("request", (request) => {
      if (/\/(checkout|wallet|negotiation|cart)(\/|\?|$)/i.test(new URL(request.url()).pathname)) {
        commerceRequests.push(request.url());
      }
    });
    await page.getByRole("button", { name: "AR / 3D Preview" }).click();
    await expect(page.getByRole("dialog")).toContainText("3D preview is not available");
    expect(commerceRequests).toEqual([]);
  });

  test("a Roman Urdu AR intent opens the selected product preview in place", async ({ page }) => {
    await page.goto("/product/lenovo-ideapad-slim-5");
    await page.evaluate(() => window.dispatchEvent(new CustomEvent("astra:ar-intent")));
    await expect(page.getByRole("dialog")).toContainText("3D preview is not available");
    await expect(page).toHaveURL(/\/product\/lenovo-ideapad-slim-5$/);
  });
});
