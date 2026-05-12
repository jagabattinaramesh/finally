import { test, expect } from "@playwright/test";

/**
 * Mock LLM contract (LLM_MOCK=true) — see backend/app/llm/mock.py.
 * Buy regex: \bbuy\s+(\d+(?:\.\d+)?)\s+(?:shares?\s+of\s+)?([A-Z]{1,5})\b
 * Watchlist add regex: \b(?:add|watch)\s+([A-Z]{1,5})\b(?!\s+shares)
 */
test.describe("AI chat (mocked)", () => {
  test.fixme(true, "Pending app integration");

  test("buy phrase triggers trade and shows inline confirmation", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("chat-input").fill("buy 2 shares of AAPL");
    await page.getByTestId("chat-send").click();

    const assistant = page.getByTestId("chat-message-assistant").last();
    await expect(assistant).toContainText(/Buying 2 shares of AAPL/i);

    await expect(page.getByTestId("chat-trade-confirmation")).toContainText("AAPL");
    await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
  });

  test("watchlist add phrase adds ticker", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("chat-input").fill("add PYPL");
    await page.getByTestId("chat-send").click();

    const assistant = page.getByTestId("chat-message-assistant").last();
    await expect(assistant).toContainText(/Added PYPL/i);
    await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();
  });

  test("unmatched message returns default fallback", async ({ page }) => {
    await page.goto("/");

    await page.getByTestId("chat-input").fill("hello there");
    await page.getByTestId("chat-send").click();

    const assistant = page.getByTestId("chat-message-assistant").last();
    await expect(assistant).toContainText("Mock LLM: I received your message.");
  });
});
