"""Tests for the IMVDbClient class."""

import asyncio
import json
import os
import time
from pathlib import Path

import httpx
import pytest
import respx

from fuzzbin.api.imvdb_client import IMVDbClient
from fuzzbin.common.config import (
    APIClientConfig,
    ConcurrencyConfig,
    HTTPConfig,
    RateLimitConfig,
    RetryConfig,
)
from fuzzbin.parsers.imvdb_models import (
    IMVDbEntity,
    IMVDbVideo,
    IMVDbVideoSearchResult,
)


@pytest.fixture
def examples_dir():
    """Get path to examples directory."""
    return Path(__file__).parent.parent.parent / "examples"


@pytest.fixture
def search_videos_response(examples_dir):
    """Load search videos response example."""
    with open(examples_dir / "imvdb_search_videos_response.json") as f:
        return json.load(f)


@pytest.fixture
def search_entities_response(examples_dir):
    """Load search entities response example."""
    with open(examples_dir / "imvdb_search_entities_response.json") as f:
        return json.load(f)


@pytest.fixture
def video_response(examples_dir):
    """Load video response example."""
    with open(examples_dir / "imvdb_video_response.json") as f:
        return json.load(f)


@pytest.fixture
def entity_response(examples_dir):
    """Load entity response example."""
    with open(examples_dir / "imvdb_entity_response.json") as f:
        return json.load(f)


@pytest.fixture
def imvdb_config():
    """Create IMVDb API configuration for testing."""
    return APIClientConfig(
        name="imvdb",
        base_url="https://imvdb.com/api/v1",
        http=HTTPConfig(
            timeout=10,
            retry=RetryConfig(
                max_attempts=3,
                status_codes=[500, 502, 503],  # Don't retry 403/404
            ),
        ),
        rate_limit=RateLimitConfig(requests_per_minute=1000, burst_size=50),
        concurrency=ConcurrencyConfig(max_concurrent_requests=10),
        custom={"app_key": "test-api-key-123"},
    )


class TestIMVDbClient:
    """Test suite for IMVDbClient."""

    @pytest.mark.asyncio
    async def test_from_config(self, imvdb_config):
        """Test creating client from configuration."""
        async with IMVDbClient.from_config(config=imvdb_config) as client:
            assert client.base_url == "https://imvdb.com/api/v1"
            assert client.rate_limiter is not None
            assert client.concurrency_limiter is not None
            assert "IMVDB-APP-KEY" in client.auth_headers
            assert client.auth_headers["IMVDB-APP-KEY"] == "test-api-key-123"

    @pytest.mark.asyncio
    async def test_env_variable_overrides_config(self, imvdb_config, monkeypatch):
        """Test that IMVDB_APP_KEY environment variable overrides config."""
        monkeypatch.setenv("IMVDB_APP_KEY", "env-key-456")

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            assert client.auth_headers["IMVDB-APP-KEY"] == "env-key-456"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_videos(self, imvdb_config, search_videos_response):
        """Test searching for videos by artist and track."""
        route = respx.get("https://imvdb.com/api/v1/search/videos").mock(
            return_value=httpx.Response(200, json=search_videos_response)
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            result = await client.search_videos("Robin Thicke", "Blurred Lines")

            # Verify result is correct type
            assert isinstance(result, IMVDbVideoSearchResult)
            
            # Verify pagination
            assert result.pagination.total_results == 196
            assert result.pagination.current_page == 1
            assert result.pagination.per_page == 25
            assert len(result.results) > 0
            
            # Verify first result
            first_video = result.results[0]
            assert first_video.song_title == "Blurred Lines"
            assert first_video.id == 121779770452

            # Verify request
            assert route.calls.last.request.headers["IMVDB-APP-KEY"] == "test-api-key-123"
            request_url = str(route.calls.last.request.url)
            assert "q=Robin+Thicke+Blurred+Lines" in request_url or "q=Robin%20Thicke%20Blurred%20Lines" in request_url
            assert "page=1" in request_url
            assert "per_page=25" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_videos_with_pagination(self, imvdb_config, search_videos_response):
        """Test video search with custom pagination."""
        route = respx.get("https://imvdb.com/api/v1/search/videos").mock(
            return_value=httpx.Response(200, json=search_videos_response)
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            result = await client.search_videos(
                "Robin Thicke", "Blurred Lines", page=2, per_page=10
            )

            # Verify pagination parameters
            request_url = str(route.calls.last.request.url)
            assert "page=2" in request_url
            assert "per_page=10" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_entities(self, imvdb_config, search_entities_response):
        """Test searching for entities by name."""
        route = respx.get("https://imvdb.com/api/v1/search/entities").mock(
            return_value=httpx.Response(200, json=search_entities_response)
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            result = await client.search_entities("Robin Thicke")

            # Verify response structure (search_entities still returns dict for now)
            assert result["total_results"] == 386
            assert result["current_page"] == 1
            assert len(result["results"]) > 0
            
            # Find Robin Thicke in results
            robin_thicke = next(
                (e for e in result["results"] if e["slug"] == "robin-thicke"), None
            )
            assert robin_thicke is not None
            assert robin_thicke["id"] == 838673

            # Verify request
            assert route.calls.last.request.headers["IMVDB-APP-KEY"] == "test-api-key-123"
            request_url = str(route.calls.last.request.url)
            assert "q=Robin+Thicke" in request_url or "q=Robin%20Thicke" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_entities_with_pagination(self, imvdb_config, search_entities_response):
        """Test entity search with custom pagination."""
        route = respx.get("https://imvdb.com/api/v1/search/entities").mock(
            return_value=httpx.Response(200, json=search_entities_response)
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            result = await client.search_entities("Robin", page=3, per_page=50)

            # Verify pagination parameters
            request_url = str(route.calls.last.request.url)
            assert "page=3" in request_url
            assert "per_page=50" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_video(self, imvdb_config, video_response):
        """Test getting video details by ID."""
        route = respx.get("https://imvdb.com/api/v1/video/121779770452").mock(
            return_value=httpx.Response(200, json=video_response)
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            result = await client.get_video(121779770452)

            # Verify result is correct type
            assert isinstance(result, IMVDbVideo)
            
            # Verify response structure
            assert result.id == 121779770452
            assert result.song_title == "Blurred Lines"
            assert result.year == 2013
            
            # Verify includes are present
            assert len(result.directors) > 0
            assert result.directors[0].entity_name == "Diane Martel"
            
            assert len(result.sources) > 0
            
            assert len(result.featured_artists) > 0
            
            assert result.credits is not None

            # Verify request includes parameter
            request_url = str(route.calls.last.request.url)
            assert "include=credits" in request_url
            assert "featured" in request_url
            assert "sources" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_entity(self, imvdb_config, entity_response):
        """Test getting entity details by ID."""
        route = respx.get("https://imvdb.com/api/v1/entity/838673").mock(
            return_value=httpx.Response(200, json=entity_response)
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            result = await client.get_entity(838673)

            # Verify result is correct type
            assert isinstance(result, IMVDbEntity)
            
            # Verify response structure
            assert result.id == 838673
            assert result.slug == "robin-thicke"
            assert result.artist_video_count == 4
            
            # Verify includes are present
            assert result.artist_videos_total == 19
            assert len(result.artist_videos) > 0
            
            assert result.featured_videos_total == 2

            # Verify request includes parameter
            request_url = str(route.calls.last.request.url)
            assert "include=artist_videos" in request_url
            assert "featured_videos" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_limiting_enforcement(self, imvdb_config, search_videos_response):
        """Test that rate limiting is enforced (1000 req/min)."""
        respx.get("https://imvdb.com/api/v1/search/videos").mock(
            return_value=httpx.Response(200, json=search_videos_response)
        )

        # Create config with lower rate for faster testing
        test_config = APIClientConfig(
            name="imvdb",
            base_url="https://imvdb.com/api/v1",
            rate_limit=RateLimitConfig(
                requests_per_second=5,  # 5 req/s for testing
                burst_size=2,
            ),
            custom={"app_key": "test-key"},
        )

        async with IMVDbClient.from_config(config=test_config) as client:
            # Make 6 requests
            start = time.monotonic()
            tasks = [
                client.search_videos("Artist", "Track") for _ in range(6)
            ]
            responses = await asyncio.gather(*tasks)
            elapsed = time.monotonic() - start

            # With 5 req/s and burst=2, 6 requests should take at least 0.8s
            assert elapsed >= 0.7, f"Rate limiting not enforced: {elapsed}s"
            assert len(responses) == 6

    @pytest.mark.asyncio
    @respx.mock
    async def test_concurrency_limiting(self, imvdb_config, search_videos_response):
        """Test that concurrency limiting is enforced."""
        # Mock with delay
        async def slow_response(request):
            await asyncio.sleep(0.15)
            return httpx.Response(200, json=search_videos_response)

        respx.get("https://imvdb.com/api/v1/search/videos").mock(
            side_effect=slow_response
        )

        # Create config with low concurrency for testing
        test_config = APIClientConfig(
            name="imvdb",
            base_url="https://imvdb.com/api/v1",
            concurrency=ConcurrencyConfig(max_concurrent_requests=2),
            custom={"app_key": "test-key"},
        )

        async with IMVDbClient.from_config(config=test_config) as client:
            # Start 6 requests simultaneously
            start = time.monotonic()
            tasks = [
                client.search_videos("Artist", "Track") for _ in range(6)
            ]
            responses = await asyncio.gather(*tasks)
            elapsed = time.monotonic() - start

            # With max 2 concurrent and 0.15s each, 6 requests should take at least 0.45s
            # (3 batches of 2 parallel requests)
            assert elapsed >= 0.40, f"Concurrency limiting not enforced: {elapsed}s"
            assert len(responses) == 6

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_retry_on_403(self, imvdb_config):
        """Test that 403 errors are not retried."""
        call_count = 0

        def count_calls(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(403, json={"error": "Forbidden"})

        respx.get("https://imvdb.com/api/v1/search/videos").mock(
            side_effect=count_calls
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.search_videos("Artist", "Track")

            assert exc_info.value.response.status_code == 403
            # Should only be called once (no retries)
            assert call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_no_retry_on_404(self, imvdb_config):
        """Test that 404 errors are not retried."""
        call_count = 0

        def count_calls(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(404, json={"error": "Not Found"})

        respx.get("https://imvdb.com/api/v1/video/999999").mock(
            side_effect=count_calls
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.get_video(999999)

            assert exc_info.value.response.status_code == 404
            # Should only be called once (no retries)
            assert call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_on_500(self, imvdb_config):
        """Test that 500 errors are retried."""
        call_count = 0

        def count_calls_then_success(request):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(500, json={"error": "Internal Server Error"})
            return httpx.Response(200, json={"total_results": 0, "results": []})

        respx.get("https://imvdb.com/api/v1/search/videos").mock(
            side_effect=count_calls_then_success
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            result = await client.search_videos("Artist", "Track")

            # Should succeed after retries
            assert isinstance(result, IMVDbVideoSearchResult)
            assert result.pagination.total_results == 0
            # Should have been called 3 times (initial + 2 retries)
            assert call_count == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_on_502(self, imvdb_config):
        """Test that 502 errors are retried."""
        call_count = 0

        def count_calls_then_success(request):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return httpx.Response(502, json={"error": "Bad Gateway"})
            return httpx.Response(200, json={"id": 123})

        respx.get("https://imvdb.com/api/v1/video/123").mock(
            side_effect=count_calls_then_success
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            result = await client.get_video(123)

            # Should succeed after retry
            assert isinstance(result, IMVDbVideo)
            assert result.id == 123
            # Should have been called 2 times (initial + 1 retry)
            assert call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_on_503(self, imvdb_config):
        """Test that 503 errors are retried."""
        call_count = 0

        def count_calls_then_success(request):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return httpx.Response(503, json={"error": "Service Unavailable"})
            return httpx.Response(200, json={"id": 456, "slug": "test", "url": "test", "artist_video_count": 0, "featured_video_count": 0})

        respx.get("https://imvdb.com/api/v1/entity/456").mock(
            side_effect=count_calls_then_success
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            result = await client.get_entity(456)

            # Should succeed after retry
            assert isinstance(result, IMVDbEntity)
            assert result.id == 456
            # Should have been called 2 times (initial + 1 retry)
            assert call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_special_characters_in_search(self, imvdb_config, search_videos_response):
        """Test that special characters in search queries are properly encoded."""
        route = respx.get("https://imvdb.com/api/v1/search/videos").mock(
            return_value=httpx.Response(200, json=search_videos_response)
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            # Search with special characters
            await client.search_videos("AC/DC", "Back In Black")

            # Verify query was encoded properly (httpx handles encoding)
            request_url = str(route.calls.last.request.url)
            # URL should contain encoded version of the search query
            assert "q=" in request_url
            # The slash should be encoded
            assert "AC%2FDC" in request_url or "AC/DC" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_api_key_header_format(self, imvdb_config):
        """Test that API key is sent with correct header name."""
        route = respx.get("https://imvdb.com/api/v1/search/videos").mock(
            return_value=httpx.Response(200, json={"total_results": 0, "results": []})
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            await client.search_videos("Artist", "Track")

            # Verify the custom header name
            assert route.calls.last.request.headers["IMVDB-APP-KEY"] == "test-api-key-123"

    @pytest.mark.asyncio
    async def test_client_without_api_key(self):
        """Test that client can be created without an API key."""
        # Ensure env var is not set
        if "IMVDB_APP_KEY" in os.environ:
            del os.environ["IMVDB_APP_KEY"]

        config = APIClientConfig(
            name="imvdb",
            base_url="https://imvdb.com/api/v1",
        )

        async with IMVDbClient.from_config(config=config) as client:
            # Should work but not have the auth header
            assert "IMVDB-APP-KEY" not in client.auth_headers or client.auth_headers.get("IMVDB-APP-KEY") is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_video_by_artist_title_exact_match(self, imvdb_config, search_videos_response):
        """Test search_video_by_artist_title with exact match."""
        route = respx.get("https://imvdb.com/api/v1/search/videos").mock(
            return_value=httpx.Response(200, json=search_videos_response)
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            video = await client.search_video_by_artist_title("Robin Thicke", "Blurred Lines")

            # Verify result
            assert isinstance(video, IMVDbVideo)
            assert video.id == 121779770452
            assert video.song_title == "Blurred Lines"
            assert video.is_exact_match is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_video_by_artist_title_with_featured_artists(self, imvdb_config, search_videos_response):
        """Test search_video_by_artist_title strips featured artists from query."""
        route = respx.get("https://imvdb.com/api/v1/search/videos").mock(
            return_value=httpx.Response(200, json=search_videos_response)
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            # Query with featured artist notation
            video = await client.search_video_by_artist_title("Robin Thicke ft. T.I.", "Blurred Lines")

            # Verify that featured artist was stripped from query (URL is lowercase)
            request_url = str(route.calls.last.request.url).lower()
            assert "robin" in request_url and "thicke" in request_url
            assert "t.i" not in request_url  # Featured artist should not be present

            # Verify result
            assert video.id == 121779770452
            assert video.is_exact_match is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_video_by_artist_title_no_results(self, imvdb_config):
        """Test search_video_by_artist_title raises EmptySearchResultsError when no results."""
        from fuzzbin.parsers.imvdb_models import EmptySearchResultsError

        respx.get("https://imvdb.com/api/v1/search/videos").mock(
            return_value=httpx.Response(200, json={"total_results": 0, "results": []})
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            with pytest.raises(EmptySearchResultsError) as exc_info:
                await client.search_video_by_artist_title("Nonexistent Artist", "Nonexistent Song")

            assert "Nonexistent Artist" in str(exc_info.value).lower() or "nonexistent artist" in str(exc_info.value)
            assert "Nonexistent Song" in str(exc_info.value).lower() or "nonexistent song" in str(exc_info.value)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_video_by_artist_title_no_match(self, imvdb_config, search_videos_response):
        """Test search_video_by_artist_title raises VideoNotFoundError when no match."""
        from fuzzbin.parsers.imvdb_models import VideoNotFoundError

        respx.get("https://imvdb.com/api/v1/search/videos").mock(
            return_value=httpx.Response(200, json=search_videos_response)
        )

        async with IMVDbClient.from_config(config=imvdb_config) as client:
            with pytest.raises(VideoNotFoundError):
                await client.search_video_by_artist_title("Completely Different Artist", "Totally Different Song")
