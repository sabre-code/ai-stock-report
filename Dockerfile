# ── Stage 1: dependency installation (cached layer) ──────────────────────────
FROM python:3.12-slim AS deps

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy only the lock files first so this layer is cached as long as
# dependencies do not change.
COPY pyproject.toml uv.lock ./

# Install all dependencies into /app/.venv (excludes the local package itself)
RUN uv sync --frozen --no-install-project --no-dev

# ── Stage 2: final image ──────────────────────────────────────────────────────
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Re-copy lock files and bring over the pre-built .venv
COPY pyproject.toml uv.lock ./
COPY --from=deps /app/.venv /app/.venv

# Copy application source and install the local package into the existing .venv
COPY app/ ./app/
RUN uv sync --frozen --no-dev

# Reports directory — override with an EFS/volume mount in production
RUN mkdir -p /app/reports

EXPOSE 8000

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["ai-stock-report-api"]
