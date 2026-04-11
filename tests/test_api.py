"""Tests for the FastAPI API endpoints.

Uses httpx AsyncClient with the app mounted via ASGITransport.
BEEtexting is mocked so no real HTTP calls are made.
"""

from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

import beetexting_token_service.config as config_module
from beetexting_token_service.api.v1.router import set_token_manager
from beetexting_token_service.app import create_app
from beetexting_token_service.config import Settings
from beetexting_token_service.exceptions import TokenNotAvailableError

# ── Helpers ─────────────────────────────────────────────────────────────────


class FakeTokenManager:
    """A minimal stand-in for TokenManager that returns canned data."""

    def __init__(self, *, has_token: bool = True):
        self._has_token = has_token
        self._token = "fake-bearer-token"
        self._expires_at = datetime.now(UTC) + timedelta(hours=1)

    async def get_current_token(self) -> tuple[str, datetime]:
        if not self._has_token:
            raise TokenNotAvailableError()
        return self._token, self._expires_at

    @property
    def has_valid_token(self) -> bool:
        return self._has_token

    @property
    def expires_at(self) -> datetime | None:
        return self._expires_at if self._has_token else None


async def _make_client(fake_settings: Settings, *, has_token: bool = True) -> AsyncClient:
    """Build a test client with a FakeTokenManager injected."""
    original = config_module._settings
    config_module._settings = fake_settings

    app = create_app()

    # Bypass the lifespan (which would try to hit real BEEtexting)
    # by injecting our fake manager directly
    fake_manager = FakeTokenManager(has_token=has_token)
    set_token_manager(fake_manager)

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    client = AsyncClient(transport=transport, base_url="http://testserver")

    # Store reference for cleanup
    client._original_settings = original  # type: ignore[attr-defined]
    return client


# ── Tests ───────────────────────────────────────────────────────────────────


class TestGetToken:
    """Tests for GET /api/v1/token."""

    async def test_returns_token_when_available(self, fake_settings: Settings) -> None:
        """Happy path: should return token, api_key, and expiry."""
        client = await _make_client(fake_settings)
        try:
            response = await client.get("/api/v1/token")
            assert response.status_code == 200

            data = response.json()
            assert data["ok"] is True
            assert data["access_token"] == "fake-bearer-token"
            assert data["token_type"] == "Bearer"
            assert data["api_key"] == "test-api-key"
            assert "expires_at_utc" in data
        finally:
            config_module._settings = client._original_settings  # type: ignore[attr-defined]
            await client.aclose()

    async def test_returns_503_when_no_token(self, fake_settings: Settings) -> None:
        """When no token is available, should return 503 with error body."""
        client = await _make_client(fake_settings, has_token=False)
        try:
            response = await client.get("/api/v1/token")
            assert response.status_code == 503

            data = response.json()
            assert data["ok"] is False
            assert data["error"]["code"] == 503
        finally:
            config_module._settings = client._original_settings  # type: ignore[attr-defined]
            await client.aclose()


class TestHealthCheck:
    """Tests for GET /api/v1/health."""

    async def test_healthy_when_token_exists(self, fake_settings: Settings) -> None:
        """Should report 'healthy' when a valid token is cached."""
        client = await _make_client(fake_settings)
        try:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "healthy"
            assert data["has_valid_token"] is True
            assert data["token_expires_at_utc"] is not None
        finally:
            config_module._settings = client._original_settings  # type: ignore[attr-defined]
            await client.aclose()

    async def test_degraded_when_no_token(self, fake_settings: Settings) -> None:
        """Should report 'degraded' when no token is available."""
        client = await _make_client(fake_settings, has_token=False)
        try:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "degraded"
            assert data["has_valid_token"] is False
        finally:
            config_module._settings = client._original_settings  # type: ignore[attr-defined]
            await client.aclose()


class TestPing:
    """Tests for GET /api/v1/ping."""

    async def test_returns_pong(self, fake_settings: Settings) -> None:
        """Liveness probe should always return pong."""
        client = await _make_client(fake_settings)
        try:
            response = await client.get("/api/v1/ping")
            assert response.status_code == 200

            data = response.json()
            assert data["ping"] == "pong"
            assert "timestamp_utc" in data
        finally:
            config_module._settings = client._original_settings  # type: ignore[attr-defined]
            await client.aclose()
