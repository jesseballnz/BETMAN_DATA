# syntax=docker/dockerfile:1
# BETMAN Consumer Service — Dockerfile
#
# Multi-stage build — same pattern as the API service.

FROM python:3.11-slim AS base
WORKDIR /app
RUN pip install --no-cache-dir uv==0.4.18

FROM base AS deps
COPY pyproject.toml .
RUN uv pip install --system --no-cache -e .

FROM deps AS production
COPY app/ ./app/

RUN addgroup --system betman && adduser --system --ingroup betman betman
USER betman

# The consumer is a long-running async process, not an HTTP server
CMD ["python", "-m", "app.main"]
