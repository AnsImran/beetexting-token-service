"""
API v1 route definitions.

All endpoints live under ``/api/v1/``.  The router is mounted by the
application factory in ``app.py``.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from src.core.config import Settings, get_settings
from src.schemas.errors import ErrorResponse
from src.schemas.health import HealthResponse
from src.schemas.token import TokenResponse
from src.services.token_manager import TokenManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])

# ── Dependency: TokenManager instance ───────────────────────────────────────
# The actual instance is injected at startup via ``app.dependency_overrides``
# (see app.py).  This placeholder just declares the type so FastAPI can
# wire things up.

_token_manager: TokenManager | None = None


def _get_token_manager() -> TokenManager:
    """FastAPI dependency that returns the shared TokenManager instance."""
    assert _token_manager is not None, "TokenManager not initialised"
    return _token_manager


def set_token_manager(manager: TokenManager) -> None:
    """Called once at startup to inject the real TokenManager."""
    global _token_manager  # noqa: PLW0603
    _token_manager = manager


# Type alias for cleaner signatures
TokenManagerDep = Annotated[TokenManager, Depends(_get_token_manager)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get(
    "/token",
    response_model=TokenResponse,
    responses={
        503: {"model": ErrorResponse, "description": "No valid token available."},
        502: {"model": ErrorResponse, "description": "Token fetch failed."},
    },
    summary="Get a valid BEEtexting Bearer token",
    description=(
        "Returns the currently cached Bearer token and its expiry time. "
        "Sibling microservices call this endpoint to obtain a token they can "
        "use in their own BEEtexting API requests."
    ),
)
async def get_token(manager: TokenManagerDep, settings: SettingsDep) -> TokenResponse:
    """Return the current BEEtexting access token to an internal caller."""
    access_token, expires_at = await manager.get_current_token()
    logger.debug("Serving token to internal caller (expires %s).", expires_at.isoformat())
    return TokenResponse(
        access_token=access_token,
        expires_at_utc=expires_at,
        api_key=settings.beetexting_api_key,
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health check",
    description="Returns the service status and whether a valid token is available.",
)
async def health_check(manager: TokenManagerDep) -> HealthResponse:
    """Lightweight health probe for load balancers and monitoring."""
    has_token = manager.has_valid_token
    return HealthResponse(
        status="healthy" if has_token else "degraded",
        has_valid_token=has_token,
        token_expires_at_utc=manager.expires_at,
    )


@router.get(
    "/ping",
    summary="Liveness probe",
    description="Returns a simple pong — confirms the process is alive.",
)
async def ping() -> dict[str, str]:
    """Bare-minimum liveness check (no dependencies)."""
    return {"ping": "pong", "timestamp_utc": datetime.now(UTC).isoformat()}
