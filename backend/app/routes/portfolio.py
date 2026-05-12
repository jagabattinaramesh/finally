"""Portfolio REST endpoints."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import list_snapshots
from app.deps import get_db, get_market
from app.market import MarketSource
from app.portfolio import TradeError, build_portfolio, execute_trade

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    ticker: str = Field(min_length=1)
    side: str
    quantity: float = Field(gt=0)


@router.get("")
def get_portfolio(
    conn: sqlite3.Connection = Depends(get_db),
    market: MarketSource = Depends(get_market),
) -> dict[str, Any]:
    return build_portfolio(conn, market)


@router.post("/trade")
def post_trade(
    req: TradeRequest,
    conn: sqlite3.Connection = Depends(get_db),
    market: MarketSource = Depends(get_market),
) -> dict[str, Any]:
    try:
        return execute_trade(conn, market, req.ticker, req.side, req.quantity)
    except TradeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/history")
def get_history(
    conn: sqlite3.Connection = Depends(get_db),
) -> list[dict[str, Any]]:
    return list_snapshots(conn)
