"""Report agent — uses Gemini to write each section narrative, then assembles the PDF."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import uuid4

from app.agents.base import BaseAgent
from app.config import get_settings
from app.models.report import ReportArtifact, ReportSection
from app.models.stock import StockResearch
from app.schemas import ProgressEvent
from app.services.chart_builder import (
    build_margins_chart,
    build_price_chart,
    build_revenue_chart,
)
from app.services.gemini_client import GeminiClient
from app.services.pdf_generator import generate_pdf

logger = logging.getLogger(__name__)


def _fmt_num(val: float | None, prefix: str = "", suffix: str = "", decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    if abs(val) >= 1e12:
        return f"{prefix}{val / 1e12:.{decimals}f}T{suffix}"
    if abs(val) >= 1e9:
        return f"{prefix}{val / 1e9:.{decimals}f}B{suffix}"
    if abs(val) >= 1e6:
        return f"{prefix}{val / 1e6:.{decimals}f}M{suffix}"
    return f"{prefix}{val:.{decimals}f}{suffix}"


def _build_research_context(r: StockResearch) -> str:
    """Serialize key research data into a compact text context for Gemini prompts."""
    lines: list[str] = []

    lines.append(f"=== {r.company.name} ({r.ticker}) ===")
    lines.append(f"Sector: {r.company.sector}  Industry: {r.company.industry}")
    lines.append(f"Market Cap: {_fmt_num(r.company.market_cap, '$')}")
    lines.append(f"Description: {r.company.description[:600]}")
    lines.append("")

    t = r.technicals
    lines.append("--- PRICE ---")
    lines.append(f"Current: ${t.current_price}  Day change: {t.day_change_pct:.2f}%")
    lines.append(f"52w High: ${t.week_52_high}  52w Low: ${t.week_52_low}")
    lines.append(f"MA50: {t.ma_50}  MA200: {t.ma_200}")
    lines.append(
        f"Returns — 1M: {t.one_month_return_pct}%  3M: {t.three_month_return_pct}%  "
        f"6M: {t.six_month_return_pct}%  1Y: {t.one_year_return_pct}%  YTD: {t.ytd_return_pct}%"
    )
    lines.append("")

    if r.quarterly_financials:
        lines.append("--- QUARTERLY FINANCIALS (most recent first) ---")
        for qf in r.quarterly_financials[:4]:
            lines.append(
                f"{qf.period}: Rev {_fmt_num(qf.revenue, '$')}  "
                f"Net {_fmt_num(qf.net_income, '$')}  "
                f"GrossMargin {qf.gross_margin_pct}%  OpMargin {qf.operating_margin_pct}%"
            )
        lines.append("")

    if r.valuation:
        v = r.valuation
        lines.append("--- VALUATION ---")
        lines.append(
            f"P/E: {v.pe_ratio}  Fwd P/E: {v.forward_pe}  P/B: {v.pb_ratio}  "
            f"P/S: {v.ps_ratio}  EV/EBITDA: {v.ev_ebitda}  PEG: {v.peg_ratio}"
        )
        lines.append(
            f"Beta: {v.beta}  Div Yield: {v.dividend_yield_pct}%  "
            f"Analyst Target: {_fmt_num(v.analyst_target_price, '$')}  "
            f"Recommendation: {v.analyst_recommendation}"
        )
        lines.append("")

    if r.news:
        lines.append("--- RECENT NEWS ---")
        for item in r.news[:10]:
            lines.append(f"• [{item.source}] {item.title} ({item.published})")
        lines.append("")

    if r.filings:
        lines.append("--- RECENT SEC FILINGS ---")
        for f in r.filings:
            lines.append(f"• {f.form_type} filed {f.filed_date}: {f.description}")

    return "\n".join(lines)


async def _write_section(
    gemini: GeminiClient,
    section_title: str,
    instruction: str,
    context: str,
) -> str:
    system = (
        "You are a senior equity research analyst writing a professional stock report. "
        "Write clear, concise, evidence-backed prose. Use specific numbers from the data. "
        "Do not use markdown headers. Use paragraph breaks (double newline) to separate thoughts. "
        "Do not include disclaimers — those appear separately."
    )
    prompt = (
        f"Research data:\n{context}\n\n"
        f"Write the '{section_title}' section of the report.\n"
        f"Instructions: {instruction}\n"
        f"Keep it to 2-4 focused paragraphs."
    )
    return await gemini.generate(prompt, system=system, temperature=0.35, max_output_tokens=800)


class ReportAgent(BaseAgent):
    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini

    @property
    def name(self) -> str:
        return "ReportAgent"

    async def run(  # type: ignore[override]
        self,
        research: StockResearch,
        job_id: str,
        emit,   # callable(ProgressEvent)
    ) -> Path:
        ctx = _build_research_context(research)
        ticker = research.ticker
        settings = get_settings()

        # ── Build charts ────────────────────────────────────────────────────
        await emit(ProgressEvent(stage="report", message="Building price chart..."))
        price_png = build_price_chart(research.price_history, research.technicals, ticker)

        await emit(ProgressEvent(stage="report", message="Building revenue & earnings chart..."))
        revenue_png = build_revenue_chart(research.quarterly_financials, ticker)

        await emit(ProgressEvent(stage="report", message="Building margins chart..."))
        margins_png = build_margins_chart(research.quarterly_financials, ticker)

        # ── Generate section narratives via Gemini ──────────────────────────
        sections_spec = [
            (
                "Executive Summary",
                "Write a crisp 2-paragraph executive summary of the investment case: "
                "key financials, recent momentum, and headline valuation. "
                "Lead with a clear verdict on the stock's current standing.",
                None,
            ),
            (
                "Company Overview",
                "Describe the business model, what the company does, its sector position, "
                "employee count, and notable competitive strengths.",
                None,
            ),
            (
                "Price Performance",
                "Analyse price performance across all available time periods, the 52-week range, "
                "relationship to MA50 and MA200, and what the technicals suggest about trend direction.",
                price_png,
            ),
            (
                "Financial Performance",
                "Discuss the most recent quarterly results including revenue trajectory, "
                "profitability trend, and margin evolution. Highlight notable beats or misses.",
                revenue_png,
            ),
            (
                "Margin Analysis",
                "Break down gross margin, operating margin, and net margin trends. "
                "Comment on margin expansion or compression and the likely drivers.",
                margins_png,
            ),
            (
                "Valuation",
                "Evaluate the current valuation multiples (P/E, forward P/E, P/B, EV/EBITDA, PEG). "
                "Contextualise against the sector and the company's growth profile. "
                "Include analyst consensus target and recommendation if available.",
                None,
            ),
            (
                "News & Recent Catalysts",
                "Summarise the most significant recent headlines and what they signal "
                "about business momentum, product pipeline, regulatory environment, or macro exposure.",
                None,
            ),
            (
                "SEC Filings",
                "Note the most recent filings and any material disclosures or risks mentioned.",
                None,
            ),
            (
                "Risks & Red Flags",
                "Identify the top 3-5 investment risks: macro, competitive, regulatory, "
                "valuation, or execution risks. Be specific and data-driven.",
                None,
            ),
            (
                "Investment Thesis",
                "Synthesise all evidence into a balanced investment thesis. "
                "State the bull case, bear case, and a neutral view on the risk/reward. "
                "Do not make a buy/sell recommendation — present the evidence objectively.",
                None,
            ),
        ]

        report_sections: list[ReportSection] = []
        total = len(sections_spec)
        for idx, (title, instruction, chart_png) in enumerate(sections_spec, 1):
            await emit(ProgressEvent(
                stage="report",
                message=f"Writing section {idx}/{total}: {title}...",
            ))
            narrative = await _write_section(self._gemini, title, instruction, ctx)
            report_sections.append(ReportSection(
                title=title,
                narrative=narrative,
                chart_png=chart_png,
            ))

        # ── Assemble PDF ────────────────────────────────────────────────────
        await emit(ProgressEvent(stage="report", message="Assembling final PDF report..."))

        pdf_path = settings.reports_dir / f"{job_id}.pdf"
        artifact = ReportArtifact(
            job_id=job_id,
            ticker=ticker,
            company_name=research.company.name,
            pdf_path=pdf_path,
            sections=report_sections,
        )
        sources = [
            "Yahoo Finance — market data, financials, and valuation (yfinance)",
            "Google News RSS — recent news headlines",
            "SEC EDGAR — regulatory filings (https://www.sec.gov/)",
            f"Report generated: {__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        ]
        generate_pdf(artifact, sources=sources)
        return pdf_path
