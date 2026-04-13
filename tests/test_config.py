"""Tests for the configuration module."""

import pytest

from src.core.config import Settings


class TestSettings:
    """Validate that Settings parses and validates environment values correctly."""

    def test_valid_settings(self, fake_settings: Settings) -> None:
        """All fields are populated with the fixture's dummy values."""
        assert fake_settings.beetexting_client_id == "test-client-id"
        assert fake_settings.beetexting_client_secret == "test-client-secret"
        assert fake_settings.beetexting_api_key == "test-api-key"
        assert fake_settings.token_refresh_buffer_seconds == 60
        assert fake_settings.log_level == "DEBUG"

    def test_log_level_normalised_to_upper(self) -> None:
        """log_level should be uppercased regardless of input."""
        s = Settings(
            beetexting_client_id="id",
            beetexting_client_secret="secret",
            beetexting_api_key="key",
            log_level="debug",
        )
        assert s.log_level == "DEBUG"

    def test_invalid_log_level_rejected(self) -> None:
        """An unrecognised log level must raise a validation error."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Settings(
                beetexting_client_id="id",
                beetexting_client_secret="secret",
                beetexting_api_key="key",
                log_level="VERBOSE",
            )

    def test_missing_required_field_rejected(self) -> None:
        """Omitting a required field must raise a validation error."""
        with pytest.raises(Exception):
            Settings(
                _env_file=None,  # block .env so the missing field isn't filled
                beetexting_client_id="id",
                # beetexting_client_secret missing
                beetexting_api_key="key",
            )  # type: ignore[call-arg]

    def test_defaults_are_sensible(self, fake_settings: Settings) -> None:
        """Default endpoint URLs and scopes should be populated."""
        assert "auth.beetexting.com" in fake_settings.beetexting_token_url
        assert "SendMessage" in fake_settings.beetexting_scopes

    def test_refresh_buffer_minimum(self) -> None:
        """token_refresh_buffer_seconds must be at least 30."""
        with pytest.raises(Exception):
            Settings(
                beetexting_client_id="id",
                beetexting_client_secret="secret",
                beetexting_api_key="key",
                token_refresh_buffer_seconds=10,
            )

    # ── ACCESS_LOG_LEVEL ────────────────────────────────────────────────
    # These three tests close a small gap: access_log_level is a second
    # field on the SAME validator as log_level.  If someone accidentally
    # drops it from the validator's field list, the log_level tests would
    # still pass but access_log_level would silently accept garbage.

    def test_access_log_level_default_is_info(self, fake_settings: Settings) -> None:
        """ACCESS_LOG_LEVEL should default to INFO so dev logs show every request."""
        assert fake_settings.access_log_level == "INFO"

    def test_access_log_level_normalised_to_upper(self) -> None:
        """access_log_level should be uppercased like log_level."""
        s = Settings(
            _env_file=None,  # block .env so we test only explicit kwargs
            beetexting_client_id="id",
            beetexting_client_secret="secret",
            beetexting_api_key="key",
            access_log_level="warning",
        )
        assert s.access_log_level == "WARNING"

    def test_invalid_access_log_level_rejected(self) -> None:
        """An unrecognised access_log_level must raise a validation error."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            Settings(
                _env_file=None,
                beetexting_client_id="id",
                beetexting_client_secret="secret",
                beetexting_api_key="key",
                access_log_level="VERBOSE",
            )
