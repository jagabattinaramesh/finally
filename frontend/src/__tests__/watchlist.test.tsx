import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Watchlist } from "@/components/Watchlist";
import { PriceProvider } from "@/lib/prices";

const items = [
  { ticker: "AAPL", price: 190, prev_close: 188, change_pct: 0.01 },
  { ticker: "MSFT", price: 410, prev_close: 415, change_pct: -0.012 },
];

function setup() {
  const onAdd = vi.fn().mockResolvedValue(undefined);
  const onRemove = vi.fn().mockResolvedValue(undefined);
  const onSelect = vi.fn();
  render(
    <PriceProvider url="about:blank">
      <Watchlist items={items} selected="AAPL" onSelect={onSelect} onAdd={onAdd} onRemove={onRemove} />
    </PriceProvider>,
  );
  return { onAdd, onRemove, onSelect };
}

describe("Watchlist", () => {
  it("renders all rows", () => {
    setup();
    expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-row-MSFT")).toBeInTheDocument();
  });

  it("calls onSelect when a row is clicked", async () => {
    const user = userEvent.setup();
    const { onSelect } = setup();
    await user.click(screen.getByTestId("watchlist-row-MSFT"));
    expect(onSelect).toHaveBeenCalledWith("MSFT");
  });

  it("submits new ticker uppercased and trimmed", async () => {
    const user = userEvent.setup();
    const { onAdd } = setup();
    const input = screen.getByTestId("watchlist-add-input");
    await user.type(input, "  pypl  ");
    await user.click(screen.getByRole("button", { name: /add ticker/i }));
    expect(onAdd).toHaveBeenCalledWith("PYPL");
  });

  it("removes a ticker", async () => {
    const user = userEvent.setup();
    const { onRemove } = setup();
    await user.click(screen.getByTestId("watchlist-remove-MSFT"));
    expect(onRemove).toHaveBeenCalledWith("MSFT");
  });
});
