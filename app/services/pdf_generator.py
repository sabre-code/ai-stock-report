"""Assemble the final stock-report PDF using ReportLab."""
from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.report import ReportArtifact, ReportSection

logger = logging.getLogger(__name__)

# ── Palette ────────────────────────────────────────────────────────────────────
_NAVY = colors.HexColor("#0d1b2a")
_BLUE = colors.HexColor("#0d6efd")
_LIGHT = colors.HexColor("#f0f4f8")
_GRAY = colors.HexColor("#6c757d")
_GREEN = colors.HexColor("#198754")
_WHITE = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm


def _styles():
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "cover_title",
            fontSize=36,
            textColor=_WHITE,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            leading=44,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            fontSize=16,
            textColor=_WHITE,
            alignment=TA_CENTER,
            fontName="Helvetica",
            spaceAfter=6,
        ),
        "section_h1": ParagraphStyle(
            "section_h1",
            fontSize=16,
            textColor=_NAVY,
            fontName="Helvetica-Bold",
            spaceBefore=14,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            fontSize=9.5,
            textColor=colors.black,
            fontName="Helvetica",
            leading=15,
            spaceAfter=6,
        ),
        "caption": ParagraphStyle(
            "caption",
            fontSize=8,
            textColor=_GRAY,
            fontName="Helvetica-Oblique",
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "source": ParagraphStyle(
            "source",
            fontSize=8,
            textColor=_GRAY,
            fontName="Helvetica",
            leading=12,
        ),
    }


class _ColoredRect(Flowable):
    """A solid colored rectangle used for the cover background band."""

    def __init__(self, width: float, height: float, fill: colors.Color) -> None:
        super().__init__()
        self.width = width
        self.height = height
        self.fill = fill

    def draw(self) -> None:
        self.canv.setFillColor(self.fill)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)


def _to_reportlab_markup(text: str) -> str:
    """Convert a small markdown subset to ReportLab-safe inline markup."""
    converted = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # Drop stray markdown markers that could break XML-ish parsing.
    return converted.replace("**", "")


def _chart_image(png_bytes: bytes, max_width: float = PAGE_W - 2 * MARGIN) -> Image | None:
    if not png_bytes:
        return None
    try:
        img = Image(io.BytesIO(png_bytes))
        ratio = img.imageHeight / img.imageWidth
        img.drawWidth = max_width
        img.drawHeight = max_width * ratio
        return img
    except Exception as exc:
        logger.warning("Could not embed chart: %s", exc)
        return None


def generate_pdf(artifact: ReportArtifact, sources: list[str] | None = None) -> Path:
    """Render the full report to *artifact.pdf_path* and return the path."""
    artifact.pdf_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(artifact.pdf_path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=f"{artifact.ticker} Stock Report",
        author="AI Stock Report Generator",
    )

    s = _styles()
    story: list = []
    content_w = PAGE_W - 2 * MARGIN

    # ── Cover page ─────────────────────────────────────────────────────────────
    cover_table = Table(
        [[
            [
                Paragraph(artifact.company_name, s["cover_title"]),
                Spacer(1, 0.25 * cm),
                Paragraph(f"Ticker: {artifact.ticker}", s["cover_sub"]),
                Paragraph(
                    f"Report generated: {datetime.utcnow().strftime('%B %d, %Y')}",
                    s["cover_sub"],
                ),
            ]
        ]],
        colWidths=[content_w],
    )
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 26),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 26),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=_BLUE))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(
        "<i>This report was generated by an AI system using publicly available data. "
        "It is for informational purposes only and does not constitute investment advice.</i>",
        s["caption"],
    ))
    story.append(PageBreak())

    # ── Sections ───────────────────────────────────────────────────────────────
    for section in artifact.sections:
        story.append(Paragraph(section.title, s["section_h1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=_BLUE, spaceAfter=6))

        # Narrative: split by double newline into paragraphs
        for para_text in section.narrative.split("\n\n"):
            para_text = para_text.strip()
            if not para_text:
                continue
            story.append(Paragraph(_to_reportlab_markup(para_text), s["body"]))

        # Embedded chart
        if section.chart_png:
            chart_img = _chart_image(section.chart_png, max_width=content_w)
            if chart_img:
                story.append(Spacer(1, 0.3 * cm))
                story.append(chart_img)
                story.append(Paragraph(f"Chart: {section.title}", s["caption"]))

        story.append(Spacer(1, 0.5 * cm))

    # ── Sources ────────────────────────────────────────────────────────────────
    if sources:
        story.append(PageBreak())
        story.append(Paragraph("Data Sources", s["section_h1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=_BLUE, spaceAfter=6))
        for src in sources:
            story.append(Paragraph(f"• {src}", s["source"]))

    # ── Disclaimer ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_GRAY))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "DISCLAIMER: This report is generated by an automated AI system using publicly "
        "available data from Yahoo Finance, Google News RSS, and the SEC EDGAR database. "
        "It is for informational and educational purposes only. It does not constitute "
        "investment advice, a recommendation, or an offer or solicitation to buy or sell "
        "any security. Always consult a qualified financial professional before making "
        "investment decisions.",
        s["caption"],
    ))

    doc.build(story)
    logger.info("PDF written: %s (%d bytes)", artifact.pdf_path, artifact.pdf_path.stat().st_size)
    return artifact.pdf_path
