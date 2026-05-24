"""Fetch company info, financials, and valuation via yfinance."""
from __future__ import annotations

import asyncio
import logging

import yfinance as yf

from app.models.stock import CompanyInfo, QuarterlyFinancials, ValuationMetrics

logger = logging.getLogger(__name__)


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if (f != f) else round(f, 4)
    except Exception:
        return None


def _safe_str(val, default: str = "") -> str:
    return str(val) if val and str(val) != "nan" else default


def _pct(num: float | None, denom: float | None) -> float | None:
    if num is not None and denom and denom != 0:
        return round(num / denom * 100, 2)
    return None


def _fetch(ticker: str) -> tuple[CompanyInfo, list[QuarterlyFinancials], ValuationMetrics]:
    tk = yf.Ticker(ticker)
    info = tk.info or {}

    company = CompanyInfo(
        ticker=ticker,
        name=_safe_str(info.get("longName"), ticker),
        sector=_safe_str(info.get("sector"), "N/A"),
        industry=_safe_str(info.get("industry"), "N/A"),
        description=_safe_str(info.get("longBusinessSummary"), "No description available."),
        country=_safe_str(info.get("country"), "N/A"),
        employees=info.get("fullTimeEmployees"),
        website=_safe_str(info.get("website"), ""),
        market_cap=_safe_float(info.get("marketCap")),
    )

    # ── Quarterly financials ────────────────────────────────────────────────
    quarters: list[QuarterlyFinancials] = []
    try:
        qf = tk.quarterly_income_stmt
        if qf is not None and not qf.empty:
            for col in qf.columns[:8]:   # most recent 8 quarters
                period_label = col.strftime("%b %Y") if hasattr(col, "strftime") else str(col)
                rev = _safe_float(qf.loc["Total Revenue", col]) if "Total Revenue" in qf.index else None
                gp = _safe_float(qf.loc["Gross Profit", col]) if "Gross Profit" in qf.index else None
                oi = _safe_float(qf.loc["Operating Income", col]) if "Operating Income" in qf.index else None
                ni = _safe_float(qf.loc["Net Income", col]) if "Net Income" in qf.index else None
                quarters.append(QuarterlyFinancials(
                    period=period_label,
                    revenue=rev,
                    gross_profit=gp,
                    operating_income=oi,
                    net_income=ni,
                    gross_margin_pct=_pct(gp, rev),
                    operating_margin_pct=_pct(oi, rev),
                    net_margin_pct=_pct(ni, rev),
                    eps=_safe_float(
                        info.get("trailingEps") if col == qf.columns[0] else None
                    ),
                ))
    except Exception as exc:
        logger.warning("Quarterly financials fetch failed: %s", exc)

    # ── Valuation ──────────────────────────────────────────────────────────
    valuation = ValuationMetrics(
        pe_ratio=_safe_float(info.get("trailingPE")),
        forward_pe=_safe_float(info.get("forwardPE")),
        pb_ratio=_safe_float(info.get("priceToBook")),
        ps_ratio=_safe_float(info.get("priceToSalesTrailing12Months")),
        ev_ebitda=_safe_float(info.get("enterpriseToEbitda")),
        peg_ratio=_safe_float(info.get("pegRatio")),
        dividend_yield_pct=_safe_float(info.get("dividendYield")) and
                           round((_safe_float(info.get("dividendYield")) or 0) * 100, 4),
        beta=_safe_float(info.get("beta")),
        analyst_target_price=_safe_float(info.get("targetMeanPrice")),
        analyst_recommendation=_safe_str(info.get("recommendationKey"), "N/A"),
    )

    return company, quarters, valuation


async def fetch_fundamentals(ticker: str) -> tuple[CompanyInfo, list[QuarterlyFinancials], ValuationMetrics]:
    return await asyncio.to_thread(_fetch, ticker)
