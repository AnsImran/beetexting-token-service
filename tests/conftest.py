"""
Shared test fixtures.

All tests use a fake ``Settings`` instance and a mock-friendly test client
so nothing ever touches the real BEEtexting API.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.config import Settings


@pytest.fixture()
def fake_settings() -> Settings:
    """Return a Settings object with dummy credentials for testing."""
    return Settings(
        beetexting_client_id="test-client-id",
        beetexting_client_secret="test-client-secret",
        beetexting_api_key="test-api-key",
        token_refresh_buffer_seconds=60,
        token_retry_attempts=1,
        token_retry_delay_seconds=0.5,
        http_timeout_seconds=5.0,
        log_level="DEBUG",
    )


@pytest.fixture()
async def test_client(fake_settings: Settings):
    """Yield an httpx AsyncClient wired to the FastAPI app.

    The app's lifespan is **not** used here — tests that need the
    TokenManager create and inject it manually to control the mock layer.
    """
    # Import late so module-level code doesn't run before fixtures
    # Override the settings singleton so the app picks up fake values
    import src.core.config as config_module
    from src.app import create_app
    original = config_module._settings
    config_module._settings = fake_settings

    app = create_app()

    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    # Restore
    config_module._settings = original
