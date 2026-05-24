"""
Central orchestrator — the only entry point for the report pipeline.

Flow:
  1. Resolve ticker via Gemini
  2. Research agent gathers all market/news/filing data (tools run in parallel)
  3. Report agent writes section narratives with Gemini + assembles PDF
  4. Progress events emitted at every stage over an async queue → SSE
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator
from uuid import uuid4

from app.agents.report import ReportAgent
from app.agents.research import ResearchAgent
from app.schemas import ProgressEvent, ReportResponse
from app.services.gemini_client import GeminiClient
from app.services.job_store import JobStore
from app.tools.ticker_resolve import resolve_ticker

logger = logging.getLogger(__name__)


class StockReportOrchestrator:
    def __init__(self, gemini: GeminiClient, job_store: JobStore) -> None:
        self._gemini = gemini
        self._job_store = job_store
        self._research = ResearchAgent()
        self._report = ReportAgent(gemini)

    def new_job_id(self) -> str:
        return str(uuid4())

    async def run_and_stream(
        self,
        job_id: str,
        query: str,
        explicit_ticker: str | None = None,
    ) -> AsyncIterator[ProgressEvent]:
        """
        Async generator that drives the full pipeline and yields ProgressEvents.
        The caller converts each event to an SSE line and flushes it to the client.
        """
        queue: asyncio.Queue[ProgressEvent | Exception] = asyncio.Queue()

        async def emit(event: ProgressEvent) -> None:
            await queue.put(event)

        async def pipeline() -> None:
            try:
                # ── 1. Resolve ticker ─────────────────────────────────────
                await emit(ProgressEvent(stage="parse", message="Resolving company and ticker..."))
                if explicit_ticker:
                    ticker = explicit_ticker.upper().strip()
                    company_name = ticker
                else:
                    ticker, company_name = await resolve_ticker(query, self._gemini)

                await self._job_store.create(job_id, query, ticker)
                await emit(ProgressEvent(stage="parse", message=f"Identified: {company_name} ({ticker})"))

                # ── 2. Research ───────────────────────────────────────────
                research = await self._research.run(ticker, company_name, emit)

                # ── 3. Report + PDF ───────────────────────────────────────
                pdf_path: Path = await self._report.run(research, job_id, emit)
                await self._job_store.set_pdf(job_id, pdf_path)

                await emit(ProgressEvent(
                    stage="complete",
                    message=f"Report ready for {company_name} ({ticker})",
                    done=True,
                    artifact_url=f"/reports/{job_id}/download",
                ))
            except Exception as exc:
                logger.exception("Pipeline error for job %s", job_id)
                await self._job_store.set_error(job_id, str(exc))
                await queue.put(exc)

        task = asyncio.create_task(pipeline())

        while True:
            item = await queue.get()
            if isinstance(item, Exception):
                yield ProgressEvent(
                    stage="error",
                    message=f"Report generation failed: {item}",
                    done=True,
                )
                break
            yield item
            if item.done:
                break

        await task   # propagate any unhandled exception

    def build_response(self, job_id: str, artifact_url: str | None = None) -> ReportResponse:
        return ReportResponse(job_id=job_id, status="completed", artifact_url=artifact_url)

