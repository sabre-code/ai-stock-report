"""Use Gemini to extract a canonical ticker symbol from a natural language query."""
from __future__ import annotations

import json
import logging

from app.services.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a financial data assistant. "
    "Your only job is to extract the stock ticker and full company name from the user's query. "
    "Return valid JSON only — no markdown, no explanation."
)

_PROMPT_TMPL = """Extract the stock ticker and company name from this request:
"{query}"

Return JSON exactly like:
{{"ticker": "NVDA", "company_name": "NVIDIA Corporation"}}
"""


async def resolve_ticker(query: str, gemini: GeminiClient) -> tuple[str, str]:
    """Return (ticker, company_name) derived from the free-text query."""
    prompt = _PROMPT_TMPL.format(query=query)
    raw = await gemini.generate_json(prompt, system=_SYSTEM)
    try:
        data = json.loads(raw)
        ticker = str(data.get("ticker", "")).upper().strip()
        company_name = str(data.get("company_name", ticker))
        if not ticker:
            raise ValueError("Empty ticker in response")
        logger.info("Resolved ticker: %s (%s)", ticker, company_name)
        return ticker, company_name
    except Exception as exc:
        logger.warning("Ticker resolution failed (%s), falling back to last word", exc)
        # Simple fallback: capitalise last meaningful word
        words = [w.strip("?.!,") for w in query.split() if w.strip("?.!,")]
        return words[-1].upper() if words else "UNKNOWN", query
