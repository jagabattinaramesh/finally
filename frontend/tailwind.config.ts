import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#0d1117",
          panel: "#11161d",
          deep: "#0a0e14",
          alt: "#1a1a2e",
        },
        line: {
          DEFAULT: "#1f2630",
          soft: "#161c25",
          strong: "#2a323d",
        },
        text: {
          primary: "#e6edf3",
          muted: "#8b95a5",
          dim: "#5a6577",
        },
        accent: {
          yellow: "#ecad0a",
          blue: "#209dd7",
          purple: "#753991",
        },
        tick: {
          up: "#26d07c",
          down: "#ef4d68",
        },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
        display: ['"Space Grotesk"', '"Inter"', "system-ui", "sans-serif"],
      },
      fontSize: {
        "2xs": ["10px", "12px"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(32, 157, 215, 0.35), 0 0 24px -8px rgba(32, 157, 215, 0.45)",
        panel: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 -1px 0 0 rgba(0,0,0,0.4) inset",
      },
      keyframes: {
        flashUp: {
          "0%": { backgroundColor: "rgba(38, 208, 124, 0.32)" },
          "100%": { backgroundColor: "rgba(38, 208, 124, 0)" },
        },
        flashDown: {
          "0%": { backgroundColor: "rgba(239, 77, 104, 0.32)" },
          "100%": { backgroundColor: "rgba(239, 77, 104, 0)" },
        },
        pulseDot: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
      },
      animation: {
        "flash-up": "flashUp 600ms ease-out",
        "flash-down": "flashDown 600ms ease-out",
        "pulse-dot": "pulseDot 1.6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
