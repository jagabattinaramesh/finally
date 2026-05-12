import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PriceFlash } from "@/components/PriceFlash";

describe("PriceFlash", () => {
  it("renders dash when price undefined", () => {
    render(<PriceFlash price={undefined} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders formatted price without flash on first mount", () => {
    render(<PriceFlash price={123.45} />);
    const el = screen.getByTestId("price-flash");
    expect(el.textContent).toBe("$123.45");
    expect(el.getAttribute("data-flash")).toBe("");
  });

  it("applies up-flash data-attr on price increase", () => {
    const { rerender } = render(<PriceFlash price={100} />);
    rerender(<PriceFlash price={101} />);
    expect(screen.getByTestId("price-flash").getAttribute("data-flash")).toBe("up");
  });

  it("applies down-flash data-attr on price decrease", () => {
    const { rerender } = render(<PriceFlash price={50} />);
    rerender(<PriceFlash price={49} />);
    expect(screen.getByTestId("price-flash").getAttribute("data-flash")).toBe("down");
  });

  it("respects explicit direction prop", () => {
    const { rerender } = render(<PriceFlash price={10} direction="up" />);
    rerender(<PriceFlash price={9} direction="up" />);
    expect(screen.getByTestId("price-flash").getAttribute("data-flash")).toBe("up");
  });
});
