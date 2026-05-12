"""LiteLLM wrapper for OpenRouter via Cerebras inference.

Returns a parsed ``ChatResponse``. Raises on transport failure. The model
occasionally omits the ``message`` field when it only intends to perform an
action, so we coerce that field before validating to keep the API contract
strict downstream.
"""

from __future__ import annotations

import json
import os
from typing import Any

from litellm import completion

from .schema import ChatResponse

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}


def call_llm(messages: list[dict[str, str]]) -> ChatResponse:
    """Send messages, request a structured ChatResponse, return the parsed model.

    OPENROUTER_API_KEY must be set in the environment.
    """
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    response = completion(
        model=MODEL,
        messages=messages,
        response_format=ChatResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )
    raw = response.choices[0].message.content
    return _parse_response(raw)


def _parse_response(raw: str) -> ChatResponse:
    """Parse the model's JSON, filling a missing ``message`` with a sensible default.

    The schema requires ``message``, but the upstream model sometimes returns
    only ``trades`` / ``watchlist_changes``. Synthesise a short summary in that
    case so we never raise a 500 to the client.
    """
    payload: dict[str, Any] = json.loads(raw)
    msg = payload.get("message")
    if not isinstance(msg, str) or not msg.strip():
        payload["message"] = _summarise(payload)
    return ChatResponse.model_validate(payload)


def _summarise(payload: dict[str, Any]) -> str:
    """One-line fallback describing the intended actions."""
    parts: list[str] = []
    for t in payload.get("trades") or []:
        side = str(t.get("side", "")).lower()
        qty = t.get("quantity")
        ticker = t.get("ticker")
        if side in ("buy", "sell") and ticker and qty is not None:
            verb = "Buying" if side == "buy" else "Selling"
            parts.append(f"{verb} {qty} {ticker}")
    for c in payload.get("watchlist_changes") or []:
        action = str(c.get("action", "")).lower()
        ticker = c.get("ticker")
        if action == "add" and ticker:
            parts.append(f"Added {ticker} to watchlist")
        elif action == "remove" and ticker:
            parts.append(f"Removed {ticker} from watchlist")
    if not parts:
        return "OK."
    return ". ".join(parts) + "."
