"""Tests for the RateLimitedAPIClient class."""

import asyncio
import time
from typing import Optional

import httpx
import pytest
import respx

from fuzzbin.api.base_client import RateLimitedAPIClient
from fuzzbin.common.config import (
    APIClientConfig,
    ConcurrencyConfig,
    HTTPConfig,
    RateLimitConfig,
    RetryConfig,
)


@pytest.fixture
def http_config():
    """Create HTTP configuration for testing."""
    return HTTPConfig(
        timeout=10,
        max_connections=10,
        retry=RetryConfig(max_attempts=1, exponential_base=2.0, exponential_multiplier=1.0),
    )


@pytest.fixture
def api_config():
    """Create API configuration for testing."""
    return APIClientConfig(
        name="test-api",
        base_url="https://api.example.com",
        rate_limit=RateLimitConfig(requests_per_second=2.0),
        concurrency=ConcurrencyConfig(max_concurrent_requests=2),
    )


class TestRateLimitedAPIClient:
    """Test suite for RateLimitedAPIClient."""

    @pytest.mark.asyncio
    async def test_from_config(self, http_config, api_config):
        """Test creating client from configuration."""
        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            assert client.base_url == "https://api.example.com"
            assert client.rate_limiter is not None
            assert client.concurrency_limiter is not None
            assert client.rate_limiter.rate == 2.0  # rate is tokens per second
            assert client.concurrency_limiter.max_concurrent == 2

    @pytest.mark.asyncio
    async def test_from_config_with_auth(self, http_config):
        """Test creating client with authentication."""
        api_config = APIClientConfig(
            name="test-api",
            base_url="https://api.example.com",
            auth={"Authorization": "Bearer test-token-123"},
            rate_limit=RateLimitConfig(requests_per_second=5.0),
        )

        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            assert client.auth_headers["Authorization"] == "Bearer test-token-123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_limiting_enforcement(self, http_config):
        """Test that rate limiting is enforced on requests."""
        # Mock the endpoint
        respx.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        # Create config with small burst to ensure rate limiting kicks in quickly
        api_config = APIClientConfig(
            name="test-api",
            base_url="https://api.example.com",
            rate_limit=RateLimitConfig(
                requests_per_second=2,
                burst_size=1  # Only allow 1 request in burst
            ),
        )

        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            # Make 3 requests sequentially - should take at least 0.5 seconds (2 req/s = 0.5s between)
            start = time.monotonic()
            responses = []
            for _ in range(3):
                response = await client.get("/test")
                responses.append(response)
            elapsed = time.monotonic() - start

            # With 2 req/s and burst_size=1, 3 requests should take at least 1 second
            # (request 0 immediate, request 1 at 0.5s, request 2 at 1.0s)
            assert elapsed >= 0.9, f"Rate limiting not enforced: {elapsed}s"
            assert all(r.status_code == 200 for r in responses)

    @pytest.mark.asyncio
    @respx.mock
    async def test_concurrency_limiting_enforcement(self, http_config):
        """Test that concurrency limiting is enforced."""
        # Mock endpoint with delay
        async def slow_response(request):
            await asyncio.sleep(0.2)
            return httpx.Response(200, json={"status": "ok"})

        respx.get("https://api.example.com/slow").mock(side_effect=slow_response)

        # Create config with max 2 concurrent
        api_config = APIClientConfig(
            name="test-api",
            base_url="https://api.example.com",
            concurrency=ConcurrencyConfig(max_concurrent_requests=2),
        )

        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            # Start 4 requests simultaneously
            start = time.monotonic()
            tasks = [client.get("/slow") for _ in range(4)]
            responses = await asyncio.gather(*tasks)
            elapsed = time.monotonic() - start

            # With max 2 concurrent and 0.2s each, 4 requests should take at least 0.4s
            # (2 parallel batches of 2 requests)
            assert elapsed >= 0.35, f"Concurrency limiting not enforced: {elapsed}s"
            assert all(r.status_code == 200 for r in responses)

    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_and_concurrency_together(self, http_config):
        """Test rate and concurrency limiting working together."""
        # Mock endpoint
        respx.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        # Config with both limits
        api_config = APIClientConfig(
            name="test-api",
            base_url="https://api.example.com",
            rate_limit=RateLimitConfig(requests_per_second=5.0),
            concurrency=ConcurrencyConfig(max_concurrent_requests=2),
        )

        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            # Make 6 requests
            tasks = [client.get("/test") for _ in range(6)]
            responses = await asyncio.gather(*tasks)

            assert len(responses) == 6
            assert all(r.status_code == 200 for r in responses)

    @pytest.mark.asyncio
    @respx.mock
    async def test_requests_without_rate_limit(self, http_config):
        """Test client works without rate limiting."""
        # Mock endpoint
        respx.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        # Config without rate limit
        api_config = APIClientConfig(name="test-api", base_url="https://api.example.com")

        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            assert client.rate_limiter is None

            # Requests should be fast without rate limiting
            start = time.monotonic()
            tasks = [client.get("/test") for _ in range(5)]
            responses = await asyncio.gather(*tasks)
            elapsed = time.monotonic() - start

            assert elapsed < 0.5, "Requests too slow without rate limiting"
            assert all(r.status_code == 200 for r in responses)

    @pytest.mark.asyncio
    @respx.mock
    async def test_requests_without_concurrency_limit(self, http_config):
        """Test client works without concurrency limiting."""
        # Mock endpoint with delay
        async def slow_response(request):
            await asyncio.sleep(0.1)
            return httpx.Response(200, json={"status": "ok"})

        respx.get("https://api.example.com/slow").mock(side_effect=slow_response)

        # Config without concurrency limit
        api_config = APIClientConfig(name="test-api", base_url="https://api.example.com")

        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            assert client.concurrency_limiter is None

            # All requests should run in parallel
            start = time.monotonic()
            tasks = [client.get("/slow") for _ in range(5)]
            responses = await asyncio.gather(*tasks)
            elapsed = time.monotonic() - start

            # Should complete in ~0.1s (all parallel) not 0.5s (sequential)
            assert elapsed < 0.3, f"Requests not parallel: {elapsed}s"
            assert all(r.status_code == 200 for r in responses)

    @pytest.mark.asyncio
    @respx.mock
    async def test_bearer_auth(self, http_config):
        """Test bearer token authentication."""
        route = respx.get("https://api.example.com/auth-test").mock(
            return_value=httpx.Response(200, json={"authenticated": True})
        )

        api_config = APIClientConfig(
            name="test-api",
            base_url="https://api.example.com",
            auth={"Authorization": "Bearer secret-token"},
        )

        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            response = await client.get("/auth-test")

            assert response.status_code == 200
            # Check the request had the auth header
            assert route.calls.last.request.headers["Authorization"] == "Bearer secret-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_api_key_header_auth(self, http_config):
        """Test API key header authentication."""
        route = respx.get("https://api.example.com/auth-test").mock(
            return_value=httpx.Response(200, json={"authenticated": True})
        )

        api_config = APIClientConfig(
            name="test-api",
            base_url="https://api.example.com",
            auth={"X-API-Key": "api-key-123"},
        )

        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            response = await client.get("/auth-test")

            assert response.status_code == 200
            assert route.calls.last.request.headers["X-API-Key"] == "api-key-123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_api_key_query_auth(self, http_config):
        """Test API key query parameter authentication."""
        route = respx.get("https://api.example.com/auth-test").mock(
            return_value=httpx.Response(200, json={"authenticated": True})
        )

        api_config = APIClientConfig(
            name="test-api",
            base_url="https://api.example.com",
        )

        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            # Pass API key as query parameter
            response = await client.get("/auth-test", params={"api_key": "query-key-456"})

            assert response.status_code == 200
            # Check the URL contains the query parameter
            request_url = str(route.calls.last.request.url)
            assert "api_key=query-key-456" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_custom_headers(self, http_config):
        """Test custom headers are included."""
        route = respx.get("https://api.example.com/test").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        api_config = APIClientConfig(
            name="test-api",
            base_url="https://api.example.com",
            auth={"X-Custom-Header": "custom-value", "X-Client-ID": "test-123"},
        )

        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            response = await client.get("/test")

            assert response.status_code == 200
            assert route.calls.last.request.headers["X-Custom-Header"] == "custom-value"
            assert route.calls.last.request.headers["X-Client-ID"] == "test-123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_post_with_json_body(self, http_config, api_config):
        """Test POST request with JSON body."""
        route = respx.post("https://api.example.com/data").mock(
            return_value=httpx.Response(201, json={"id": 123, "created": True})
        )

        async with RateLimitedAPIClient.from_config(
            config=api_config
        ) as client:
            response = await client.post("/data", json={"name": "test", "value": 42})

            assert response.status_code == 201
            data = response.json()
            assert data["id"] == 123
            assert data["created"] is True

    @pytest.mark.asyncio
    async def test_multiple_clients_independent_limits(self, http_config):
        """Test multiple clients have independent rate limiters."""
        api_config_1 = APIClientConfig(
            name="api1",
            base_url="https://api1.example.com",
            rate_limit=RateLimitConfig(requests_per_second=10.0),
        )

        api_config_2 = APIClientConfig(
            name="api2",
            base_url="https://api2.example.com",
            rate_limit=RateLimitConfig(requests_per_second=5.0),
        )

        async with RateLimitedAPIClient.from_config(
            config=api_config_1
        ) as client1, RateLimitedAPIClient.from_config(
            config=api_config_2
        ) as client2:
            # Verify they have independent limiters
            assert client1.rate_limiter is not client2.rate_limiter
            assert client1.rate_limiter.rate == 10.0  # rate is tokens per second
            assert client2.rate_limiter.rate == 5.0
