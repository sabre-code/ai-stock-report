"""In-memory job state tracker for report generation requests."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class JobRecord:
    job_id: str
    query: str
    ticker: str
    status: JobStatus = JobStatus.PENDING
    pdf_path: Path | None = None
    error: str | None = None
    progress_events: list[dict] = field(default_factory=list)


class JobStore:
    """Thread-safe in-memory store keyed by job_id."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, job_id: str, query: str, ticker: str) -> JobRecord:
        async with self._lock:
            record = JobRecord(job_id=job_id, query=query, ticker=ticker)
            self._jobs[job_id] = record
            return record

    async def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    async def update_status(self, job_id: str, status: JobStatus) -> None:
        async with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].status = status

    async def set_pdf(self, job_id: str, path: Path) -> None:
        async with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].pdf_path = path
                self._jobs[job_id].status = JobStatus.DONE

    async def set_error(self, job_id: str, error: str) -> None:
        async with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].error = error
                self._jobs[job_id].status = JobStatus.FAILED


# Singleton — shared across the process
_store = JobStore()


def get_job_store() -> JobStore:
    return _store
