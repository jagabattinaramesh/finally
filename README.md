# FinAlly — the Finance Ally

An AI-powered trading workstation that streams live market data, simulates portfolio trading, and lets an LLM assistant analyze positions and execute trades from natural language.

Built entirely by coding agents as the capstone for an agentic AI coding course.

## What it does

- Streams live prices into a Bloomberg-inspired dark UI with flash animations
- Trades a simulated portfolio ($10k virtual cash, instant fills, no fees)
- Visualizes holdings via positions table, treemap heatmap, and P&L chart
- AI chat assistant analyzes the portfolio and executes trades and watchlist changes on request

## Stack

- **Frontend:** Next.js (static export) + TypeScript + Tailwind
- **Backend:** FastAPI (Python, `uv`-managed) with SSE streaming
- **Database:** SQLite (lazy-initialized, volume-mounted)
- **AI:** LiteLLM via OpenRouter (Cerebras inference, structured outputs)
- **Market data:** Built-in GBM simulator (default) or Massive API

The whole app ships as a single Docker container on port 8000.

## Quick start

```bash
cp .env.example .env        # add OPENROUTER_API_KEY
docker build -t finally .
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
# open http://localhost:8000
```

## Environment

| Variable | Required | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | AI chat |
| `MASSIVE_API_KEY` | No | Real market data (omit to use simulator) |
| `LLM_MOCK` | No | Deterministic mock LLM for tests |

## Status

The project is being rebuilt by agents from `planning/PLAN.md`. See that document for the full specification, architecture, and design decisions.

## License

See [LICENSE](LICENSE).
