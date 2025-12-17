"""Shared pytest fixtures for all tests."""

import pytest
import pytest_asyncio
import httpx
import respx

from fuzzbin.common.config import Config, HTTPConfig, LoggingConfig


@pytest.fixture
def sample_config() -> Config:
    """Provide a sample configuration for tests."""
    return Config(
        http=HTTPConfig(
            timeout=30,
            max_redirects=5,
            verify_ssl=True,
        ),
        logging=LoggingConfig(
            level="DEBUG",
            format="text",
            handlers=["console"],
        ),
    )


@pytest.fixture
def http_config() -> HTTPConfig:
    """Provide a sample HTTP configuration for tests."""
    return HTTPConfig(
        timeout=10,
        max_redirects=3,
        verify_ssl=True,
    )


@pytest_asyncio.fixture
async def async_httpx_client() -> httpx.AsyncClient:
    """Provide an async httpx client for tests."""
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def mock_http():
    """Provide a respx mock for httpx requests."""
    with respx.mock:
        yield respx
