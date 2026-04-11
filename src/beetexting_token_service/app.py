"""
FastAPI application factory.

Creates and configures the FastAPI app with:
- Lifespan management (startup / shutdown for TokenManager).
- API versioning (v1 router mounted at ``/api/v1``).
- Centralised error handlers.
- OpenAPI metadata.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from beetexting_token_service.api.v1.router import router as v1_router
from beetexting_token_service.api.v1.router import set_token_manager
from beetexting_token_service.config import get_settings
from beetexting_token_service.exceptions import register_error_handlers
from beetexting_token_service.logging_config import setup_logging
from beetexting_token_service.token_manager import TokenManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown of long-lived resources.

    On startup:
        1. Configure logging.
        2. Create and start the TokenManager (fetches first token).
        3. Inject the manager into the v1 router.

    On shutdown:
        1. Stop the TokenManager (cancel background task, close HTTP client).
    """
    settings = get_settings()
    setup_logging(level=settings.log_level)

    logger.info("=== BEEtexting Token Service starting ===")
    logger.info(
        "Config: refresh_buffer=%ds, retries=%d, retry_delay=%.1fs, http_timeout=%.1fs",
        settings.token_refresh_buffer_seconds,
        settings.token_retry_attempts,
        settings.token_retry_delay_seconds,
        settings.http_timeout_seconds,
    )

    # Create and start the token manager
    manager = TokenManager(settings)
    await manager.start()
    set_token_manager(manager)

    yield  # ← application is running and serving requests

    # Shutdown
    logger.info("=== BEEtexting Token Service shutting down ===")
    await manager.stop()


def create_app() -> FastAPI:
    """Build and return the fully-configured FastAPI application."""
    app = FastAPI(
        title="BEEtexting Token Service",
        summary="Internal OAuth2 token manager for BEEtexting.",
        description=(
            "This microservice keeps a valid BEEtexting OAuth2 Bearer token in memory "
            "and exposes it via a simple REST endpoint.  Sibling services call "
            "``GET /api/v1/token`` instead of managing credentials themselves."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Wire up error handlers and routes
    register_error_handlers(app)
    app.include_router(v1_router)

    return app
