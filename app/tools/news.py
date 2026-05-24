"""Fetch recent news headlines via Google News RSS (no API key needed)."""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote_plus

import feedparser

from app.config import get_settings
from app.models.stock import NewsItem

logger = logging.getLogger(__name__)

_RSS_TMPL = (
    "https://news.google.com/rss/search"
    "?q={query}+stock&hl=en-US&gl=US&ceid=US:en"
)


def _fetch(ticker: str, company_name: str, max_items: int) -> list[NewsItem]:
    query = quote_plus(f"{company_name} {ticker}")
    url = _RSS_TMPL.format(query=query)
    feed = feedparser.parse(url)

    items: list[NewsItem] = []
    for entry in feed.entries[:max_items]:
        items.append(NewsItem(
            title=entry.get("title", ""),
            source=entry.get("source", {}).get("title", "Unknown"),
            published=entry.get("published", ""),
            url=entry.get("link", ""),
            summary=entry.get("summary", "")[:500],
        ))

    if not items:
        logger.warning("No news found for %s / %s", ticker, company_name)

    return items


async def fetch_news(ticker: str, company_name: str) -> list[NewsItem]:
    max_items = get_settings().news_max_items
    return await asyncio.to_thread(_fetch, ticker, company_name, max_items)
