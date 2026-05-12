import { test, expect } from "@playwright/test";

test.describe("SSE resilience", () => {
  test.fixme(true, "Pending app integration");

  test("reconnects after disconnect and status dot returns green", async ({ page }) => {
    await page.goto("/");

    const status = page.getByTestId("connection-status");
    await expect(status).toHaveAttribute("data-state", "connected");

    await page.evaluate(() => {
      const w = window as unknown as { __finallyEventSource?: EventSource };
      w.__finallyEventSource?.close();
    });

    await expect(status).toHaveAttribute("data-state", /reconnecting|disconnected/);
    await expect(status).toHaveAttribute("data-state", "connected", { timeout: 15_000 });
  });
});
