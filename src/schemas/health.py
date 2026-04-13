"""
Health check schemas.

Models returned by the ``/api/v1/health`` endpoint.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response returned by the ``/health`` endpoint."""

    status: str = Field(
        ...,
        description="Overall service health: 'healthy' or 'degraded'.",
        examples=["healthy"],
    )
    has_valid_token: bool = Field(
        ...,
        description="Whether the service currently holds a usable BEEtexting token.",
    )
    token_expires_at_utc: datetime | None = Field(
        default=None,
        description="UTC expiry time of the current token, or null if no token exists.",
        examples=["2026-04-11T13:00:00+00:00"],
    )
