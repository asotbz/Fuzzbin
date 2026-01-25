"""Tests for the MusicBrainzClient class."""

import json
from pathlib import Path

import httpx
import pytest
import respx

from fuzzbin.api.musicbrainz_client import MusicBrainzClient
from fuzzbin.common.config import APIClientConfig
from fuzzbin.parsers.musicbrainz_models import RecordingNotFoundError


@pytest.fixture
def examples_dir():
    """Get path to examples directory."""
    return Path(__file__).parent.parent.parent / "examples"


@pytest.fixture
def search_response(examples_dir):
    """Load search response example."""
    with open(examples_dir / "musicbrainz_search_response.json") as f:
        return json.load(f)


@pytest.fixture
def isrc_search_response(examples_dir):
    """Load ISRC search response example."""
    with open(examples_dir / "musicbrainz_isrc_search_response.json") as f:
        return json.load(f)


@pytest.fixture
def isrc_response(examples_dir):
    """Load ISRC lookup response example."""
    with open(examples_dir / "musicbrainz_isrc_response.json") as f:
        return json.load(f)


@pytest.fixture
def recording_response(examples_dir):
    """Load recording response example."""
    with open(examples_dir / "musicbrainz_recording_response.json") as f:
        return json.load(f)


@pytest.fixture
def musicbrainz_config():
    """Create MusicBrainz API configuration for testing."""
    return APIClientConfig(name="musicbrainz")


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary directory for cache storage to avoid test interference."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


class TestMusicBrainzClient:
    """Test suite for MusicBrainzClient."""

    @pytest.mark.asyncio
    async def test_from_config(self, musicbrainz_config, temp_cache_dir):
        """Test creating client from configuration."""
        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            assert client.base_url == "https://musicbrainz.org/ws/2"
            assert client.rate_limiter is not None
            assert client.concurrency_limiter is not None
            assert "User-Agent" in client.auth_headers
            assert "fuzzbin" in client.auth_headers["User-Agent"]
            assert "https://github.com/asotbz/Fuzzbin" in client.auth_headers["User-Agent"]
            assert "Accept" in client.auth_headers
            assert client.auth_headers["Accept"] == "application/json"

    @pytest.mark.asyncio
    async def test_from_config_none(self, temp_cache_dir):
        """Test creating client with no config (MusicBrainz requires no auth)."""
        async with MusicBrainzClient.from_config(config_dir=temp_cache_dir) as client:
            assert client.base_url == "https://musicbrainz.org/ws/2"
            assert "User-Agent" in client.auth_headers

    @pytest.mark.asyncio
    async def test_user_agent_format(self, musicbrainz_config, temp_cache_dir):
        """Test that User-Agent header follows required format."""
        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            user_agent = client.auth_headers["User-Agent"]
            assert user_agent.startswith("fuzzbin/")
            assert "(https://github.com/asotbz/Fuzzbin)" in user_agent


class TestBuildQuery:
    """Test suite for the _build_query helper method."""

    def test_build_query_artist_and_recording(self):
        """Test building query with artist and recording."""
        query = MusicBrainzClient._build_query(
            artist="Nirvana", recording="Smells Like Teen Spirit"
        )
        assert 'recording:"Smells Like Teen Spirit"' in query
        assert 'artist:"Nirvana"' in query
        assert " AND " in query

    def test_build_query_isrc_only(self):
        """Test building query with ISRC only."""
        query = MusicBrainzClient._build_query(isrc="USGF19942501")
        assert query == "isrc:USGF19942501"

    def test_build_query_recording_only(self):
        """Test building query with recording only."""
        query = MusicBrainzClient._build_query(recording="Smells Like Teen Spirit")
        assert query == 'recording:"Smells Like Teen Spirit"'

    def test_build_query_artist_only(self):
        """Test building query with artist only."""
        query = MusicBrainzClient._build_query(artist="Nirvana")
        assert query == 'artist:"Nirvana"'

    def test_build_query_with_rgid(self):
        """Test building query with release group ID."""
        query = MusicBrainzClient._build_query(
            recording="Smells Like Teen Spirit",
            rgid="1b022e01-4da6-387b-8658-8678046e4cef",
        )
        assert 'recording:"Smells Like Teen Spirit"' in query
        assert "rgid:1b022e01-4da6-387b-8658-8678046e4cef" in query
        assert " AND " in query

    def test_build_query_escapes_special_characters(self):
        """Test that special Lucene characters are escaped."""
        query = MusicBrainzClient._build_query(
            artist="AC/DC", recording="Back in Black (Remastered)"
        )
        # Forward slash and parentheses should be escaped
        assert 'artist:"AC\\/DC"' in query
        assert 'recording:"Back in Black \\(Remastered\\)"' in query

    def test_build_query_escapes_quotes(self):
        """Test that quotes in values are escaped."""
        query = MusicBrainzClient._build_query(recording='She Said "Hello"')
        assert 'recording:"She Said \\"Hello\\""' in query

    def test_build_query_empty_raises_error(self):
        """Test that empty query raises ValueError."""
        with pytest.raises(ValueError, match="At least one search criterion"):
            MusicBrainzClient._build_query()

    def test_build_query_all_params(self):
        """Test building query with all parameters."""
        query = MusicBrainzClient._build_query(
            artist="Nirvana",
            recording="Smells Like Teen Spirit",
            isrc="USGF19942501",
            rgid="1b022e01-4da6-387b-8658-8678046e4cef",
        )
        assert "isrc:USGF19942501" in query
        assert 'recording:"Smells Like Teen Spirit"' in query
        assert 'artist:"Nirvana"' in query
        assert "rgid:1b022e01-4da6-387b-8658-8678046e4cef" in query
        # All joined with AND
        assert query.count(" AND ") == 3


class TestSearchRecordings:
    """Test suite for search_recordings method."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_recordings_by_artist_and_title(
        self, musicbrainz_config, search_response, temp_cache_dir
    ):
        """Test searching for recordings by artist and title."""
        route = respx.get("https://musicbrainz.org/ws/2/recording").mock(
            return_value=httpx.Response(200, json=search_response)
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            result = await client.search_recordings(
                artist="Nirvana", recording="Smells Like Teen Spirit"
            )

            # Verify response structure
            assert result.count == 13
            assert result.offset == 0
            assert len(result.recordings) > 0

            # Verify first recording
            first_recording = result.recordings[0]
            assert first_recording.id == "a227a9bd-ad64-47c9-bd5e-05a0222eba09"
            assert first_recording.title == "Smells Like Teen Spirit"
            assert first_recording.score == 100
            assert first_recording.video is True
            assert first_recording.artist_name == "Nirvana"

            # Verify request parameters
            request_url = str(route.calls.last.request.url)
            assert "fmt=json" in request_url
            assert "query=" in request_url
            assert "inc=" in request_url
            assert "limit=25" in request_url
            assert "offset=0" in request_url

            # Verify User-Agent header
            assert "User-Agent" in route.calls.last.request.headers
            assert "fuzzbin" in route.calls.last.request.headers["User-Agent"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_recordings_by_isrc(
        self, musicbrainz_config, isrc_search_response, temp_cache_dir
    ):
        """Test searching for recordings by ISRC."""
        route = respx.get("https://musicbrainz.org/ws/2/recording").mock(
            return_value=httpx.Response(200, json=isrc_search_response)
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            result = await client.search_recordings(isrc="USGF19942501")

            # Verify response - count from example file
            assert result.count == 1
            assert len(result.recordings) == 1

            # Verify request contains ISRC query
            request_url = str(route.calls.last.request.url)
            assert "isrc%3AUSGF19942501" in request_url or "isrc:USGF19942501" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_recordings_with_pagination(
        self, musicbrainz_config, search_response, temp_cache_dir
    ):
        """Test search with custom pagination parameters."""
        route = respx.get("https://musicbrainz.org/ws/2/recording").mock(
            return_value=httpx.Response(200, json=search_response)
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            _result = await client.search_recordings(
                artist="Nirvana",
                recording="Smells Like Teen Spirit",
                limit=10,
                offset=50,
            )

            # Verify pagination parameters in request
            request_url = str(route.calls.last.request.url)
            assert "limit=10" in request_url
            assert "offset=50" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_recordings_limit_capped_at_100(
        self, musicbrainz_config, search_response, temp_cache_dir
    ):
        """Test that limit is capped at 100 (API maximum)."""
        route = respx.get("https://musicbrainz.org/ws/2/recording").mock(
            return_value=httpx.Response(200, json=search_response)
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            await client.search_recordings(artist="Nirvana", limit=500)

            # Verify limit is capped
            request_url = str(route.calls.last.request.url)
            assert "limit=100" in request_url

    @pytest.mark.asyncio
    async def test_search_recordings_no_criteria_raises_error(
        self, musicbrainz_config, temp_cache_dir
    ):
        """Test that search with no criteria raises ValueError."""
        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            with pytest.raises(ValueError, match="At least one search criterion"):
                await client.search_recordings()


class TestLookupByISRC:
    """Test suite for lookup_by_isrc method."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_lookup_by_isrc(self, musicbrainz_config, isrc_response, temp_cache_dir):
        """Test ISRC lookup."""
        route = respx.get("https://musicbrainz.org/ws/2/isrc/USGF19942501").mock(
            return_value=httpx.Response(200, json=isrc_response)
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            result = await client.lookup_by_isrc("USGF19942501")

            # Verify response
            assert len(result.recordings) > 0
            first_recording = result.recordings[0]
            assert first_recording.title == "Smells Like Teen Spirit"
            assert first_recording.artist_name == "Nirvana"

            # Verify request
            assert route.calls.last.request.url.path == "/ws/2/isrc/USGF19942501"
            request_url = str(route.calls.last.request.url)
            assert "fmt=json" in request_url
            assert "inc=" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_lookup_by_isrc_not_found(self, musicbrainz_config, temp_cache_dir):
        """Test ISRC lookup returns 404."""
        respx.get("https://musicbrainz.org/ws/2/isrc/INVALID123456").mock(
            return_value=httpx.Response(404, json={"error": "Not Found"})
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            with pytest.raises(RecordingNotFoundError) as exc_info:
                await client.lookup_by_isrc("INVALID123456")

            assert exc_info.value.isrc == "INVALID123456"


class TestGetRecording:
    """Test suite for get_recording method."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_recording(self, musicbrainz_config, recording_response, temp_cache_dir):
        """Test getting recording by MBID."""
        mbid = "5fb524f1-8cc8-4c04-a921-e34c0a911ea7"
        route = respx.get(f"https://musicbrainz.org/ws/2/recording/{mbid}").mock(
            return_value=httpx.Response(200, json=recording_response)
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            result = await client.get_recording(mbid)

            # Verify response
            assert result.title == "Smells Like Teen Spirit"
            assert result.tags is not None
            assert len(result.tags) > 0
            # Verify grunge tag exists
            grunge_tags = [t for t in result.tags if t.name == "grunge"]
            assert len(grunge_tags) > 0

            # Verify request
            assert route.calls.last.request.url.path == f"/ws/2/recording/{mbid}"
            request_url = str(route.calls.last.request.url)
            assert "fmt=json" in request_url
            assert "inc=" in request_url

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_recording_not_found(self, musicbrainz_config, temp_cache_dir):
        """Test getting recording that doesn't exist."""
        mbid = "00000000-0000-0000-0000-000000000000"
        respx.get(f"https://musicbrainz.org/ws/2/recording/{mbid}").mock(
            return_value=httpx.Response(404, json={"error": "Not Found"})
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            with pytest.raises(RecordingNotFoundError) as exc_info:
                await client.get_recording(mbid)

            assert exc_info.value.mbid == mbid

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_recording_custom_includes(
        self, musicbrainz_config, recording_response, temp_cache_dir
    ):
        """Test getting recording with custom includes parameter."""
        # Use a different MBID to ensure this test doesn't share cache with others
        mbid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        route = respx.get(f"https://musicbrainz.org/ws/2/recording/{mbid}").mock(
            return_value=httpx.Response(200, json=recording_response)
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            await client.get_recording(mbid, includes="tags+isrcs")

            # Verify custom includes in request
            request_url = str(route.calls.last.request.url)
            assert "inc=tags%2Bisrcs" in request_url or "inc=tags+isrcs" in request_url


class TestRecordingModel:
    """Test suite for MusicBrainzRecording model properties."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_recording_duration_seconds(
        self, musicbrainz_config, search_response, temp_cache_dir
    ):
        """Test duration_seconds property."""
        respx.get("https://musicbrainz.org/ws/2/recording").mock(
            return_value=httpx.Response(200, json=search_response)
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            result = await client.search_recordings(
                artist="Nirvana", recording="Smells Like Teen Spirit"
            )

            # First recording has length=180000 (milliseconds)
            first_recording = result.recordings[0]
            assert first_recording.length == 180000
            assert first_recording.duration_seconds == 180.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_recording_artist_name(self, musicbrainz_config, search_response, temp_cache_dir):
        """Test artist_name property."""
        respx.get("https://musicbrainz.org/ws/2/recording").mock(
            return_value=httpx.Response(200, json=search_response)
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            result = await client.search_recordings(
                artist="Nirvana", recording="Smells Like Teen Spirit"
            )

            first_recording = result.recordings[0]
            assert first_recording.artist_name == "Nirvana"


class TestErrorHandling:
    """Test suite for error handling."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_http_error_propagated(self, musicbrainz_config, temp_cache_dir):
        """Test that HTTP errors are propagated."""
        respx.get("https://musicbrainz.org/ws/2/recording").mock(
            return_value=httpx.Response(500, json={"error": "Internal Server Error"})
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.search_recordings(artist="Nirvana")

    @pytest.mark.asyncio
    @respx.mock
    async def test_rate_limit_response(self, musicbrainz_config, temp_cache_dir):
        """Test handling of rate limit response."""
        respx.get("https://musicbrainz.org/ws/2/recording").mock(
            return_value=httpx.Response(
                503,
                json={"error": "Rate limit exceeded"},
                headers={"Retry-After": "5"},
            )
        )

        async with MusicBrainzClient.from_config(
            config=musicbrainz_config, config_dir=temp_cache_dir
        ) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.search_recordings(artist="Nirvana")
