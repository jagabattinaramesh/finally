"""LLM chat integration for FinAlly.

Public surface:

- ``ChatResponse`` — structured output schema returned by the model.
- ``process_message`` — public entry point used by the /api/chat route.
"""

from .schema import ChatResponse, Trade, WatchlistChange
from .service import process_message

__all__ = [
    "ChatResponse",
    "Trade",
    "WatchlistChange",
    "process_message",
]
