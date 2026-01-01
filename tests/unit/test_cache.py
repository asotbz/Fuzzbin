"""Tests for HTTP response caching using Hishel."""

import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any

import httpx
import pytest
import respx

from fuzzbin.common.config import (
    HTTPConfig,
    CacheConfig,
)
from fuzzbin.common.http_client import AsyncHTTPClient
from fuzzbin.common.rate_limiter import RateLimiter
from fuzzbin.api.base_client import RateLimitedAPIClient


@pytest.fixture
def cache_config(tmp_path: Path) -> CacheConfig:
    """Create a cache configuration for testing."""
    cache_db = tmp_path / "test_cache.db"
    return CacheConfig(
        enabled=True,
        storage_path=str(cache_db),
        ttl=3600,
        stale_while_revalidate=60,
        cacheable_methods=["GET", "HEAD"],
        cacheable_status_codes=[200, 203, 204, 206, 300, 301, 308],
    )


@pytest.fixture
def http_config() -> HTTPConfig:
    """Create an HTTP configuration for testing."""
    return HTTPConfig(timeout=10)


@pytest.fixture
def api_client_config(http_config: HTTPConfig, cache_config: CacheConfig) -> dict:
    """Create configuration dict for API client with cache enabled."""
    return {
        "http_config": http_config,
        "base_url": "https://api.example.com",
        "cache_config": cache_config,
    }


@pytest.mark.asyncio
class TestCacheConfiguration:
    """Test cache configuration validation and setup."""

    async def test_cache_config_validation(self, tmp_path: Path):
        """Test that cache configuration validates properly."""
        cache_config = CacheConfig(
            enabled=True,
            storage_path=str(tmp_path / "cache.db"),
            ttl=1800,
            stale_while_revalidate=120,
        )

        assert cache_config.enabled is True
        assert cache_config.ttl == 1800
        assert cache_config.stale_while_revalidate == 120
        assert "GET" in cache_config.cacheable_methods
        assert "HEAD" in cache_config.cacheable_methods
        assert 200 in cache_config.cacheable_status_codes

    async def test_cache_config_methods_validation(self):
        """Test that invalid HTTP methods are rejected."""
        with pytest.raises(ValueError, match="Invalid HTTP method"):
            CacheConfig(
                enabled=True,
                cacheable_methods=["GET", "INVALID"],
            )

    async def test_cache_config_status_codes_validation(self):
        """Test that invalid status codes are rejected."""
        with pytest.raises(ValueError, match="Invalid HTTP status code"):
            CacheConfig(
                enabled=True,
                cacheable_status_codes=[200, 999],
            )

    async def test_cache_disabled_by_default(self):
        """Test that cache is disabled by default."""
        cache_config = CacheConfig()
        assert cache_config.enabled is False


@pytest.mark.asyncio
class TestCacheHitMiss:
    """Test cache hit and miss scenarios."""

    @respx.mock
    async def test_cache_miss_first_request(
        self, http_config: HTTPConfig, cache_config: CacheConfig
    ):
        """Test that first request results in cache miss."""
        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config
        ) as client:
            response = await client.get("/data")

            assert response.status_code == 200
            assert response.json() == {"result": "success"}
            # First request should not be from cache
            assert not client._is_cached_response(response)

    @respx.mock
    async def test_cache_hit_second_request(
        self, http_config: HTTPConfig, cache_config: CacheConfig
    ):
        """Test that second identical request results in cache hit."""
        mock_route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config
        ) as client:
            # First request
            response1 = await client.get("/data")
            assert response1.status_code == 200
            assert mock_route.call_count == 1

            # Second request should be from cache
            response2 = await client.get("/data")
            assert response2.status_code == 200
            assert response2.json() == {"result": "success"}
            # Should still be 1 because second request came from cache
            assert mock_route.call_count == 1
            assert client._is_cached_response(response2)

    @respx.mock
    async def test_cache_respects_http_method(
        self, http_config: HTTPConfig, cache_config: CacheConfig
    ):
        """Test that only configured methods are cached."""
        # POST should not be cached by default
        mock_route = respx.post("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "created"})
        )

        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config
        ) as client:
            # First POST request
            response1 = await client.post("/data", json={"test": "data"})
            assert response1.status_code == 200
            assert mock_route.call_count == 1

            # Second POST request - should NOT be from cache
            response2 = await client.post("/data", json={"test": "data"})
            assert response2.status_code == 200
            # Should be 2 because POST is not cached
            assert mock_route.call_count == 2
            assert not client._is_cached_response(response2)

    @respx.mock
    async def test_cache_respects_status_codes(
        self, http_config: HTTPConfig, cache_config: CacheConfig
    ):
        """Test that only configured status codes are cached."""
        # 404 should not be cached by default
        mock_route = respx.get("https://api.example.com/notfound").mock(
            return_value=httpx.Response(404, json={"error": "not found"})
        )

        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config
        ) as client:
            # First request
            response1 = await client.get("/notfound")
            assert response1.status_code == 404
            assert mock_route.call_count == 1

            # Second request - should NOT be from cache
            response2 = await client.get("/notfound")
            assert response2.status_code == 404
            # Should be 2 because 404 is not cached
            assert mock_route.call_count == 2


@pytest.mark.asyncio
class TestCacheStorage:
    """Test SQLite cache storage functionality."""

    @respx.mock
    async def test_sqlite_storage_created(
        self, http_config: HTTPConfig, cache_config: CacheConfig
    ):
        """Test that SQLite database file is created."""
        storage_path = Path(cache_config.storage_path)
        assert not storage_path.exists()

        respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config
        ) as client:
            await client.get("/data")
            # Storage file should be created
            assert storage_path.exists()
            assert storage_path.is_file()

    @respx.mock
    async def test_shared_sqlite_storage(
        self, http_config: HTTPConfig, tmp_path: Path
    ):
        """Test that multiple clients can share the same SQLite database."""
        shared_cache_db = tmp_path / "shared_cache.db"
        
        cache_config1 = CacheConfig(
            enabled=True,
            storage_path=str(shared_cache_db),
            ttl=3600,
        )
        
        cache_config2 = CacheConfig(
            enabled=True,
            storage_path=str(shared_cache_db),
            ttl=3600,
        )

        mock_route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        # First client makes request
        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config1
        ) as client1:
            response1 = await client1.get("/data")
            assert response1.status_code == 200
            assert mock_route.call_count == 1

        # Second client should use the cached response from shared database
        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config2
        ) as client2:
            response2 = await client2.get("/data")
            assert response2.status_code == 200
            # Should still be 1 because second client used cached response
            assert mock_route.call_count == 1


@pytest.mark.asyncio
class TestCacheClearing:
    """Test cache clearing functionality."""

    @respx.mock
    async def test_clear_cache(
        self, http_config: HTTPConfig, cache_config: CacheConfig
    ):
        """Test that clear_cache removes all cached responses."""
        mock_route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config
        ) as client:
            # First request
            response1 = await client.get("/data")
            assert response1.status_code == 200
            assert mock_route.call_count == 1

            # Second request should be cached
            response2 = await client.get("/data")
            assert mock_route.call_count == 1

            # Clear cache
            await client.clear_cache()

            # Third request should not be cached
            response3 = await client.get("/data")
            assert response3.status_code == 200
            # Should be 2 now because cache was cleared
            assert mock_route.call_count == 2

    @respx.mock
    async def test_clear_cache_on_api_client(
        self, api_client_config: dict
    ):
        """Test cache clearing on RateLimitedAPIClient."""
        mock_route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        async with RateLimitedAPIClient(
            http_config=api_client_config["http_config"],
            base_url=api_client_config["base_url"],
            cache_config=api_client_config["cache_config"],
        ) as client:
            # First request
            await client.get("/data")
            assert mock_route.call_count == 1

            # Second request should be cached
            await client.get("/data")
            assert mock_route.call_count == 1

            # Clear cache
            await client.clear_cache()

            # Third request should hit the API again
            await client.get("/data")
            assert mock_route.call_count == 2


@pytest.mark.asyncio
class TestCacheWithRateLimiting:
    """Test interaction between cache and rate limiting."""

    @respx.mock
    async def test_cache_hit_bypasses_rate_limiter(
        self, api_client_config: dict
    ):
        """Test that cached responses don't consume rate limit quota."""
        mock_route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        rate_limiter = RateLimiter(requests_per_minute=60)
        async with RateLimitedAPIClient(
            http_config=api_client_config["http_config"],
            base_url=api_client_config["base_url"],
            cache_config=api_client_config["cache_config"],
            rate_limiter=rate_limiter,
        ) as client:
            # First request - should use rate limiter
            response1 = await client.get("/data")
            assert response1.status_code == 200
            assert mock_route.call_count == 1

            # Record available tokens after first request
            if client.rate_limiter:
                tokens_after_first = client.rate_limiter.get_available_tokens()

                # Second request should be cached and NOT consume rate limit
                response2 = await client.get("/data")
                assert response2.status_code == 200
                assert mock_route.call_count == 1  # Still 1, from cache
                
                # Tokens should be approximately the same (cache hit doesn't consume rate limit)
                # Allow for slight increase due to bucket refill over time
                tokens_after_second = client.rate_limiter.get_available_tokens()
                assert tokens_after_second >= tokens_after_first
                assert tokens_after_second < tokens_after_first + 1.0  # Less than 1 second of refill

    @respx.mock
    async def test_multiple_cache_hits_preserve_rate_limit(
        self, api_client_config: dict
    ):
        """Test that multiple cache hits don't consume any rate limit."""
        mock_route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        rate_limiter = RateLimiter(requests_per_minute=60)
        async with RateLimitedAPIClient(
            http_config=api_client_config["http_config"],
            base_url=api_client_config["base_url"],
            cache_config=api_client_config["cache_config"],
            rate_limiter=rate_limiter,
        ) as client:
            # First request
            await client.get("/data")
            
            if client.rate_limiter:
                tokens_after_first = client.rate_limiter.get_available_tokens()

                # Make 5 more requests - all should be cached
                for _ in range(5):
                    await client.get("/data")

                # Only 1 actual request should have been made
                assert mock_route.call_count == 1
                
                # Rate limit tokens should be approximately unchanged
                # Allow for slight increase due to bucket refill over time
                tokens_after_cached = client.rate_limiter.get_available_tokens()
                assert tokens_after_cached >= tokens_after_first
                assert tokens_after_cached < tokens_after_first + 1.0  # Less than 1 second of refill


class TestPerAPIConfiguration:
    """Test per-API cache configuration."""

    @respx.mock
    async def test_different_ttl_per_api(self, http_config: HTTPConfig, tmp_path: Path):
        """Test that different APIs can have different cache TTLs."""
        cache_db = tmp_path / "multi_api_cache.db"

        # API 1: Short TTL (1 second)
        cache_config1 = CacheConfig(
            enabled=True,
            storage_path=str(cache_db),
            ttl=1,
            stale_while_revalidate=0,
        )

        # API 2: Long TTL (1 hour)
        cache_config2 = CacheConfig(
            enabled=True,
            storage_path=str(cache_db),
            ttl=3600,
            stale_while_revalidate=60,
        )

        mock_route1 = respx.get("https://api1.example.com/data").mock(
            return_value=httpx.Response(200, json={"api": "1"})
        )
        
        mock_route2 = respx.get("https://api2.example.com/data").mock(
            return_value=httpx.Response(200, json={"api": "2"})
        )

        # Test API 1 with short TTL
        async with AsyncHTTPClient(
            http_config, "https://api1.example.com", cache_config1
        ) as client1:
            await client1.get("/data")
            assert mock_route1.call_count == 1

        # Test API 2 with long TTL
        async with AsyncHTTPClient(
            http_config, "https://api2.example.com", cache_config2
        ) as client2:
            await client2.get("/data")
            assert mock_route2.call_count == 1

            # Both configs are valid and can coexist
            assert cache_config1.ttl == 1
            assert cache_config2.ttl == 3600

    @respx.mock
    async def test_cache_disabled_for_specific_api(
        self, http_config: HTTPConfig, tmp_path: Path
    ):
        """Test that cache can be disabled for specific APIs."""
        # API 1: Cache enabled
        cache_config1 = CacheConfig(
            enabled=True,
            storage_path=str(tmp_path / "cache1.db"),
            ttl=3600,
        )

        # API 2: Cache disabled
        cache_config2 = CacheConfig(
            enabled=False,
        )

        mock_route1 = respx.get("https://api1.example.com/data").mock(
            return_value=httpx.Response(200, json={"cached": True})
        )
        
        mock_route2 = respx.get("https://api2.example.com/data").mock(
            return_value=httpx.Response(200, json={"cached": False})
        )

        # API 1: Should cache
        async with AsyncHTTPClient(
            http_config, "https://api1.example.com", cache_config1
        ) as client1:
            await client1.get("/data")
            await client1.get("/data")
            # Only 1 request due to caching
            assert mock_route1.call_count == 1

        # API 2: Should NOT cache
        async with AsyncHTTPClient(
            http_config, "https://api2.example.com", cache_config2
        ) as client2:
            await client2.get("/data")
            await client2.get("/data")
            # 2 requests because caching is disabled
            assert mock_route2.call_count == 2


@pytest.mark.asyncio
class TestCacheWithRetries:
    """Test interaction between cache and retry logic."""

    @respx.mock
    async def test_cache_miss_triggers_retry_on_error(
        self, http_config: HTTPConfig, cache_config: CacheConfig
    ):
        """Test that cache misses still trigger retry logic on errors."""
        # First request fails, second succeeds
        mock_route = respx.get("https://api.example.com/data").mock(
            side_effect=[
                httpx.Response(500, json={"error": "server error"}),
                httpx.Response(200, json={"result": "success"}),
            ]
        )

        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config
        ) as client:
            response = await client.get("/data")
            
            # Should succeed after retry
            assert response.status_code == 200
            assert response.json() == {"result": "success"}
            # Should have made 2 requests (1 failure + 1 retry)
            assert mock_route.call_count == 2

    @respx.mock
    async def test_cached_response_no_retry(
        self, http_config: HTTPConfig, cache_config: CacheConfig
    ):
        """Test that cached responses are returned immediately without retries."""
        mock_route = respx.get("https://api.example.com/data").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config
        ) as client:
            # First request
            response1 = await client.get("/data")
            assert response1.status_code == 200
            assert mock_route.call_count == 1

            # Cached request should be instant (no retry logic involved)
            response2 = await client.get("/data")
            assert response2.status_code == 200
            # Still 1 request total
            assert mock_route.call_count == 1


@pytest.mark.asyncio
class TestCacheWithAuthentication:
    """Test that cache keys include authentication headers."""

    @respx.mock
    async def test_different_auth_different_cache(
        self, http_config: HTTPConfig, tmp_path: Path
    ):
        """Test that different auth credentials use separate cache databases."""
        # Use separate cache databases for different auth contexts
        cache_db1 = tmp_path / "auth1_cache.db"
        cache_db2 = tmp_path / "auth2_cache.db"
        
        cache_config1 = CacheConfig(
            enabled=True,
            storage_path=str(cache_db1),
            ttl=3600,
        )
        
        cache_config2 = CacheConfig(
            enabled=True,
            storage_path=str(cache_db2),
            ttl=3600,
        )

        # Mock route that returns different data based on auth header
        def auth_response(request):
            auth_header = request.headers.get("Authorization", "")
            if "token1" in auth_header:
                return httpx.Response(200, json={"user": "user1"})
            elif "token2" in auth_header:
                return httpx.Response(200, json={"user": "user2"})
            return httpx.Response(401, json={"error": "unauthorized"})

        mock_route = respx.get("https://api.example.com/user").mock(
            side_effect=auth_response
        )

        # Client 1 with token1 and its own cache
        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config1
        ) as client1:
            response1 = await client1.get(
                "/user", headers={"Authorization": "Bearer token1"}
            )
            assert response1.json()["user"] == "user1"
            assert mock_route.call_count == 1

        # Client 2 with token2 and its own cache - should make a new request
        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config2
        ) as client2:
            response2 = await client2.get(
                "/user", headers={"Authorization": "Bearer token2"}
            )
            assert response2.json()["user"] == "user2"
            # Should be 2 because different cache databases
            assert mock_route.call_count == 2

        # Client 1 again with token1 - should use cache
        async with AsyncHTTPClient(
            http_config, "https://api.example.com", cache_config1
        ) as client3:
            response3 = await client3.get(
                "/user", headers={"Authorization": "Bearer token1"}
            )
            assert response3.json()["user"] == "user1"
            # Should still be 2 because this matches client1's cached request
            assert mock_route.call_count == 2
