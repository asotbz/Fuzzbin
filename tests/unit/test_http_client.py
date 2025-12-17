"""Unit tests for AsyncHTTPClient."""

import pytest
import httpx
import respx

from fuzzbin.common.http_client import AsyncHTTPClient
from fuzzbin.common.config import HTTPConfig, RetryConfig


class TestAsyncHTTPClient:
    """Test suite for AsyncHTTPClient."""

    @pytest.mark.asyncio
    async def test_get_success(self, http_config: HTTPConfig):
        """Test successful GET request."""
        with respx.mock:
            route = respx.get("https://api.example.com/users/1").mock(
                return_value=httpx.Response(
                    200,
                    json={"id": 1, "name": "John Doe"},
                )
            )

            async with AsyncHTTPClient(
                http_config, base_url="https://api.example.com"
            ) as client:
                response = await client.get("/users/1")

            assert response.status_code == 200
            assert response.json() == {"id": 1, "name": "John Doe"}
            assert route.called
            assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_post_with_json(self, http_config: HTTPConfig):
        """Test POST request with JSON payload."""
        with respx.mock:
            route = respx.post("https://api.example.com/users").mock(
                return_value=httpx.Response(
                    201,
                    json={"id": 2, "created": True},
                )
            )

            async with AsyncHTTPClient(
                http_config, base_url="https://api.example.com"
            ) as client:
                response = await client.post(
                    "/users",
                    json={"name": "Jane Doe", "email": "jane@example.com"},
                )

            assert response.status_code == 201
            assert response.json()["created"] is True
            assert route.called

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self, http_config_with_retry: HTTPConfig):
        """Test retry logic succeeds after network errors."""
        config = http_config_with_retry

        with respx.mock:
            # First two calls fail with network errors, third succeeds
            route = respx.get("https://api.example.com/data").mock(
                side_effect=[
                    httpx.ConnectError("Connection failed"),
                    httpx.TimeoutException("Request timeout"),
                    httpx.Response(200, json={"data": "success"}),
                ]
            )

            async with AsyncHTTPClient(
                config, base_url="https://api.example.com"
            ) as client:
                response = await client.get("/data")

            assert response.status_code == 200
            assert response.json() == {"data": "success"}
            assert route.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, http_config_with_retry: HTTPConfig):
        """Test retry logic exhausts and raises exception."""
        config = http_config_with_retry

        with respx.mock:
            # All attempts fail with timeout
            route = respx.get("https://api.example.com/fail").mock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            async with AsyncHTTPClient(
                config, base_url="https://api.example.com"
            ) as client:
                with pytest.raises(httpx.TimeoutException):
                    await client.get("/fail")

            # Should retry max_attempts times (3 in this case)
            assert route.call_count == config.retry.max_attempts

    @pytest.mark.asyncio
    async def test_retry_on_500_error(self, http_config_with_retry: HTTPConfig):
        """Test retry on 500 Internal Server Error."""
        config = http_config_with_retry

        with respx.mock:
            # First call returns 500, second succeeds
            route = respx.get("https://api.example.com/unstable").mock(
                side_effect=[
                    httpx.Response(500, json={"error": "Internal Server Error"}),
                    httpx.Response(200, json={"status": "ok"}),
                ]
            )

            async with AsyncHTTPClient(
                config, base_url="https://api.example.com"
            ) as client:
                response = await client.get("/unstable")

            assert response.status_code == 200
            assert route.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_503_error(self, http_config_with_retry: HTTPConfig):
        """Test retry on 503 Service Unavailable."""
        config = http_config_with_retry

        with respx.mock:
            # First two calls return 503, third succeeds
            route = respx.get("https://api.example.com/service").mock(
                side_effect=[
                    httpx.Response(503, json={"error": "Service Unavailable"}),
                    httpx.Response(503, json={"error": "Service Unavailable"}),
                    httpx.Response(200, json={"status": "available"}),
                ]
            )

            async with AsyncHTTPClient(
                config, base_url="https://api.example.com"
            ) as client:
                response = await client.get("/service")

            assert response.status_code == 200
            assert route.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_404_error(self, http_config: HTTPConfig):
        """Test that 404 errors are not retried."""
        with respx.mock:
            route = respx.get("https://api.example.com/notfound").mock(
                return_value=httpx.Response(404, json={"error": "Not Found"})
            )

            async with AsyncHTTPClient(
                http_config, base_url="https://api.example.com"
            ) as client:
                response = await client.get("/notfound")

            # Should not raise, just return 404
            assert response.status_code == 404
            # Should only be called once (no retries)
            assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_400_error(self, http_config: HTTPConfig):
        """Test that 400 Bad Request errors are not retried."""
        with respx.mock:
            route = respx.post("https://api.example.com/data").mock(
                return_value=httpx.Response(400, json={"error": "Bad Request"})
            )

            async with AsyncHTTPClient(
                http_config, base_url="https://api.example.com"
            ) as client:
                response = await client.post("/data", json={"invalid": "data"})

            assert response.status_code == 400
            assert route.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_429_rate_limit(self, http_config_with_retry: HTTPConfig):
        """Test retry on 429 Too Many Requests."""
        config = http_config_with_retry

        with respx.mock:
            # First call rate limited, second succeeds
            route = respx.get("https://api.example.com/rate-limited").mock(
                side_effect=[
                    httpx.Response(429, json={"error": "Too Many Requests"}),
                    httpx.Response(200, json={"data": "success"}),
                ]
            )

            async with AsyncHTTPClient(
                config, base_url="https://api.example.com"
            ) as client:
                response = await client.get("/rate-limited")

            assert response.status_code == 200
            assert route.call_count == 2

    @pytest.mark.asyncio
    async def test_put_request(self, http_config: HTTPConfig):
        """Test PUT request."""
        with respx.mock:
            route = respx.put("https://api.example.com/users/1").mock(
                return_value=httpx.Response(200, json={"id": 1, "updated": True})
            )

            async with AsyncHTTPClient(
                http_config, base_url="https://api.example.com"
            ) as client:
                response = await client.put("/users/1", json={"name": "Updated"})

            assert response.status_code == 200
            assert route.called

    @pytest.mark.asyncio
    async def test_delete_request(self, http_config: HTTPConfig):
        """Test DELETE request."""
        with respx.mock:
            route = respx.delete("https://api.example.com/users/1").mock(
                return_value=httpx.Response(204)
            )

            async with AsyncHTTPClient(
                http_config, base_url="https://api.example.com"
            ) as client:
                response = await client.delete("/users/1")

            assert response.status_code == 204
            assert route.called

    @pytest.mark.asyncio
    async def test_generic_request_method(self, http_config: HTTPConfig):
        """Test generic request method with custom HTTP method."""
        with respx.mock:
            route = respx.head("https://api.example.com/status").mock(
                return_value=httpx.Response(200)
            )

            async with AsyncHTTPClient(
                http_config, base_url="https://api.example.com"
            ) as client:
                response = await client.request("HEAD", "/status")

            assert response.status_code == 200
            assert route.called

    @pytest.mark.asyncio
    async def test_context_manager_initialization(self, http_config: HTTPConfig):
        """Test that client requires context manager."""
        client = AsyncHTTPClient(http_config, base_url="https://api.example.com")

        # Should raise error if used without context manager
        with pytest.raises(RuntimeError, match="Client not initialized"):
            await client.get("/test")

    @pytest.mark.asyncio
    async def test_multiple_requests_same_client(self, http_config: HTTPConfig):
        """Test multiple requests with the same client instance."""
        with respx.mock:
            route1 = respx.get("https://api.example.com/endpoint1").mock(
                return_value=httpx.Response(200, json={"id": 1})
            )
            route2 = respx.get("https://api.example.com/endpoint2").mock(
                return_value=httpx.Response(200, json={"id": 2})
            )

            async with AsyncHTTPClient(
                http_config, base_url="https://api.example.com"
            ) as client:
                response1 = await client.get("/endpoint1")
                response2 = await client.get("/endpoint2")

            assert response1.json()["id"] == 1
            assert response2.json()["id"] == 2
            assert route1.called
            assert route2.called
