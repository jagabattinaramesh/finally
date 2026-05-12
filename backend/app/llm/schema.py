"""Pydantic models for the LLM structured-output contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Trade(BaseModel):
    """A buy or sell order the LLM wants to execute."""

    ticker: str = Field(min_length=1, max_length=10)
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)


class WatchlistChange(BaseModel):
    """A request to add or remove a ticker from the watchlist."""

    ticker: str = Field(min_length=1, max_length=10)
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    """Top-level structured response the LLM must return."""

    message: str
    trades: list[Trade] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)
