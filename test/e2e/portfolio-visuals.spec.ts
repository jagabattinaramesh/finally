import { test, expect } from "@playwright/test";

test.describe("portfolio visuals", () => {
  test.fixme(true, "Pending app integration");

  test("heatmap renders and P&L chart has data", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("trade-ticker").fill("AAPL");
    await page.getByTestId("trade-quantity").fill("3");
    await page.getByTestId("trade-buy").click();
    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();

    const heatmap = page.getByTestId("portfolio-heatmap");
    await expect(heatmap).toBeVisible();
    await expect(heatmap.locator("[data-ticker]")).toHaveCount(1);

    const pnlChart = page.getByTestId("pnl-chart");
    await expect(pnlChart).toBeVisible();
    await expect
      .poll(async () => Number(await pnlChart.getAttribute("data-points") ?? "0"), {
        timeout: 5000,
      })
      .toBeGreaterThan(0);
  });
});
