import { describe, it, expect } from "vitest";
import { __testing } from "@/lib/api";

const { normalizePortfolio, normalizeWatchlist, normalizeSnapshots } = __testing;

describe("api normalizers", () => {
  it("watchlist accepts bare array (current backend shape)", () => {
    const items = normalizeWatchlist([
      { ticker: "AAPL", price: 190, prev_close: 188, change_pct: 0.01 },
      { ticker: "MSFT", price: 410 },
    ]);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ ticker: "AAPL", price: 190, prev_close: 188 });
    expect(items[1].prev_close).toBe(410);
  });

  it("watchlist accepts envelope { items: [...] }", () => {
    const items = normalizeWatchlist({ items: [{ ticker: "TSLA", price: 200 }] });
    expect(items).toEqual([{ ticker: "TSLA", price: 200, prev_close: 200, change_pct: 0 }]);
  });

  it("watchlist handles null", () => {
    expect(normalizeWatchlist(null)).toEqual([]);
  });

  it("portfolio normalizes unrealized_pnl -> unrealized_pl", () => {
    const p = normalizePortfolio({
      cash_balance: 9649.84,
      total_value: 9999.6,
      positions: [
        {
          ticker: "AAPL",
          quantity: 2,
          avg_cost: 175.08,
          current_price: 174.88,
          market_value: 349.76,
          unrealized_pnl: -0.4,
          change_pct: -0.1142,
        },
      ],
    });
    expect(p.positions[0].unrealized_pl).toBe(-0.4);
    expect(p.cash_balance).toBe(9649.84);
    expect(p.total_value).toBe(9999.6);
  });

  it("snapshots convert ISO recorded_at to ms", () => {
    const out = normalizeSnapshots([
      { total_value: 10000, recorded_at: "2026-05-12T09:14:16Z" },
      { total_value: 10010, recorded_at: "2026-05-12T09:14:46Z" },
    ]);
    expect(out).toHaveLength(2);
    expect(out[0].ts).toBeGreaterThan(0);
    expect(out[1].ts).toBeGreaterThan(out[0].ts);
  });

  it("snapshots convert fractional-seconds ts to ms", () => {
    const out = normalizeSnapshots([{ total_value: 10000, ts: 1700000000.5 }]);
    expect(out[0].ts).toBe(1700000000500);
  });
});
