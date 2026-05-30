"""Domain models for the assembled report."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ReportSection:
    title: str
    narrative: str              # AI-generated markdown prose
    chart_png: bytes | None = None   # embedded chart image


@dataclass
class ReportArtifact:
    job_id: str
    ticker: str
    company_name: str
    pdf_path: Path
    sections: list[ReportSection] = field(default_factory=list)
