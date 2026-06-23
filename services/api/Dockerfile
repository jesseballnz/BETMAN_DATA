# syntax=docker/dockerfile:1
# BETMAN Data API — Dockerfile
#
# Multi-stage build:
#   base     — Python + uv
#   deps     — install Python dependencies
#   production — final minimal image

FROM python:3.11-slim AS base
WORKDIR /app
RUN pip install --no-cache-dir uv==0.4.18

# ── Install dependencies ──────────────────────────────────────────────────────
FROM base AS deps
COPY pyproject.toml .
# Install production deps only (no dev extras)
RUN uv pip install --system --no-cache -e .

# ── Production image ──────────────────────────────────────────────────────────
FROM deps AS production
# Copy application source
COPY app/ ./app/

# Non-root user for security
RUN addgroup --system betman && adduser --system --ingroup betman betman
USER betman

EXPOSE 8000

# uvicorn with 2 workers by default; override via CMD or environment
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
