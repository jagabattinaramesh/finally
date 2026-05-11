# Massive API Reference (for FinAlly)

> Research notes and worked examples for the **Massive** REST API
> (formerly **Polygon.io** — rebranded 2025-10-30). This document scopes
> what FinAlly actually needs: live-ish prices for ~10 watchlist tickers
> and previous-day close for change calculations. Other Massive endpoints
> (fundamentals, options, corporate actions, etc.) are intentionally out
> of scope.

---

## 1. Background

Polygon.io rebranded to Massive on 2025-10-30. The transition is
backward-compatible:

| Item | New | Legacy (still works) |
|------|-----|----------------------|
| Docs site | `massive.com/docs` | `polygon.io/docs` |
| REST base URL | `https://api.massive.com` | `https://api.polygon.io` |
| Python package | `massive` | `polygon-api-client` |
| Existing API keys | unchanged | unchanged |

For this project we standardize on `https://api.massive.com` but the
legacy host will keep working for an extended deprecation window.

---

## 2. Authentication

Every request needs an API key. Two equivalent forms:

```
# Query parameter
GET https://api.massive.com/v2/.../...?apiKey=YOUR_KEY

# Bearer header (preferred — keeps key out of logs/history)
GET https://api.massive.com/v2/.../...
Authorization: Bearer YOUR_KEY
```

FinAlly reads the key from `MASSIVE_API_KEY` and uses the **Bearer
header** so the secret never appears in URLs.

If the key is missing or invalid the API returns HTTP 401 with a JSON
error body.

---

## 3. Rate limits

| Tier | Limit | Notes |
|------|-------|-------|
| Free (Basic) | **5 requests / minute** | end-of-day data, 15-minute delayed quotes |
| Starter | unlimited RPS, real-time delay | per-tier streaming limits apply |
| Developer / Advanced / Business | unlimited RPS, real-time | varies by license |

Exceeding the cap returns **HTTP 429**. The recommended client policy
is exponential backoff. FinAlly maps the tier to a poll interval:

| Effective tier | Polling interval used by FinAlly |
|----------------|----------------------------------|
| Free | **15 s** (4 calls/min, leaves headroom under the 5/min cap) |
| Paid | **2–5 s** (configurable) |

A single snapshot call returns all watchlist tickers, so one poll per
interval is sufficient regardless of watchlist size (up to the 250-ticker
limit per request).

---

## 4. Endpoints FinAlly uses

### 4.1 Full Market Snapshot (primary endpoint)

This is the workhorse for FinAlly's live tile grid. One call returns
current and previous-day OHLC plus the last trade for a list of tickers.

```
GET /v2/snapshot/locale/us/markets/stocks/tickers
    ?tickers=AAPL,GOOGL,MSFT,AMZN,TSLA,NVDA,META,JPM,V,NFLX
```

**Query parameters**

| Name | Type | Notes |
|------|------|-------|
| `tickers` | CSV string | Case-sensitive. Up to ~250 symbols. Omit to return the entire US market. |
| `include_otc` | bool | Default `false`. |

**Response shape** (trimmed)

```json
{
  "status": "OK",
  "count": 10,
  "tickers": [
    {
      "ticker": "AAPL",
      "todaysChange": 1.23,
      "todaysChangePerc": 0.65,
      "updated": 1715444532000000000,
      "day":     { "o": 189.50, "h": 191.20, "l": 188.90, "c": 190.73, "v": 41203122, "vw": 190.40 },
      "prevDay": { "o": 188.10, "h": 189.95, "l": 187.80, "c": 189.50, "v": 39021556, "vw": 188.75 },
      "min":     { "av": 102345, "c": 190.73, "h": 190.81, "l": 190.65, "o": 190.70, "v": 5123, "t": 1715444460000 },
      "lastTrade": { "p": 190.73, "s": 100, "t": 1715444531999000000, "x": 4, "c": [12] },
      "lastQuote": { "P": 190.74, "S": 3, "p": 190.72, "s": 5, "t": 1715444531998000000 }
    }
    /* ... one entry per requested ticker ... */
  ]
}
```

**Fields FinAlly cares about**

| JSON path | Use |
|-----------|-----|
| `ticker` | Symbol |
| `lastTrade.p` | Current price (preferred) |
| `day.c` | Fallback when `lastTrade` is absent (pre-market) |
| `prevDay.c` | Previous-day close, used for daily % change |
| `todaysChange`, `todaysChangePerc` | Already-computed deltas |
| `updated` | Nanosecond timestamp of last update |

Timestamps from the v2 snapshot are **nanoseconds since epoch** — divide
by 1e9 to compare against `time.time()`.

### 4.2 Previous Close (single ticker)

Used when a brand-new ticker is added mid-session and we need a baseline
before the first full snapshot tick. Lightweight, one ticker per call.

```
GET /v2/aggs/ticker/{ticker}/prev?adjusted=true
```

```json
{
  "ticker": "AAPL",
  "status": "OK",
  "results": [
    { "o": 188.10, "h": 189.95, "l": 187.80, "c": 189.50,
      "v": 39021556, "vw": 188.75, "t": 1715271600000, "n": 412055 }
  ]
}
```

`t` here is **milliseconds since epoch** (note the unit mismatch with
the snapshot endpoint).

### 4.3 Aggregates / Custom Bars (sparkline backfill — optional)

Not required for the MVP (frontend accumulates its own sparklines from
the SSE stream), but useful if we later want a deeper intraday history
on page load.

```
GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
```

Example — 1-minute bars for today:

```
GET /v2/aggs/ticker/AAPL/range/1/minute/2026-05-11/2026-05-11
    ?adjusted=true&sort=asc&limit=390
```

### 4.4 Unified Snapshot v3 (forward-looking alternative)

Massive also exposes a newer v3 endpoint that unifies stocks/options/fx/
crypto/indices. It is functionally similar to 4.1 for our use case but
uses different field names and the `ticker.any_of=` query syntax.

```
GET /v3/snapshot?type=stocks&ticker.any_of=AAPL,GOOGL,MSFT
```

We stick with the v2 endpoint (4.1) because (a) the field shape is more
stable, (b) every Polygon community example uses it, and (c) it has no
250-result page boundary issue for a 10-ticker watchlist.

---

## 5. Worked example — `httpx` (the approach FinAlly will use)

A direct HTTP call is simpler than pulling in the SDK for one endpoint.

```python
"""Minimal Massive REST client for the FinAlly snapshot poll."""

import os
import httpx

BASE_URL = "https://api.massive.com"


async def fetch_snapshot(tickers: list[str], api_key: str) -> dict[str, dict]:
    """Return a {ticker: {price, prev_close, change_pct, updated_ns}} map."""
    url = f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
    params = {"tickers": ",".join(tickers)}
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        body = resp.json()

    out: dict[str, dict] = {}
    for entry in body.get("tickers", []):
        last_trade = entry.get("lastTrade") or {}
        day = entry.get("day") or {}
        prev_day = entry.get("prevDay") or {}
        price = last_trade.get("p") or day.get("c")
        if price is None:
            continue
        out[entry["ticker"]] = {
            "price": float(price),
            "prev_close": float(prev_day.get("c", price)),
            "change_pct": float(entry.get("todaysChangePerc", 0.0)),
            "updated_ns": int(entry.get("updated", 0)),
        }
    return out


if __name__ == "__main__":
    import asyncio

    key = os.environ["MASSIVE_API_KEY"]
    print(asyncio.run(fetch_snapshot(["AAPL", "GOOGL", "MSFT"], key)))
```

### Handling 429 / transient failures

```python
import asyncio
import httpx

async def fetch_with_backoff(call, *, attempts: int = 4) -> dict:
    """Retry on 429 / 5xx with exponential backoff (1s, 2s, 4s)."""
    delay = 1.0
    for i in range(attempts):
        try:
            return await call()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status not in (429, 500, 502, 503, 504) or i == attempts - 1:
                raise
            await asyncio.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")
```

---

## 6. Worked example — official `massive` SDK (alternative)

If we ever want trades, quotes, fundamentals, etc. the SDK becomes worth
its weight. Listed here for completeness.

```bash
uv add massive
```

```python
from massive import RESTClient

client = RESTClient(api_key="YOUR_KEY")  # reads MASSIVE_API_KEY env var if omitted

# Full market snapshot, filtered by tickers
snap = client.get_snapshot_all(
    "stocks",
    tickers=["AAPL", "GOOGL", "MSFT"],
)
for t in snap:
    print(t.ticker, t.last_trade.price, t.prev_day.close, t.todays_change_perc)

# Previous-day close, single ticker
prev = client.get_previous_close_agg("AAPL")
print(prev[0].close)
```

The SDK returns dataclass-like objects rather than raw dicts. Field
names are `snake_case` versions of the JSON keys.

---

## 7. Quick reference card

| Need | Endpoint | Method | Returns |
|------|----------|--------|---------|
| Live prices for N watched tickers | `/v2/snapshot/locale/us/markets/stocks/tickers?tickers=…` | GET | list of snapshots |
| Baseline prev close for a single ticker | `/v2/aggs/ticker/{T}/prev` | GET | single OHLC bar |
| Intraday history (optional sparkline backfill) | `/v2/aggs/ticker/{T}/range/1/minute/{from}/{to}` | GET | list of 1m bars |
| Market open/closed status | `/v1/marketstatus/now` | GET | `{market: "open" \| "closed", …}` |

| Auth | `Authorization: Bearer $MASSIVE_API_KEY` |
| Base | `https://api.massive.com` |
| Free-tier RPS | 5/min (FinAlly polls every 15 s) |
| Paid-tier RPS | unlimited (FinAlly polls every 2–5 s) |
| Error to handle | 429 → exponential backoff |
