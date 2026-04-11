"""
Custom exceptions and FastAPI error handlers.

Every exception that the service can raise is defined here so that error
handling is consistent and centralised.  The ``register_error_handlers``
function wires these into the FastAPI app at startup.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Custom exception hierarchy ──────────────────────────────────────────────


class TokenServiceError(Exception):
    """Base exception for all token-service errors.

    Every custom exception in this service inherits from this class so
    callers can ``except TokenServiceError`` to catch anything we raise.
    """

    def __init__(self, message: str = "An internal error occurred.", status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class TokenFetchError(TokenServiceError):
    """Raised when we fail to obtain a token from BEEtexting.

    This covers network errors, bad credentials, and unexpected response
    shapes from the BEEtexting OAuth2 endpoint.
    """

    def __init__(self, message: str = "Failed to fetch token from BEEtexting."):
        super().__init__(message=message, status_code=502)


class TokenNotAvailableError(TokenServiceError):
    """Raised when a caller asks for a token but none has been acquired yet.

    This typically happens if the service just started and the first
    background refresh hasn't completed, or if every refresh attempt has
    failed.
    """

    def __init__(self, message: str = "No valid token is currently available."):
        super().__init__(message=message, status_code=503)


# ── FastAPI error handlers ──────────────────────────────────────────────────


def _build_error_body(status_code: int, message: str) -> dict[str, Any]:
    """Build a consistent JSON error envelope."""
    return {
        "ok": False,
        "error": {
            "code": status_code,
            "message": message,
        },
    }


def register_error_handlers(app: FastAPI) -> None:
    """Attach error handlers to the FastAPI application.

    This ensures that **all** responses — even unexpected crashes — return
    a uniform JSON shape so consuming services can parse errors reliably.
    """

    @app.exception_handler(TokenServiceError)
    async def _handle_token_service_error(
        _request: Request, exc: TokenServiceError
    ) -> JSONResponse:
        """Handle any of our custom exceptions."""
        logger.error("TokenServiceError: %s (status=%d)", exc.message, exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_body(exc.status_code, exc.message),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for anything we didn't anticipate.

        Logs the full traceback for debugging but returns a generic message
        to the caller — internal details should never leak.
        """
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_build_error_body(500, "An unexpected internal error occurred."),
        )
