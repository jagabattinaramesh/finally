import { test, expect } from "@playwright/test";

const parseDollar = (s: string | null) =>
  Number((s ?? "").replace(/[^0-9.\-]/g, ""));

test.describe("buy", () => {
  test.fixme(true, "Pending app integration");

  test("buying shares decreases cash and creates a position", async ({ page }) => {
    await page.goto("/");

    const cash = page.getByTestId("cash-balance");
    const before = parseDollar(await cash.textContent());

    await page.getByTestId("trade-ticker").fill("AAPL");
    await page.getByTestId("trade-quantity").fill("5");
    await page.getByTestId("trade-buy").click();

    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
    await expect
      .poll(async () => parseDollar(await cash.textContent()), { timeout: 5000 })
      .toBeLessThan(before);
  });
});
