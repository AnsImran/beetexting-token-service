"""
Application configuration loaded from environment variables.

Every tuneable parameter lives here — nothing is hard-coded in the service logic.
Uses Pydantic Settings so values are validated at startup and fail fast on
missing / malformed configuration.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration for the BEEtexting Token Service.

    Values are read from environment variables (or a `.env` file in the
    project root).  Names are **case-insensitive** — `beetexting_client_id`
    and `BEETEXTING_CLIENT_ID` are both accepted.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # silently ignore unrelated env vars
    )

    # ── BEEtexting OAuth2 credentials ───────────────────────────────────────
    beetexting_client_id: str = Field(
        ...,
        description="OAuth2 client ID for the BEEtexting M2M application.",
    )
    beetexting_client_secret: str = Field(
        ...,
        description="OAuth2 client secret for the BEEtexting M2M application.",
    )
    beetexting_api_key: str = Field(
        ...,
        description="API key sent as the x-api-key header on every BEEtexting request.",
    )

    # ── BEEtexting OAuth2 endpoints ─────────────────────────────────────────
    beetexting_token_url: str = Field(
        default="https://auth.beetexting.com/oauth2/token/",
        description="BEEtexting OAuth2 token endpoint.",
    )
    beetexting_scopes: str = Field(
        default=(
            "https://com.beetexting.scopes/ReadContact "
            "https://com.beetexting.scopes/WriteContact "
            "https://com.beetexting.scopes/SendMessage"
        ),
        description="Space-separated OAuth2 scopes to request.",
    )

    # ── Token refresh behaviour ─────────────────────────────────────────────
    token_refresh_buffer_seconds: int = Field(
        default=300,
        ge=30,
        description=(
            "How many seconds before token expiry to trigger a proactive refresh. "
            "Default is 300 (5 minutes)."
        ),
    )
    token_retry_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of retry attempts when a token request fails.",
    )
    token_retry_delay_seconds: float = Field(
        default=2.0,
        ge=0.5,
        le=30.0,
        description="Base delay in seconds between retry attempts (doubles each retry).",
    )

    # ── HTTP client settings ────────────────────────────────────────────────
    http_timeout_seconds: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Timeout in seconds for HTTP requests to BEEtexting.",
    )

    # ── FastAPI server settings ─────────────────────────────────────────────
    app_host: str = Field(
        default="127.0.0.1",
        description="Host to bind the FastAPI server to. Default is localhost only.",
    )
    app_port: int = Field(
        default=8100,
        ge=1024,
        le=65535,
        description="Port for the FastAPI server.",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        """Ensure the log level is always upper-case and valid."""
        normalised = value.upper()
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalised not in valid:
            raise ValueError(f"log_level must be one of {valid}, got '{value}'")
        return normalised


# ── Module-level singleton ──────────────────────────────────────────────────
# Imported once at startup; every module reads from the same instance.

_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached Settings singleton, creating it on first call."""
    global _settings  # noqa: PLW0603
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
