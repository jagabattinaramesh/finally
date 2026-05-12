import { test, expect } from "@playwright/test";

const parseDollar = (s: string | null) =>
  Number((s ?? "").replace(/[^0-9.\-]/g, ""));

test.describe("sell", () => {
  test.fixme(true, "Pending app integration");

  test("selling shares increases cash and updates position", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("trade-ticker").fill("AAPL");
    await page.getByTestId("trade-quantity").fill("5");
    await page.getByTestId("trade-buy").click();
    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();

    const cash = page.getByTestId("cash-balance");
    const cashAfterBuy = parseDollar(await cash.textContent());

    await page.getByTestId("trade-ticker").fill("AAPL");
    await page.getByTestId("trade-quantity").fill("5");
    await page.getByTestId("trade-sell").click();

    await expect
      .poll(async () => parseDollar(await cash.textContent()), { timeout: 5000 })
      .toBeGreaterThan(cashAfterBuy);
    await expect(page.getByTestId("position-row-AAPL")).toHaveCount(0);
  });
});
