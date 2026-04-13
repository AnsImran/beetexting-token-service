"""
Error response schemas.

Defines the standard error envelope returned by every failed request.
All FastAPI error handlers in ``src/core/exceptions.py`` return JSON
matching this shape so consuming services can parse errors reliably.
"""

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Inner error object with code and message."""

    code: int = Field(..., description="HTTP status code.", examples=[502])
    message: str = Field(
        ...,
        description="Human-readable error description.",
        examples=["Failed to fetch token from BEEtexting."],
    )


class ErrorResponse(BaseModel):
    """Standard error envelope returned on any failure."""

    ok: bool = Field(default=False)
    error: ErrorDetail
