"""Fetch recent SEC filings for a company using the free EDGAR REST API."""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import get_settings
from app.models.stock import FilingSummary

logger = logging.getLogger(__name__)

_EDGAR_CIK_URL = "https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=10-K%2C10-Q%2C8-K&dateRange=custom&startdt=2024-01-01&enddt=2099-01-01&_source=hits.hits._source.period_of_report,hits.hits._source.file_date,hits.hits._source.form_type,hits.hits._source.display_names,hits.hits._source.period_of_report"
_EDGAR_SEARCH_URL = (
    "https://efts.sec.gov/LATEST/search-index"
    "?q=%22{ticker}%22"
    "&forms=10-K%2C10-Q%2C8-K"
    "&dateRange=custom&startdt=2023-01-01&enddt=2099-01-01"
)
_EDGAR_FILING_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type={form}&dateb=&owner=include&count={count}&search_text=&output=atom"
_EDGAR_VIEW_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no_dashes}/{document}"

_HEADERS = {
    "User-Agent": "ai-stock-report contact@example.com",
    "Accept": "application/json",
}


def _parse_filings(data: dict, max_items: int, ticker: str) -> list[FilingSummary]:
    hits = data.get("hits", {}).get("hits", [])
    results: list[FilingSummary] = []
    for hit in hits[:max_items]:
        src = hit.get("_source", {})
        form_type = src.get("form_type", "")
        filed = src.get("file_date", "")
        display = src.get("display_names", [ticker])
        name = display[0] if display else ticker
        accession = hit.get("_id", "").replace("-", "")
        cik = hit.get("_source", {}).get("entity_id", "")
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form_type}&dateb=&owner=include&count=5"
        results.append(FilingSummary(
            form_type=form_type,
            filed_date=filed,
            description=f"{form_type} filed by {name}",
            url=url,
        ))
    return results


async def _async_fetch(ticker: str, max_items: int) -> list[FilingSummary]:
    url = _EDGAR_SEARCH_URL.format(ticker=ticker)
    async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            filings = _parse_filings(data, max_items, ticker)
            logger.info("SEC EDGAR: %d filings for %s", len(filings), ticker)
            return filings
        except Exception as exc:
            logger.warning("SEC EDGAR fetch failed for %s: %s", ticker, exc)
            return []


async def fetch_sec_filings(ticker: str) -> list[FilingSummary]:
    max_items = get_settings().sec_filings_max
    return await _async_fetch(ticker, max_items)
