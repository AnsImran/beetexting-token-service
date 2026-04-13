"""
Token-related Pydantic v2 schemas.

These models cover everything in the token domain:
- ``BeeTextingTokenResponse``: validates upstream JSON from BEEtexting's OAuth2 endpoint.
- ``CachedToken``: the immutable, in-memory token state held by TokenManager.
- ``TokenResponse``: the outbound API response returned by ``GET /api/v1/token``.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

# ── BEEtexting API response ─────────────────────────────────────────────────


class BeeTextingTokenResponse(BaseModel):
    """Validates the raw JSON returned by BEEtexting's OAuth2 token endpoint.

    Used internally to parse and validate the upstream response before we
    store the token.  This replaces manual dict-key checks and gives us
    clear error messages when the API response shape changes unexpectedly.

    The model is frozen (immutable) because it is a value object — once
    parsed, it should never be modified.
    """

    model_config = ConfigDict(
        frozen=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        },
    )

    access_token: str = Field(
        ...,
        alias="access_token",
        min_length=1,
        repr=False,
        description="The Bearer token string issued by BEEtexting.",
        examples=["eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    token_type: str = Field(
        default="Bearer",
        alias="token_type",
        description="Token type — expected to always be 'Bearer'.",
        examples=["Bearer"],
    )
    expires_in: int = Field(
        ...,
        alias="expires_in",
        gt=0,
        description="Number of seconds until the token expires (must be positive).",
        examples=[3600],
    )


# ── Cached token state ─────────────────────────────────────────────────────


class CachedToken(BaseModel):
    """Represents a single BEEtexting token stored in memory by TokenManager.

    This model holds everything needed to serve a token to callers and to
    decide when it needs refreshing.  A new instance is created on every
    successful refresh, atomically replacing the previous one.

    The model is frozen (immutable) — once created, the token state cannot
    be accidentally mutated.  To update the token, create a new CachedToken
    and swap it in under the asyncio lock.
    """

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_at_utc": "2026-04-11T13:00:00+00:00",
                "fetched_at_utc": "2026-04-11T12:00:00+00:00",
            }
        },
    )

    access_token: str = Field(
        ...,
        min_length=1,
        repr=False,
        description="The Bearer token string issued by BEEtexting.",
        examples=["eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    token_type: str = Field(
        default="Bearer",
        description="Token type — always 'Bearer'.",
        examples=["Bearer"],
    )
    expires_at_utc: datetime = Field(
        ...,
        description=(
            "UTC-aware timestamp when this token expires.  "
            "Calculated as fetch_time + expires_in from the API response."
        ),
        examples=["2026-04-11T13:00:00+00:00"],
    )
    fetched_at_utc: datetime = Field(
        ...,
        description="UTC-aware timestamp when this token was obtained from BEEtexting.",
        examples=["2026-04-11T12:00:00+00:00"],
    )

    @property
    def is_expired(self) -> bool:
        """Check whether this token has passed its expiry time.

        Returns True if the current UTC time is at or past expires_at_utc.
        This centralises the expiry logic on the model itself rather than
        scattering it across the codebase.
        """
        return datetime.now(UTC) >= self.expires_at_utc


# ── Outbound API response ──────────────────────────────────────────────────


class TokenResponse(BaseModel):
    """Response returned by the ``GET /api/v1/token`` endpoint.

    Sibling microservices call this to get a valid Bearer token they can use
    for BEEtexting API requests.
    """

    ok: bool = Field(
        default=True,
        description="Indicates the request succeeded.",
    )
    access_token: str = Field(
        ...,
        description="Bearer token for BEEtexting API calls.",
    )
    token_type: str = Field(
        default="Bearer",
        description="Token type — always 'Bearer'.",
    )
    expires_at_utc: datetime = Field(
        ...,
        description="UTC timestamp when this token expires.",
        examples=["2026-04-11T13:00:00+00:00"],
    )
    api_key: str = Field(
        ...,
        description="The x-api-key header value required alongside the Bearer token.",
    )
