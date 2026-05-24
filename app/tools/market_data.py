"""Fetch price history and technical snapshot via yfinance."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

import yfinance as yf

from app.config import get_settings
from app.models.stock import PriceBar, TechnicalSnapshot

logger = logging.getLogger(__name__)


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if (f != f) else f   # NaN guard
    except Exception:
        return None


def _pct_change(start: float | None, end: float | None) -> float | None:
    if start and end and start != 0:
        return round((end - start) / abs(start) * 100, 2)
    return None


def _fetch(ticker: str, days: int) -> tuple[list[PriceBar], TechnicalSnapshot | None]:
    """Blocking yfinance call — run in thread pool."""
    period_start = date.today() - timedelta(days=days)
    tk = yf.Ticker(ticker)
    hist = tk.history(start=period_start.isoformat(), auto_adjust=True)

    if hist.empty:
        logger.warning("No price history for %s", ticker)
        return [], None

    bars: list[PriceBar] = []
    for ts, row in hist.iterrows():
        bars.append(PriceBar(
            date=ts.date(),
            open=_safe_float(row["Open"]) or 0.0,
            high=_safe_float(row["High"]) or 0.0,
            low=_safe_float(row["Low"]) or 0.0,
            close=_safe_float(row["Close"]) or 0.0,
            volume=int(row["Volume"]) if row["Volume"] == row["Volume"] else 0,
        ))

    closes = [b.close for b in bars]
    current = closes[-1] if closes else 0.0
    prev_close = closes[-2] if len(closes) > 1 else current

    def ma(n: int) -> float | None:
        if len(closes) >= n:
            return round(sum(closes[-n:]) / n, 4)
        return None

    # period returns
    def ret(offset_days: int) -> float | None:
        idx = max(0, len(bars) - offset_days)
        past = bars[idx].close if idx < len(bars) else None
        return _pct_change(past, current)

    # YTD: find first bar on or after Jan 1 this year
    this_year = date.today().year
    ytd_start = next((b.close for b in bars if b.date.year == this_year), None)

    snap = TechnicalSnapshot(
        current_price=round(current, 4),
        prev_close=round(prev_close, 4),
        day_change_pct=_pct_change(prev_close, current) or 0.0,
        week_52_high=round(max(b.high for b in bars), 4),
        week_52_low=round(min(b.low for b in bars), 4),
        ma_50=ma(50),
        ma_200=ma(200),
        ytd_return_pct=_pct_change(ytd_start, current),
        one_month_return_pct=ret(21),
        three_month_return_pct=ret(63),
        six_month_return_pct=ret(126),
        one_year_return_pct=ret(252),
    )
    return bars, snap


async def fetch_market_data(ticker: str) -> tuple[list[PriceBar], TechnicalSnapshot | None]:
    days = get_settings().price_history_days
    return await asyncio.to_thread(_fetch, ticker, days)
