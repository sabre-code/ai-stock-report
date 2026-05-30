"""Domain models for stock research data."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class PriceBar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class TechnicalSnapshot:
    current_price: float
    prev_close: float
    day_change_pct: float
    week_52_high: float
    week_52_low: float
    ma_50: float | None
    ma_200: float | None
    ytd_return_pct: float | None
    one_month_return_pct: float | None
    three_month_return_pct: float | None
    six_month_return_pct: float | None
    one_year_return_pct: float | None


@dataclass
class CompanyInfo:
    ticker: str
    name: str
    sector: str
    industry: str
    description: str
    country: str
    employees: int | None
    website: str
    market_cap: float | None


@dataclass
class QuarterlyFinancials:
    period: str           # e.g. "Q1 2025"
    revenue: float | None
    gross_profit: float | None
    operating_income: float | None
    net_income: float | None
    gross_margin_pct: float | None
    operating_margin_pct: float | None
    net_margin_pct: float | None
    eps: float | None


@dataclass
class ValuationMetrics:
    pe_ratio: float | None
    forward_pe: float | None
    pb_ratio: float | None
    ps_ratio: float | None
    ev_ebitda: float | None
    peg_ratio: float | None
    dividend_yield_pct: float | None
    beta: float | None
    analyst_target_price: float | None
    analyst_recommendation: str | None


@dataclass
class NewsItem:
    title: str
    source: str
    published: str   # raw string from RSS
    url: str
    summary: str


@dataclass
class FilingSummary:
    form_type: str    # 10-K, 10-Q, 8-K
    filed_date: str
    description: str
    url: str


@dataclass
class StockResearch:
    """Full evidence bundle built by the research agent."""
    ticker: str
    company: CompanyInfo
    technicals: TechnicalSnapshot
    price_history: list[PriceBar]
    quarterly_financials: list[QuarterlyFinancials]   # most recent first
    valuation: ValuationMetrics
    news: list[NewsItem]
    filings: list[FilingSummary]
    errors: list[str] = field(default_factory=list)   # non-fatal collection errors
