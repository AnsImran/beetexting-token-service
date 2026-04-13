# syntax=docker/dockerfile:1.6
# ──────────────────────────────────────────────────────────────────────────────
# BEEtexting Token Service — production container image
#
# Produces a slim Python 3.12 image that runs the FastAPI token service.
# Build locally:
#     docker build -t beetexting-token-service:dev .
# Published image (CI):
#     ghcr.io/ansimran/beetexting-token-service/token-service:latest
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

WORKDIR /app

# ── Runtime dependencies ────────────────────────────────────────────────────
# Install exactly what the service needs, with version pins matching
# pyproject.toml.  `--no-cache-dir` keeps the layer small.
RUN pip install --no-cache-dir \
    "fastapi>=0.115,<1" \
    "uvicorn[standard]>=0.34,<1" \
    "httpx>=0.28,<1" \
    "pydantic>=2.10,<3" \
    "pydantic-settings>=2.7,<3" \
    "python-dotenv>=1.0,<2"

# ── Python runtime tweaks ───────────────────────────────────────────────────
# PYTHONUNBUFFERED=1 makes stdout/stderr flush immediately so Docker logs
# show output in real time instead of buffering.
# PYTHONDONTWRITEBYTECODE=1 avoids creating .pyc files inside the container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ── Application code ───────────────────────────────────────────────────────
# Copy only what the service actually needs at runtime.
COPY main.py .
COPY src/ src/

# ── Network & healthcheck ──────────────────────────────────────────────────
# Expose the service port (documentation only — docker-compose maps it).
EXPOSE 8100

# Healthcheck hits the lightweight /ping endpoint (no dependencies needed).
# Uses stdlib urllib so we don't have to install curl/wget.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8100/api/v1/ping', timeout=3).status == 200 else sys.exit(1)" \
    || exit 1

# ── Server binding ─────────────────────────────────────────────────────────
# Inside the container, bind to 0.0.0.0 so Docker can route traffic to it.
# On the host, docker-compose maps this to 127.0.0.1 only, so the service
# is never exposed to the public internet.
ENV APP_HOST=0.0.0.0 \
    APP_PORT=8100

CMD ["python", "main.py"]
