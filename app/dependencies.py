"""FastAPI dependency injection providers."""
from __future__ import annotations

from app.orchestrator import StockReportOrchestrator
from app.services.gemini_client import GeminiClient
from app.services.job_store import JobStore, get_job_store


def get_gemini_client() -> GeminiClient:
    return GeminiClient()


def get_orchestrator() -> StockReportOrchestrator:
    return StockReportOrchestrator(
        gemini=get_gemini_client(),
        job_store=get_job_store(),
    )
