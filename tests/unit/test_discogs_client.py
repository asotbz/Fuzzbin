"""Tests for the DiscogsClient class."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
import respx

from fuzzbin.api.discogs_client import DiscogsClient
from fuzzbin.common.config import (
    APIClientConfig,
)


@pytest.fixture(autouse=True)
def clear_discogs_env_vars(monkeypatch):
    """Clear Discogs environment variables before each test to prevent real credentials from interfering."""
    monkeypatch.delenv("DISCOGS_API_KEY", raising=False)
    monkeypatch.delenv("DISCOGS_API_SECRET", raising=False)


@pytest.fixture
def examples_dir():
    """Get path to examples directory."""
    return Path(__file__).parent.parent.parent / "examples"


@pytest.fixture
def search_response(examples_dir):
    """Load search response example."""
    with open(examples_dir / "discogs_search_response.json") as f:
        return json.load(f)


@pytest.fixture
def artist_releases_response(examples_dir):
    """Load artist releases response example."""
    with open(examples_dir / "discogs_artist_releases_response.json") as f:
        return json.load(f)


@pytest.fixture
def master_response(examples_dir):
    """Load master response example."""
    with open(examples_dir / "discogs_master_response.json") as f:
        return json.load(f)


@pytest.fixture
def release_response(examples_dir):
    """Load release response example."""
    with open(examples_dir / "discogs_release_response.json") as f:
        return json.load(f)


@pytest.fixture
def discogs_config():
    """Create Discogs API configuration for testing."""
    return APIClientConfig(
        auth={"api_key": "test-key-123", "api_secret": "test-secret-456"},
    )


class TestDiscogsClient:
    """Test suite for DiscogsClient."""

    @pytest.mark.asyncio
    async def test_from_config(self, discogs_config):
        """Test creating client from configuration."""
        async with DiscogsClient.from_config(config=discogs_config) as client:
            assert client.base_url == "https://api.discogs.com"
            assert client.rate_limiter is not None
            assert client.concurrency_limiter is not None
            assert "Authorization" in client.auth_headers
            assert (
                client.auth_headers["Authorization"]
                == "Discogs key=test-key-123, secret=test-secret-456"
            )
            assert "User-Agent" in client.auth_headers
            assert "fuzzbin" in client.auth_headers["User-Agent"]

    @pytest.mark.asyncio
    async def test_env_variables_override_config(self, discogs_config, monkeypatch):
        """Test that DISCOGS_API_KEY and DISCOGS_API_SECRET env variables override config."""
        monkeypatch.setenv("DISCOGS_API_KEY", "env-key-789")
        monkeypatch.setenv("DISCOGS_API_SECRET", "env-secret-abc")

        async with DiscogsClient.from_config(config=discogs_config) as client:
            assert (
                client.auth_headers["Authorization"]
                == "Discogs key=env-key-789, secret=env-secret-abc"
            )

    @pytest.mark.asyncio
    async def test_user_agent_format(self, discogs_config):
        """Test that User-Agent header follows required format."""
        async with DiscogsClient.from_config(config=discogs_config) as client:
            user_agent = client.auth_headers["User-Agent"]
            assert user_agent.startswith("fuzzbin/")
            assert "+https://github.com/asotbz/Fuzzbin" in user_agent

    @pytest.mark.asyncio
    @respx.mock
    async def test_search(self, discogs_config, search_response):
        """Test searching for releases by artist and track."""
        route = respx.get("https://api.discogs.com/database/search").mock(
            return_value=httpx.Response(
                200,
                json=search_response,
                headers={
                    "X-Discogs-Ratelimit": "60",
                    "X-Discogs-Ratelimit-Used": "1",
                    "X-Discogs-Ratelimit-Remaining": "59",
                },
            )
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            result = await client.search("nirvana", "smells like teen spirit")

            # Verify response structure
            assert "pagination" in result
            assert result["pagination"]["page"] == 1
            assert result["pagination"]["items"] == 10

            assert "results" in result
            assert len(result["results"]) > 0

            # Verify first result (Nevermind master)
            nevermind = next((r for r in result["results"] if r["id"] == 13814), None)
            assert nevermind is not None
            assert nevermind["type"] == "master"
            assert nevermind["title"] == "Nirvana - Nevermind"
            assert nevermind["year"] == "1992"

            # Verify request parameters
            assert (
                route.calls.last.request.headers["Authorization"]
                == "Discogs key=test-key-123, secret=test-secret-456"
            )
            assert "User-Agent" in route.calls.last.request.headers

            request_url = str(route.calls.last.request.url)
            assert "type=master" in request_url
            assert "format=album" in request_url
            assert "artist=nirvana" in request_url
            assert "track=smells" in request_url
            assert "page=1" in request_url
            assert "per_page=50" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_with_pagination(self, discogs_config, search_response):
        """Test search with custom pagination."""
        route = respx.get("https://api.discogs.com/database/search").mock(
            return_value=httpx.Response(
                200,
                json=search_response,
                headers={
                    "X-Discogs-Ratelimit": "60",
                    "X-Discogs-Ratelimit-Used": "2",
                    "X-Discogs-Ratelimit-Remaining": "58",
                },
            )
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            _result = await client.search("nirvana", "lithium", page=2, per_page=25)

            # Verify pagination parameters
            request_url = str(route.calls.last.request.url)
            assert "page=2" in request_url
            assert "per_page=25" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_artist_releases(self, discogs_config, artist_releases_response):
        """Test getting artist releases by artist ID."""
        route = respx.get("https://api.discogs.com/artists/125246/releases").mock(
            return_value=httpx.Response(
                200,
                json=artist_releases_response,
                headers={
                    "X-Discogs-Ratelimit": "60",
                    "X-Discogs-Ratelimit-Used": "3",
                    "X-Discogs-Ratelimit-Remaining": "57",
                },
            )
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            result = await client.get_artist_releases(125246)

            # Verify response structure
            assert "pagination" in result
            assert result["pagination"]["page"] == 1
            assert result["pagination"]["pages"] == 43
            assert result["pagination"]["items"] == 2138

            assert "releases" in result
            assert len(result["releases"]) > 0

            # Verify first release
            first_release = result["releases"][0]
            assert "id" in first_release
            assert "title" in first_release
            assert "year" in first_release
            assert "type" in first_release

            # Verify request
            assert (
                route.calls.last.request.headers["Authorization"]
                == "Discogs key=test-key-123, secret=test-secret-456"
            )
            request_url = str(route.calls.last.request.url)
            assert "page=1" in request_url
            assert "per_page=50" in request_url
            assert "sort=year" in request_url
            assert "sort_order=asc" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_artist_releases_with_custom_params(
        self, discogs_config, artist_releases_response
    ):
        """Test artist releases with custom sorting and pagination."""
        route = respx.get("https://api.discogs.com/artists/125246/releases").mock(
            return_value=httpx.Response(
                200,
                json=artist_releases_response,
                headers={
                    "X-Discogs-Ratelimit": "60",
                    "X-Discogs-Ratelimit-Used": "4",
                    "X-Discogs-Ratelimit-Remaining": "56",
                },
            )
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            _result = await client.get_artist_releases(
                125246, page=5, per_page=100, sort="title", sort_order="desc"
            )

            # Verify parameters
            request_url = str(route.calls.last.request.url)
            assert "page=5" in request_url
            assert "per_page=100" in request_url
            assert "sort=title" in request_url
            assert "sort_order=desc" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_master(self, discogs_config, master_response):
        """Test getting master release details by master ID."""
        route = respx.get("https://api.discogs.com/masters/13814").mock(
            return_value=httpx.Response(
                200,
                json=master_response,
                headers={
                    "X-Discogs-Ratelimit": "60",
                    "X-Discogs-Ratelimit-Used": "5",
                    "X-Discogs-Ratelimit-Remaining": "55",
                },
            )
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            result = await client.get_master(13814)

            # Verify response structure
            assert result["id"] == 13814
            assert result["title"] == "Nevermind"
            assert result["year"] == 1992
            assert result["main_release"] == 25823602

            # Verify artists
            assert "artists" in result
            assert len(result["artists"]) > 0
            assert result["artists"][0]["name"] == "Nirvana"
            assert result["artists"][0]["id"] == 125246

            # Verify tracklist
            assert "tracklist" in result
            assert len(result["tracklist"]) > 0
            first_track = result["tracklist"][0]
            assert first_track["title"] == "Smells Like Teen Spirit"
            assert first_track["position"] == "A1"

            # Verify genres and styles
            assert "genres" in result
            assert "Rock" in result["genres"]
            assert "styles" in result
            assert "Grunge" in result["styles"]

            # Verify images and videos
            assert "images" in result
            assert len(result["images"]) > 0
            assert "videos" in result
            assert len(result["videos"]) > 0

            # Verify request
            assert (
                route.calls.last.request.headers["Authorization"]
                == "Discogs key=test-key-123, secret=test-secret-456"
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_release(self, discogs_config, release_response):
        """Test getting release details by release ID."""
        route = respx.get("https://api.discogs.com/releases/25823602").mock(
            return_value=httpx.Response(
                200,
                json=release_response,
                headers={
                    "X-Discogs-Ratelimit": "60",
                    "X-Discogs-Ratelimit-Used": "6",
                    "X-Discogs-Ratelimit-Remaining": "54",
                },
            )
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            result = await client.get_release(25823602)

            # Verify response structure
            assert result["id"] == 25823602
            assert result["title"] == "Nevermind"
            assert result["year"] == 1992
            assert result["country"] == "Colombia"
            assert result["master_id"] == 13814

            # Verify artists
            assert "artists" in result
            assert len(result["artists"]) > 0
            assert result["artists"][0]["name"] == "Nirvana"

            # Verify labels and formats
            assert "labels" in result
            assert len(result["labels"]) > 0
            assert "formats" in result
            assert len(result["formats"]) > 0
            assert result["formats"][0]["name"] == "Vinyl"

            # Verify tracklist
            assert "tracklist" in result
            assert len(result["tracklist"]) > 0

            # Verify identifiers
            assert "identifiers" in result
            assert len(result["identifiers"]) > 0

            # Verify request
            assert (
                route.calls.last.request.headers["Authorization"]
                == "Discogs key=test-key-123, secret=test-secret-456"
            )

    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_limit_headers_tracked(self, discogs_config, search_response):
        """Test that rate limit headers are tracked and logged."""
        _route = respx.get("https://api.discogs.com/database/search").mock(
            return_value=httpx.Response(
                200,
                json=search_response,
                headers={
                    "X-Discogs-Ratelimit": "60",
                    "X-Discogs-Ratelimit-Used": "10",
                    "X-Discogs-Ratelimit-Remaining": "50",
                },
            )
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            result = await client.search("test", "test")

            # Verify the response was successful
            assert "results" in result

            # Headers should have been tracked by _make_request

    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_limit_adjustment(self, discogs_config, search_response):
        """Test that rate limiter is adjusted based on API headers."""
        # Use a significantly different limit to trigger adjustment
        _route = respx.get("https://api.discogs.com/database/search").mock(
            return_value=httpx.Response(
                200,
                json=search_response,
                headers={
                    "X-Discogs-Ratelimit": "120",  # API reports 2x the limit
                    "X-Discogs-Ratelimit-Used": "1",
                    "X-Discogs-Ratelimit-Remaining": "119",
                },
            )
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            # Initial limit should be 60 req/min = 1.0 req/sec
            initial_rate = client.rate_limiter.rate
            assert abs(initial_rate - 1.0) < 0.01

            # Make request
            await client.search("test", "test")

            # Rate limiter should have been adjusted to 120 req/min = 2.0 req/sec
            # because 120 - 60 = 60 which is > 10% of 60 (6)
            assert abs(client.rate_limiter.rate - 2.0) < 0.01

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_on_500_error(self, discogs_config, search_response):
        """Test that 500 errors are retried."""
        route = respx.get("https://api.discogs.com/database/search").mock(
            side_effect=[
                httpx.Response(500, json={"error": "Internal Server Error"}),
                httpx.Response(500, json={"error": "Internal Server Error"}),
                httpx.Response(
                    200,
                    json=search_response,
                    headers={
                        "X-Discogs-Ratelimit": "60",
                        "X-Discogs-Ratelimit-Used": "1",
                        "X-Discogs-Ratelimit-Remaining": "59",
                    },
                ),
            ]
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            result = await client.search("test", "test")

            # Should succeed after retries
            assert "results" in result
            # Should have made 3 attempts
            assert len(route.calls) == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_retry_on_404_error(self, discogs_config):
        """Test that 404 errors are not retried."""
        route = respx.get("https://api.discogs.com/masters/999999").mock(
            return_value=httpx.Response(404, json={"message": "Not Found"})
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_master(999999)

            # Should only make 1 attempt (no retries)
            assert len(route.calls) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_retry_on_401_error(self, discogs_config):
        """Test that 401 errors are not retried."""
        route = respx.get("https://api.discogs.com/database/search").mock(
            return_value=httpx.Response(401, json={"message": "Unauthorized"})
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.search("test", "test")

            # Should only make 1 attempt (no retries)
            assert len(route.calls) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_retry_on_403_error(self, discogs_config):
        """Test that 403 errors are not retried."""
        route = respx.get("https://api.discogs.com/database/search").mock(
            return_value=httpx.Response(403, json={"message": "Forbidden"})
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.search("test", "test")

            # Should only make 1 attempt (no retries)
            assert len(route.calls) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_limiting(self, discogs_config, search_response):
        """Test that rate limiting is applied with default settings."""
        route = respx.get("https://api.discogs.com/database/search").mock(
            return_value=httpx.Response(
                200,
                json=search_response,
                headers={
                    "X-Discogs-Ratelimit": "60",
                    "X-Discogs-Ratelimit-Used": "1",
                    "X-Discogs-Ratelimit-Remaining": "59",
                },
            )
        )

        async with DiscogsClient.from_config(config=discogs_config) as client:
            # Verify rate limiter is configured
            assert client.rate_limiter is not None
            # Verify rate is approximately correct (DEFAULT_REQUESTS_PER_MINUTE / 60 seconds)
            expected_rate = DiscogsClient.DEFAULT_REQUESTS_PER_MINUTE / 60.0
            assert abs(client.rate_limiter.rate - expected_rate) < 0.01

            # Make multiple requests - they should succeed
            for _ in range(3):
                await client.search("test", "test")

            assert len(route.calls) == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_concurrency_limiting(self, discogs_config, search_response):
        """Test that concurrency limiting is applied with default settings."""

        # Create a slow response to test concurrency
        async def slow_response(request):
            await asyncio.sleep(0.1)
            return httpx.Response(
                200,
                json=search_response,
                headers={
                    "X-Discogs-Ratelimit": "60",
                    "X-Discogs-Ratelimit-Used": "1",
                    "X-Discogs-Ratelimit-Remaining": "59",
                },
            )

        route = respx.get("https://api.discogs.com/database/search").mock(side_effect=slow_response)

        async with DiscogsClient.from_config(config=discogs_config) as client:
            # Verify concurrency limiter is configured with defaults
            assert client.concurrency_limiter is not None
            assert client.concurrency_limiter.max_concurrent == DiscogsClient.DEFAULT_MAX_CONCURRENT

            # Make concurrent requests - they should all succeed
            tasks = [client.search("test", f"test{i}") for i in range(5)]
            results = await asyncio.gather(*tasks)

            # All should succeed
            assert len(results) == 5
            assert len(route.calls) == 5

    @pytest.mark.asyncio
    async def test_client_without_credentials(self):
        """Test that client can be created without credentials."""
        config = APIClientConfig()

        async with DiscogsClient.from_config(config=config) as client:
            # Should not have Authorization header
            assert "Authorization" not in client.auth_headers
            # But should still have User-Agent
            assert "User-Agent" in client.auth_headers
