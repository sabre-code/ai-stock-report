from __future__ import annotations

from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    query: str = Field(min_length=1, description="User request, e.g. generate a report for NVIDIA")
    ticker: str | None = Field(default=None, description="Optional explicit ticker symbol")


class ProgressEvent(BaseModel):
    stage: str
    message: str
    done: bool = False
    artifact_url: str | None = None


class ReportResponse(BaseModel):
    job_id: str
    status: str
    artifact_url: str | None = None
