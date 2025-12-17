"""Fixtures specific to unit tests."""

import pytest
from unittest.mock import AsyncMock

from fuzzbin.common.config import HTTPConfig, RetryConfig


@pytest.fixture
def retry_config() -> RetryConfig:
    """Provide a retry configuration for unit tests."""
    return RetryConfig(
        max_attempts=3,
        backoff_multiplier=1.0,
        min_wait=0.1,  # Shorter wait for tests
        max_wait=1.0,  # Shorter wait for tests
        status_codes=[429, 500, 502, 503, 504],
    )


@pytest.fixture
def http_config_with_retry(retry_config: RetryConfig) -> HTTPConfig:
    """Provide HTTP config with custom retry settings for tests."""
    return HTTPConfig(
        timeout=5,
        retry=retry_config,
    )
