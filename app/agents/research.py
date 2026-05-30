"""Research agent — runs all data-fetch tools in parallel and builds a StockResearch bundle."""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from app.agents.base import BaseAgent
from app.models.stock import CompanyInfo, StockResearch, TechnicalSnapshot
from app.schemas import ProgressEvent
from app.services.gemini_client import GeminiClient
from app.tools import fundamentals, market_data, news, sec_filings

logger = logging.getLogger(__name__)

_UNKNOWN_COMPANY = CompanyInfo(
    ticker="",
    name="Unknown",
    sector="N/A",
    industry="N/A",
    description="No information available.",
    country="N/A",
    employees=None,
    website="",
    market_cap=None,
)
_UNKNOWN_SNAP = TechnicalSnapshot(
    current_price=0.0,
    prev_close=0.0,
    day_change_pct=0.0,
    week_52_high=0.0,
    week_52_low=0.0,
    ma_50=None,
    ma_200=None,
    ytd_return_pct=None,
    one_month_return_pct=None,
    three_month_return_pct=None,
    six_month_return_pct=None,
    one_year_return_pct=None,
)


class ResearchAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "ResearchAgent"

    async def run(  # type: ignore[override]
        self,
        ticker: str,
        company_name: str,
        emit,   # callable(ProgressEvent)
    ) -> StockResearch:
        errors: list[str] = []

        await emit(ProgressEvent(stage="research", message=f"Fetching market data for {ticker}..."))
        price_task = asyncio.create_task(market_data.fetch_market_data(ticker))

        await emit(ProgressEvent(stage="research", message=f"Fetching fundamentals for {ticker}..."))
        fund_task = asyncio.create_task(fundamentals.fetch_fundamentals(ticker))

        await emit(ProgressEvent(stage="research", message=f"Fetching news for {company_name}..."))
        news_task = asyncio.create_task(news.fetch_news(ticker, company_name))

        await emit(ProgressEvent(stage="research", message=f"Fetching SEC filings for {ticker}..."))
        filings_task = asyncio.create_task(sec_filings.fetch_sec_filings(ticker))

        # Await all; tolerate individual failures
        try:
            bars, snap = await price_task
        except Exception as exc:
            logger.error("Market data error: %s", exc)
            errors.append(f"Market data: {exc}")
            bars, snap = [], None

        try:
            company, quarters, valuation = await fund_task
        except Exception as exc:
            logger.error("Fundamentals error: %s", exc)
            errors.append(f"Fundamentals: {exc}")
            company, quarters, valuation = _UNKNOWN_COMPANY, [], None  # type: ignore[assignment]

        try:
            news_items = await news_task
        except Exception as exc:
            logger.error("News error: %s", exc)
            errors.append(f"News: {exc}")
            news_items = []

        try:
            filing_items = await filings_task
        except Exception as exc:
            logger.error("SEC filings error: %s", exc)
            errors.append(f"SEC filings: {exc}")
            filing_items = []

        company.ticker = ticker
        if company.name in ("Unknown", "") and company_name:
            company.name = company_name

        await emit(ProgressEvent(stage="research", message="Research complete. Building evidence bundle..."))

        return StockResearch(
            ticker=ticker,
            company=company,
            technicals=snap or _UNKNOWN_SNAP,
            price_history=bars,
            quarterly_financials=quarters,
            valuation=valuation,  # type: ignore[arg-type]
            news=news_items,
            filings=filing_items,
            errors=errors,
        )
