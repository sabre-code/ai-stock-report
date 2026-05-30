"""FastAPI application entry point."""
from __future__ import annotations

import logging
import logging.config

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import reports

# ── Logging ────────────────────────────────────────────────────────────────────
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
    },
    "root": {"level": "INFO", "handlers": ["console"]},
})

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Stock Report API",
    version="0.2.0",
    description="Agentic stock report generator — SSE progress + PDF artifact.",
)

app.include_router(reports.router)


@app.get("/health", tags=["meta"])
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": "0.2.0"})


# ── Dev runner ─────────────────────────────────────────────────────────────────
def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )

