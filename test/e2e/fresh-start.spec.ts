import { test, expect } from "@playwright/test";

const DEFAULT_TICKERS = [
  "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
  "NVDA", "META", "JPM", "V", "NFLX",
];

test.describe("fresh start", () => {
  test.fixme(true, "Pending app integration — fill selectors once frontend is built");

  test("default watchlist, $10k cash, prices stream", async ({ page }) => {
    await page.goto("/");

    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByText(ticker, { exact: false })).toBeVisible();
    }

    await expect(page.getByText(/\$\s*10[,.]?000/)).toBeVisible();

    const firstPrice = page.getByTestId(`price-${DEFAULT_TICKERS[0]}`);
    const initial = await firstPrice.textContent();
    await expect
      .poll(async () => (await firstPrice.textContent()) !== initial, { timeout: 5000 })
      .toBe(true);
  });
});
