import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Positions, deriveLive } from "@/components/Positions";
import { PriceProvider } from "@/lib/prices";

const positions = [
  {
    ticker: "AAPL",
    quantity: 10,
    avg_cost: 100,
    current_price: 110,
    market_value: 1100,
    unrealized_pl: 100,
    unrealized_pl_pct: 0.1,
  },
  {
    ticker: "TSLA",
    quantity: 5,
    avg_cost: 250,
    current_price: 200,
    market_value: 1000,
    unrealized_pl: -250,
    unrealized_pl_pct: -0.2,
  },
];

describe("Positions math + render", () => {
  it("recomputes derived fields from live price", () => {
    const p = positions[0];
    const live = deriveLive(p, 120);
    expect(live.market_value).toBe(1200);
    expect(live.unrealized_pl).toBe(200);
    expect(live.unrealized_pl_pct).toBeCloseTo(0.2);
  });

  it("falls back to stored price when no live", () => {
    const p = positions[1];
    const live = deriveLive(p, undefined);
    expect(live.current_price).toBe(200);
    expect(live.market_value).toBe(1000);
    expect(live.unrealized_pl).toBe(-250);
  });

  it("handles zero cost gracefully", () => {
    const live = deriveLive(
      { ticker: "X", quantity: 0, avg_cost: 0, current_price: 0, market_value: 0, unrealized_pl: 0, unrealized_pl_pct: 0 },
      undefined,
    );
    expect(live.unrealized_pl_pct).toBe(0);
  });

  it("renders all rows", () => {
    render(
      <PriceProvider url="about:blank">
        <Positions positions={positions} />
      </PriceProvider>,
    );
    expect(screen.getByTestId("position-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("position-row-TSLA")).toBeInTheDocument();
  });

  it("shows empty state when no positions", () => {
    render(
      <PriceProvider url="about:blank">
        <Positions positions={[]} />
      </PriceProvider>,
    );
    expect(screen.getByText(/no open positions/i)).toBeInTheDocument();
  });
});
