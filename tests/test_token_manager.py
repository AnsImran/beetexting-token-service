"""Tests for the TokenManager class.

All HTTP calls to BEEtexting are mocked using ``respx`` so tests never
touch the real API.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from pydantic import ValidationError

from beetexting_token_service.config import Settings
from beetexting_token_service.exceptions import TokenFetchError, TokenNotAvailableError
from beetexting_token_service.schemas import BeeTextingTokenResponse, CachedToken
from beetexting_token_service.token_manager import TokenManager

# ── Helpers ─────────────────────────────────────────────────────────────────

FAKE_TOKEN_RESPONSE = {
    "access_token": "fake-access-token-12345",
    "token_type": "Bearer",
    "expires_in": 3600,
}


def _mock_token_endpoint(settings: Settings, *, status: int = 200, json: dict | None = None):
    """Set up a respx mock for the BEEtexting token endpoint."""
    return respx.post(settings.beetexting_token_url).mock(
        return_value=httpx.Response(
            status_code=status,
            json=json if json is not None else FAKE_TOKEN_RESPONSE,
        )
    )


# ── Tests ───────────────────────────────────────────────────────────────────


class TestTokenManagerLifecycle:
    """Tests for start / stop and the basic happy path."""

    @respx.mock
    async def test_start_fetches_initial_token(self, fake_settings: Settings) -> None:
        """On start(), the manager should fetch and cache a token."""
        _mock_token_endpoint(fake_settings)

        manager = TokenManager(fake_settings)
        await manager.start()

        try:
            assert manager.has_valid_token is True
            token, expires_at = await manager.get_current_token()
            assert token == "fake-access-token-12345"
            assert expires_at > datetime.now(UTC)
        finally:
            await manager.stop()

    @respx.mock
    async def test_stop_cancels_background_task(self, fake_settings: Settings) -> None:
        """After stop(), the background refresh task should be cancelled."""
        _mock_token_endpoint(fake_settings)

        manager = TokenManager(fake_settings)
        await manager.start()
        assert manager._refresh_task is not None

        await manager.stop()
        assert manager._refresh_task.cancelled() or manager._refresh_task.done()


class TestGetCurrentToken:
    """Tests for the get_current_token() public method."""

    async def test_raises_when_no_token(self, fake_settings: Settings) -> None:
        """If start() was never called, get_current_token() should raise."""
        manager = TokenManager(fake_settings)
        with pytest.raises(TokenNotAvailableError):
            await manager.get_current_token()

    @respx.mock
    async def test_raises_when_token_expired(self, fake_settings: Settings) -> None:
        """If the cached token is past its expiry, report unavailable."""
        _mock_token_endpoint(fake_settings, json={
            "access_token": "expired-token",
            "token_type": "Bearer",
            "expires_in": 1,  # expires in 1 second
        })

        manager = TokenManager(fake_settings)
        await manager.start()

        try:
            # Wait long enough for the 1-second token to expire
            await asyncio.sleep(1.1)
            with pytest.raises(TokenNotAvailableError):
                await manager.get_current_token()
        finally:
            await manager.stop()


class TestTokenFetchRetries:
    """Tests for retry behaviour on fetch failures."""

    @respx.mock
    async def test_retries_on_failure(self, fake_settings: Settings) -> None:
        """A single failure followed by success should still produce a token."""
        # Allow 2 retries for this test
        fake_settings = fake_settings.model_copy(update={"token_retry_attempts": 2})

        route = respx.post(fake_settings.beetexting_token_url).mock(
            side_effect=[
                httpx.Response(status_code=500, json={"error": "server error"}),
                httpx.Response(status_code=200, json=FAKE_TOKEN_RESPONSE),
            ]
        )

        manager = TokenManager(fake_settings)
        await manager.start()

        try:
            assert manager.has_valid_token is True
            assert route.call_count == 2
        finally:
            await manager.stop()

    @respx.mock
    async def test_raises_after_all_retries_exhausted(self, fake_settings: Settings) -> None:
        """If every retry fails, TokenFetchError should be raised."""
        _mock_token_endpoint(fake_settings, status=500, json={"error": "down"})

        manager = TokenManager(fake_settings)
        with pytest.raises(TokenFetchError):
            await manager.start()

        # Clean up — stop won't fail even if start() didn't fully complete
        await manager.stop()


class TestSecondsUntilRefresh:
    """Tests for the refresh timing calculation."""

    @respx.mock
    async def test_refresh_scheduled_before_expiry(self, fake_settings: Settings) -> None:
        """The next refresh should be scheduled buffer-seconds before expiry."""
        _mock_token_endpoint(fake_settings)

        manager = TokenManager(fake_settings)
        await manager.start()

        try:
            seconds = manager._seconds_until_refresh()
            # Token expires in 3600s, buffer is 60s → should sleep ~3540s
            # Allow some tolerance for test execution time
            assert 3500 < seconds < 3545
        finally:
            await manager.stop()

    async def test_minimum_sleep_when_no_token(self, fake_settings: Settings) -> None:
        """With no token, the sleep should be the 10s minimum floor."""
        manager = TokenManager(fake_settings)
        assert manager._seconds_until_refresh() == 10.0


class TestTokenFetchValidation:
    """Tests for response validation in _fetch_token_from_beetexting."""

    @respx.mock
    async def test_rejects_missing_access_token_field(self, fake_settings: Settings) -> None:
        """A response missing 'access_token' should raise TokenFetchError."""
        _mock_token_endpoint(fake_settings, json={"token_type": "Bearer", "expires_in": 3600})

        manager = TokenManager(fake_settings)
        manager._http_client = httpx.AsyncClient()

        try:
            with pytest.raises(TokenFetchError, match="Unexpected response shape"):
                await manager._fetch_token_from_beetexting()
        finally:
            await manager._http_client.aclose()

    @respx.mock
    async def test_rejects_non_200_status(self, fake_settings: Settings) -> None:
        """A non-200 HTTP status should raise TokenFetchError."""
        _mock_token_endpoint(fake_settings, status=401, json={"error": "unauthorized"})

        manager = TokenManager(fake_settings)
        manager._http_client = httpx.AsyncClient()

        try:
            with pytest.raises(TokenFetchError, match="HTTP 401"):
                await manager._fetch_token_from_beetexting()
        finally:
            await manager._http_client.aclose()


class TestBeeTextingTokenResponseSchema:
    """Tests for Pydantic validation of the upstream API response model."""

    def test_valid_response(self) -> None:
        """A well-formed response should parse without error."""
        model = BeeTextingTokenResponse(
            access_token="abc123", token_type="Bearer", expires_in=3600
        )
        assert model.access_token == "abc123"
        assert model.token_type == "Bearer"
        assert model.expires_in == 3600

    def test_rejects_missing_access_token(self) -> None:
        """Missing access_token should fail validation."""
        with pytest.raises(ValidationError):
            BeeTextingTokenResponse(token_type="Bearer", expires_in=3600)  # type: ignore[call-arg]

    def test_rejects_missing_expires_in(self) -> None:
        """Missing expires_in should fail validation."""
        with pytest.raises(ValidationError):
            BeeTextingTokenResponse(access_token="abc", token_type="Bearer")  # type: ignore[call-arg]

    def test_rejects_non_positive_expires_in(self) -> None:
        """expires_in must be > 0."""
        with pytest.raises(ValidationError):
            BeeTextingTokenResponse(access_token="abc", expires_in=0)

    def test_rejects_negative_expires_in(self) -> None:
        """Negative expires_in should fail validation."""
        with pytest.raises(ValidationError):
            BeeTextingTokenResponse(access_token="abc", expires_in=-100)

    def test_rejects_empty_access_token(self) -> None:
        """An empty string access_token should fail min_length=1 validation."""
        with pytest.raises(ValidationError):
            BeeTextingTokenResponse(access_token="", expires_in=3600)

    def test_frozen_prevents_mutation(self) -> None:
        """Model should be immutable — assignment raises an error."""
        model = BeeTextingTokenResponse(access_token="abc", expires_in=3600)
        with pytest.raises(ValidationError):
            model.access_token = "changed"  # type: ignore[misc]

    def test_repr_hides_access_token(self) -> None:
        """access_token should not appear in repr() to prevent log leaks."""
        model = BeeTextingTokenResponse(access_token="SECRET_TOKEN_VALUE", expires_in=3600)
        representation = repr(model)
        assert "SECRET_TOKEN_VALUE" not in representation

    def test_alias_population(self) -> None:
        """Should accept field values via alias names (matching the API JSON keys)."""
        # Simulates parsing a raw dict from response.json()
        data = {"access_token": "tok123", "token_type": "Bearer", "expires_in": 7200}
        model = BeeTextingTokenResponse(**data)
        assert model.access_token == "tok123"
        assert model.expires_in == 7200


class TestCachedTokenSchema:
    """Tests for Pydantic validation of the in-memory CachedToken model."""

    def test_valid_cached_token(self) -> None:
        """A well-formed CachedToken should parse without error."""
        now = datetime.now(UTC)
        model = CachedToken(
            access_token="abc123",
            expires_at_utc=now + timedelta(hours=1),
            fetched_at_utc=now,
        )
        assert model.access_token == "abc123"
        assert model.token_type == "Bearer"  # default
        assert model.fetched_at_utc == now

    def test_rejects_missing_expires_at(self) -> None:
        """Missing expires_at_utc should fail validation."""
        with pytest.raises(ValidationError):
            CachedToken(
                access_token="abc",
                fetched_at_utc=datetime.now(UTC),
            )  # type: ignore[call-arg]

    def test_rejects_empty_access_token(self) -> None:
        """An empty string access_token should fail min_length=1 validation."""
        now = datetime.now(UTC)
        with pytest.raises(ValidationError):
            CachedToken(
                access_token="",
                expires_at_utc=now + timedelta(hours=1),
                fetched_at_utc=now,
            )

    def test_frozen_prevents_mutation(self) -> None:
        """Model should be immutable — assignment raises an error."""
        now = datetime.now(UTC)
        model = CachedToken(
            access_token="abc",
            expires_at_utc=now + timedelta(hours=1),
            fetched_at_utc=now,
        )
        with pytest.raises(ValidationError):
            model.access_token = "changed"  # type: ignore[misc]

    def test_repr_hides_access_token(self) -> None:
        """access_token should not appear in repr() to prevent log leaks."""
        now = datetime.now(UTC)
        model = CachedToken(
            access_token="SUPER_SECRET_TOKEN",
            expires_at_utc=now + timedelta(hours=1),
            fetched_at_utc=now,
        )
        representation = repr(model)
        assert "SUPER_SECRET_TOKEN" not in representation

    def test_is_expired_false_for_future_token(self) -> None:
        """A token expiring in the future should not be expired."""
        now = datetime.now(UTC)
        model = CachedToken(
            access_token="abc",
            expires_at_utc=now + timedelta(hours=1),
            fetched_at_utc=now,
        )
        assert model.is_expired is False

    def test_is_expired_true_for_past_token(self) -> None:
        """A token with an expiry in the past should be expired."""
        now = datetime.now(UTC)
        model = CachedToken(
            access_token="abc",
            expires_at_utc=now - timedelta(seconds=1),
            fetched_at_utc=now - timedelta(hours=1),
        )
        assert model.is_expired is True
