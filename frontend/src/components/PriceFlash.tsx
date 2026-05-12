"use client";

import { useEffect, useRef, useState } from "react";
import { fmtUsd } from "@/lib/format";

type Props = {
  price: number | undefined;
  direction?: "up" | "down" | "flat";
  className?: string;
  prefix?: string;
};

export function PriceFlash({ price, direction, className = "", prefix }: Props) {
  const prevRef = useRef<number | undefined>(undefined);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    if (price === undefined) return;
    const prev = prevRef.current;
    if (prev !== undefined && prev !== price) {
      const dir = direction ?? (price > prev ? "up" : price < prev ? "down" : "flat");
      if (dir !== "flat") {
        setFlash(dir);
        const t = setTimeout(() => setFlash(null), 600);
        prevRef.current = price;
        return () => clearTimeout(t);
      }
    }
    prevRef.current = price;
  }, [price, direction]);

  if (price === undefined) {
    return <span className={`tabular text-text-dim ${className}`}>—</span>;
  }

  return (
    <span
      data-testid="price-flash"
      data-flash={flash ?? ""}
      className={`tabular px-1.5 rounded-sm transition-colors ${
        flash === "up" ? "animate-flash-up text-tick-up" : flash === "down" ? "animate-flash-down text-tick-down" : ""
      } ${className}`}
    >
      {prefix}
      {fmtUsd(price)}
    </span>
  );
}
