# syntax=docker/dockerfile:1.6
# ──────────────────────────────────────────────────────────────────────────────
# BEEtexting Token Service — production container image
#
# Drives install from pyproject.toml + uv.lock so new deps in pyproject
# (Prometheus instrumentator, OpenTelemetry) flow into the image without
# editing this file again. CMD is wrapped with opentelemetry-instrument;
# when OTEL_* env vars are set by docker-compose, traces ship via OTLP.
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

WORKDIR /app

# Pull `uv` from its official image. Much faster than pip for rebuilds.
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

# ── Dependency layer ───────────────────────────────────────────────────────
# Cached as long as pyproject.toml + uv.lock don't change. --no-install-project
# installs deps only (we don't package this service as a wheel).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Put the venv's bin on PATH so `opentelemetry-bootstrap`, `python`, and
# `opentelemetry-instrument` resolve without a `uv run` prefix.
ENV PATH="/app/.venv/bin:$PATH"

# Install OTel auto-instrumentors matching the deps we just installed
# (fastapi, httpx, logging, asgi, stdlib). Idempotent; safe to re-run.
RUN opentelemetry-bootstrap -a install

# ── Python runtime tweaks ───────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ── Application code ───────────────────────────────────────────────────────
COPY main.py .
COPY src/ src/

# ── Network & healthcheck ──────────────────────────────────────────────────
EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8100/api/v1/ping', timeout=3).status == 200 else sys.exit(1)" \
    || exit 1

ENV APP_HOST=0.0.0.0 \
    APP_PORT=8100

# opentelemetry-instrument wraps the real process. Inert when OTEL env
# vars are absent, so the image runs fine standalone (dev / tests).
CMD ["opentelemetry-instrument", "python", "main.py"]
