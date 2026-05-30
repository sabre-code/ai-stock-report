"""Build chart images (PNG bytes) from research data for embedding in the PDF."""
from __future__ import annotations

import io
import logging
from datetime import date

import matplotlib
matplotlib.use("Agg")   # non-interactive backend — must be set before pyplot import
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

from app.models.stock import PriceBar, QuarterlyFinancials, TechnicalSnapshot

logger = logging.getLogger(__name__)

_DPI = 150
_FIG_W, _FIG_H = 10, 4.5
_STYLE = {
    "axes.facecolor": "#f8f9fa",
    "figure.facecolor": "#ffffff",
    "axes.grid": True,
    "grid.color": "#dee2e6",
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.family": "DejaVu Sans",
}


def _to_png(fig: plt.Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=_DPI, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def build_price_chart(bars: list[PriceBar], snap: TechnicalSnapshot, ticker: str) -> bytes:
    """Price line chart with 50-day and 200-day moving averages."""
    if not bars:
        return b""
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))

        dates = [b.date for b in bars]
        closes = [b.close for b in bars]

        ax.plot(dates, closes, color="#0d6efd", linewidth=1.5, label="Close", zorder=3)

        if snap.ma_50 is not None and len(closes) >= 50:
            ma50 = [sum(closes[max(0, i - 49):i + 1]) / min(i + 1, 50) for i in range(len(closes))]
            ax.plot(dates, ma50, color="#fd7e14", linewidth=1.2, linestyle="--", label="MA 50", zorder=2)

        if snap.ma_200 is not None and len(closes) >= 200:
            ma200 = [sum(closes[max(0, i - 199):i + 1]) / min(i + 1, 200) for i in range(len(closes))]
            ax.plot(dates, ma200, color="#6f42c1", linewidth=1.2, linestyle="--", label="MA 200", zorder=2)

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        fig.autofmt_xdate(rotation=30, ha="right")
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.2f"))
        ax.set_title(f"{ticker} — 1-Year Price History", fontsize=13, fontweight="bold", pad=10)
        ax.set_ylabel("Price (USD)")
        ax.legend(fontsize=9)

    return _to_png(fig)


def build_revenue_chart(quarters: list[QuarterlyFinancials], ticker: str) -> bytes:
    """Grouped bar chart: quarterly revenue vs net income."""
    q = [qf for qf in quarters if qf.revenue is not None][:8]
    if not q:
        return b""

    q = list(reversed(q))   # oldest → newest
    labels = [qf.period for qf in q]
    revenues = [(qf.revenue or 0) / 1e9 for qf in q]
    net_incomes = [(qf.net_income or 0) / 1e9 for qf in q]

    x = range(len(labels))
    width = 0.38

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))
        ax.bar([i - width / 2 for i in x], revenues, width, label="Revenue", color="#0d6efd", alpha=0.85)
        ax.bar([i + width / 2 for i in x], net_incomes, width, label="Net Income", color="#198754", alpha=0.85)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:.1f}B"))
        ax.set_title(f"{ticker} — Quarterly Revenue & Net Income", fontsize=13, fontweight="bold", pad=10)
        ax.legend(fontsize=9)

    return _to_png(fig)


def build_margins_chart(quarters: list[QuarterlyFinancials], ticker: str) -> bytes:
    """Line chart: gross margin % and operating margin % by quarter."""
    q = [qf for qf in quarters if qf.gross_margin_pct is not None][:8]
    if not q:
        return b""

    q = list(reversed(q))
    labels = [qf.period for qf in q]
    gm = [qf.gross_margin_pct or 0 for qf in q]
    om = [qf.operating_margin_pct or 0 for qf in q]

    x = range(len(labels))

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=(_FIG_W, _FIG_H))
        ax.plot(list(x), gm, marker="o", color="#0d6efd", linewidth=1.8, markersize=5, label="Gross Margin")
        ax.plot(list(x), om, marker="s", color="#fd7e14", linewidth=1.8, markersize=5, label="Operating Margin")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))
        ax.set_title(f"{ticker} — Quarterly Margins", fontsize=13, fontweight="bold", pad=10)
        ax.legend(fontsize=9)

    return _to_png(fig)
