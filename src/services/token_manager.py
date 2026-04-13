"""
Core token management — fetch, cache, and proactively refresh BEEtexting tokens.

The ``TokenManager`` class runs a background asyncio task that:
1. Fetches a fresh OAuth2 token on startup.
2. Sleeps until ``token_refresh_buffer_seconds`` before expiry.
3. Fetches a new token, replacing the old one in memory.
4. Repeats forever.

Other modules never talk to BEEtexting directly — they call
``token_manager.get_current_token()`` which returns instantly from cache.
"""

import asyncio
import base64
import logging
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import ValidationError

from src.core.config import Settings
from src.core.exceptions import TokenFetchError, TokenNotAvailableError
from src.schemas.token import BeeTextingTokenResponse, CachedToken

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages the lifecycle of a single BEEtexting OAuth2 access token.

    This class is designed to be instantiated once at application startup
    and shared across all request handlers via FastAPI's dependency system.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        # Current token state (protected by an asyncio lock for safe swaps).
        # A single CachedToken model replaces loose attributes — one object,
        # one atomic swap, one None-check.
        self._lock = asyncio.Lock()
        self._cached_token: CachedToken | None = None

        # Background refresh task handle
        self._refresh_task: asyncio.Task[None] | None = None

        # Shared HTTP client — created once, reused for every request
        self._http_client: httpx.AsyncClient | None = None

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialise the HTTP client and kick off the background refresh loop.

        Called once during FastAPI's ``lifespan`` startup.
        """
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._settings.http_timeout_seconds),
        )
        logger.info("TokenManager starting — fetching initial token …")
        # Fetch the very first token synchronously (block startup until we have one)
        await self._refresh_token()
        # Then hand off to the background loop
        self._refresh_task = asyncio.create_task(
            self._refresh_loop(), name="token-refresh-loop"
        )
        logger.info("Background token refresh loop started.")

    async def stop(self) -> None:
        """Cancel the background task and close the HTTP client.

        Called during FastAPI's ``lifespan`` shutdown.
        """
        if self._refresh_task is not None:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            logger.info("Background token refresh loop stopped.")
        if self._http_client is not None:
            await self._http_client.aclose()
            logger.info("HTTP client closed.")

    # ── Public API ──────────────────────────────────────────────────────

    async def get_current_token(self) -> tuple[str, datetime]:
        """Return the cached (access_token, expires_at_utc) pair.

        Raises:
            TokenNotAvailableError: If no valid token exists in memory.
        """
        async with self._lock:
            if self._cached_token is None:
                raise TokenNotAvailableError()

            # If the token has already expired (clock skew, missed refresh),
            # report it as unavailable rather than handing out a dead token.
            if self._cached_token.is_expired:
                logger.warning("Cached token has expired — reporting unavailable.")
                raise TokenNotAvailableError("Cached token has expired. Refresh is in progress.")

            return self._cached_token.access_token, self._cached_token.expires_at_utc

    @property
    def has_valid_token(self) -> bool:
        """Quick check (non-async) for health endpoint."""
        if self._cached_token is None:
            return False
        return not self._cached_token.is_expired

    @property
    def expires_at(self) -> datetime | None:
        """Return the current token's expiry time, or None."""
        if self._cached_token is None:
            return None
        return self._cached_token.expires_at_utc

    # ── Background refresh loop ─────────────────────────────────────────

    async def _refresh_loop(self) -> None:
        """Sleep until the token is about to expire, then refresh it.

        Runs forever as a background task.  On failure it retries with
        exponential back-off (configured via settings).
        """
        while True:
            try:
                # Work out how long to sleep before the next refresh
                sleep_seconds = self._seconds_until_refresh()
                logger.info(
                    "Next token refresh in %.0f seconds (at %s UTC).",
                    sleep_seconds,
                    (datetime.now(UTC) + timedelta(seconds=sleep_seconds)).isoformat(),
                )
                await asyncio.sleep(sleep_seconds)

                # Time to refresh
                await self._refresh_token()

            except asyncio.CancelledError:
                # Service is shutting down — exit cleanly
                raise
            except Exception:
                # Something went wrong — log it and retry after a short delay
                # so the loop doesn't die permanently.
                logger.exception("Token refresh loop encountered an error — retrying in 30 s.")
                await asyncio.sleep(30)

    def _seconds_until_refresh(self) -> float:
        """Calculate how many seconds to wait before the next refresh.

        Returns at least 10 seconds to avoid a busy-loop if something is off.
        """
        if self._cached_token is None:
            return 10.0  # no token yet — refresh immediately-ish

        buffer = timedelta(seconds=self._settings.token_refresh_buffer_seconds)
        refresh_at = self._cached_token.expires_at_utc - buffer
        delta = (refresh_at - datetime.now(UTC)).total_seconds()

        # Never go below 10 s to protect against busy-looping
        return max(delta, 10.0)

    # ── Token fetch with retries ────────────────────────────────────────

    async def _refresh_token(self) -> None:
        """Fetch a new token from BEEtexting and store it in memory.

        Retries up to ``token_retry_attempts`` times with exponential
        back-off on failure.
        """
        settings = self._settings
        last_error: Exception | None = None

        for attempt in range(1, settings.token_retry_attempts + 1):
            try:
                api_response = await self._fetch_token_from_beetexting()

                # Build a CachedToken — one object, one atomic swap
                now = datetime.now(UTC)
                token = CachedToken(
                    access_token=api_response.access_token,
                    token_type=api_response.token_type,
                    expires_at_utc=now + timedelta(seconds=api_response.expires_in),
                    fetched_at_utc=now,
                )

                async with self._lock:
                    self._cached_token = token

                logger.info(
                    "Token refreshed successfully. Expires at %s UTC (in %d s).",
                    token.expires_at_utc.isoformat(),
                    api_response.expires_in,
                )
                return  # success — exit the retry loop

            except Exception as exc:
                last_error = exc
                delay = settings.token_retry_delay_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Token fetch attempt %d/%d failed: %s — retrying in %.1f s.",
                    attempt,
                    settings.token_retry_attempts,
                    exc,
                    delay,
                )
                if attempt < settings.token_retry_attempts:
                    await asyncio.sleep(delay)

        # All retries exhausted
        raise TokenFetchError(
            f"Failed to fetch token after {settings.token_retry_attempts} attempts: {last_error}"
        )

    async def _fetch_token_from_beetexting(self) -> BeeTextingTokenResponse:
        """Make the actual HTTP POST to the BEEtexting token endpoint.

        Returns:
            A validated ``BeeTextingTokenResponse`` model parsed from the
            upstream JSON.

        Raises:
            TokenFetchError: On HTTP errors, invalid JSON, or unexpected
                response shapes (Pydantic validation failure).
        """
        if self._http_client is None:
            raise TokenFetchError("HTTP client is not initialised — was start() called?")

        settings = self._settings

        # Build Basic auth header: base64("client_id:client_secret")
        credentials = f"{settings.beetexting_client_id}:{settings.beetexting_client_secret}"
        basic_token = base64.b64encode(credentials.encode()).decode()

        try:
            response = await self._http_client.post(
                settings.beetexting_token_url,
                headers={
                    "Authorization": f"Basic {basic_token}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "client_credentials",
                    "scope": settings.beetexting_scopes,
                },
            )
        except httpx.HTTPError as exc:
            raise TokenFetchError(f"Network error contacting BEEtexting: {exc}") from exc

        # Validate the HTTP status
        if response.status_code != 200:
            body = response.text[:500]  # truncate to avoid logging huge payloads
            raise TokenFetchError(
                f"BEEtexting returned HTTP {response.status_code}: {body}"
            )

        # Parse JSON and validate through the Pydantic model — this replaces
        # manual dict-key checks with proper type validation.
        try:
            data = response.json()
        except Exception as exc:
            raise TokenFetchError(f"Invalid JSON from BEEtexting: {exc}") from exc

        try:
            return BeeTextingTokenResponse(**data)
        except ValidationError as exc:
            raise TokenFetchError(
                f"Unexpected response shape from BEEtexting: {exc}"
            ) from exc
