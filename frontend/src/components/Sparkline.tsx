"use client";

import { useEffect, useRef } from "react";

type Point = { ts: number; price: number };

export function Sparkline({
  data,
  width = 88,
  height = 24,
  positive,
}: {
  data: Point[];
  width?: number;
  height?: number;
  positive?: boolean;
}) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    if (data.length < 2) {
      ctx.strokeStyle = "#2a323d";
      ctx.setLineDash([2, 3]);
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();
      return;
    }

    const prices = data.map((d) => d.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const stroke = positive === undefined ? "#209dd7" : positive ? "#26d07c" : "#ef4d68";

    ctx.lineWidth = 1.25;
    ctx.strokeStyle = stroke;
    ctx.beginPath();
    data.forEach((d, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((d.price - min) / range) * (height - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // fill underneath
    const grad = ctx.createLinearGradient(0, 0, 0, height);
    grad.addColorStop(0, `${stroke}33`);
    grad.addColorStop(1, `${stroke}00`);
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();
  }, [data, width, height, positive]);

  return <canvas ref={ref} style={{ width, height }} data-testid="sparkline" />;
}
