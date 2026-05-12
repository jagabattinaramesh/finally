"""Chat REST endpoint. Delegates to app.llm.service.process_message."""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.deps import get_db, get_market
from app.llm import process_message
from app.market import MarketSource

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


@router.post("")
async def post_chat(
    req: ChatRequest,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
    market: MarketSource = Depends(get_market),
) -> dict[str, Any]:
    try:
        return await process_message(conn, market, req.message, request=request)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
