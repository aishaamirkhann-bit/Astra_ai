import { expect, test } from "@playwright/test";

// Account role is persisted by the backend. Always restore the shared demo
// account so later browser specs begin with the buyer authorization state.
test.afterEach(async ({ page }) => {
  await page.request.post("http://localhost:8000/api/v1/auth/role", { data: { role: "buyer" } });
});

test("switches account mode and prefills seller listing from barcode", async ({ page }) => {
  test.setTimeout(60_000);
  await page.goto("/");
  const profileMenu = page.getByRole("button", { name: "Open profile menu" });
  await expect(profileMenu).toBeVisible();
  await profileMenu.click();
  await page.getByRole("radio", { name: "Switch to Seller Mode" }).click();

  await expect(page).toHaveURL(/\/seller\/dashboard$/);
  await expect(page.getByText("Seller Mode", { exact: true }).first()).toBeVisible();
  await expect(page.getByLabel("Search Listings, Orders, Barcodes, or Inventory")).toHaveAttribute("placeholder", "Search Listings, Orders, Barcodes, or Inventory...");
  await expect(page.locator("aside nav a")).toHaveText([
    "Dashboard", "My Inventory", "Products", "Orders", "ASTRA Check",
    "Sales Goals", "Wallet", "Fulfillment", "Notifications", "Messages",
  ]);

  await page.getByLabel("Barcode / EAN / UPC").fill("890123456001");
  await expect(page.getByLabel("Product name")).toHaveValue("Samsung Galaxy A35 5G");
  await expect(page.getByLabel("Brand")).toHaveValue("Samsung");
  await expect(page.getByRole("textbox", { name: "Category", exact: true })).toHaveValue("Mobiles");
  await expect(page.getByLabel("Description")).toHaveValue(/Samsung Galaxy A35 5G/);
  await expect(page.getByLabel("Product image URL")).toHaveValue("/images/products/samsung-phone.jpg");
  await expect(page.getByLabel("Product name")).toBeDisabled();
  await expect(page.getByLabel("Price")).toHaveValue("89999");

  for (const route of [
    "/seller/inventory", "/seller/products", "/seller/orders", "/seller/astra-check",
    "/seller/sales-goals", "/seller/wallet", "/seller/fulfillment",
    "/seller/notifications", "/seller/messages",
  ]) {
    await page.goto(route);
    await expect(page.locator("main h1")).toBeVisible();
  }

  await profileMenu.click();
  await page.getByRole("radio", { name: "Switch to Buyer Mode" }).click();
  await expect(page).toHaveURL(/\/buyer\/dashboard$/);
  await expect(page.getByRole("link", { name: "Seller Dashboard" })).toHaveCount(0);
  await page.goto("/seller/dashboard");
  await expect(page).toHaveURL(/\/$/);
});
