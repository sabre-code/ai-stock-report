"""Report-related API routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.dependencies import get_orchestrator
from app.orchestrator import StockReportOrchestrator
from app.schemas import ReportRequest, ReportResponse
from app.services.job_store import JobStatus, get_job_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportResponse, status_code=202)
async def create_report(
    request: ReportRequest,
    orchestrator: StockReportOrchestrator = Depends(get_orchestrator),
) -> ReportResponse:
    """Start a report job and return the job_id immediately."""
    job_id = orchestrator.new_job_id()
    return ReportResponse(
        job_id=job_id,
        status="pending",
        artifact_url=f"/reports/{job_id}/download",
    )


@router.get("/stream")
async def stream_report(
    query: str,
    ticker: str | None = None,
    orchestrator: StockReportOrchestrator = Depends(get_orchestrator),
) -> StreamingResponse:
    """
    SSE endpoint — starts the pipeline immediately and streams ProgressEvent
    JSON objects as server-sent events.

    Event format:
        event: <stage>
        data: <ProgressEvent JSON>
    """
    job_id = orchestrator.new_job_id()

    async def generator():
        # Send job_id as first event so the client can reference the artifact URL
        yield f"event: job_start\ndata: {{\"job_id\": \"{job_id}\"}}\n\n"
        async for event in orchestrator.run_and_stream(job_id, query, ticker):
            payload = event.model_dump_json()
            yield f"event: {event.stage}\ndata: {payload}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}/status")
async def report_status(job_id: str):
    """Poll for job status without streaming."""
    store = get_job_store()
    record = await store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job_id,
        "status": record.status,
        "error": record.error,
        "artifact_url": f"/reports/{job_id}/download" if record.pdf_path else None,
    }


@router.get("/{job_id}/download")
async def download_report(job_id: str):
    """Serve the generated PDF file."""
    store = get_job_store()
    record = await store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.status == JobStatus.FAILED:
        raise HTTPException(status_code=500, detail=f"Report failed: {record.error}")
    if record.status != JobStatus.DONE or record.pdf_path is None:
        raise HTTPException(status_code=202, detail="Report is still being generated")
    if not record.pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
    return FileResponse(
        path=str(record.pdf_path),
        media_type="application/pdf",
        filename=f"{record.ticker}_stock_report.pdf",
    )
