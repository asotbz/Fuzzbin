"""MusicBrainz API client for music metadata lookup."""

import re
from pathlib import Path
from typing import Any, Optional

import structlog

from .base_client import RateLimitedAPIClient
from ..common.config import APIClientConfig, CacheConfig
from ..parsers.musicbrainz_models import (
    MusicBrainzISRCResponse,
    MusicBrainzRecording,
    MusicBrainzRecordingSearchResponse,
    MusicBrainzRelease,
    RecordingNotFoundError,
)
from ..parsers.musicbrainz_parser import MusicBrainzParser

logger = structlog.get_logger(__name__)


def _get_version() -> str:
    """Get Fuzzbin version for User-Agent header."""
    try:
        from importlib.metadata import version as get_version

        return get_version("fuzzbin")
    except Exception:
        return "0.1.0"


class MusicBrainzClient(RateLimitedAPIClient):
    """
    Client for MusicBrainz API.

    MusicBrainz is an open music encyclopedia that provides structured metadata
    about recordings, releases, artists, and works.

    API Rate Limit: 1 request per second (enforced by User-Agent requirement)
    No API credentials required.

    Features:
    - Recording search by artist name, track title, and/or ISRC
    - ISRC-based recording lookup
    - Recording lookup by MBID
    - Lucene query syntax support for advanced searches
    - Automatic pagination support
    - Rate limiting and concurrency control

    Authentication:
    - No API key required
    - Must include User-Agent header with application info

    Example:
        >>> import asyncio
        >>> from fuzzbin.api.musicbrainz_client import MusicBrainzClient
        >>> from fuzzbin.common.config import APIClientConfig
        >>>
        >>> async def main():
        ...     config = APIClientConfig(name="musicbrainz")
        ...
        ...     async with MusicBrainzClient.from_config(config) as client:
        ...         # Search for recordings by artist and title
        ...         results = await client.search_recordings(
        ...             artist="Nirvana",
        ...             recording="Smells Like Teen Spirit"
        ...         )
        ...
        ...         # Search by ISRC
        ...         results = await client.search_recordings(isrc="USGF19942501")
        ...
        ...         # Get recording details by MBID
        ...         recording = await client.get_recording("5fb524f1-8cc8-4c04-a921-e34c0a911ea7")
        ...
        ...         # Direct ISRC lookup
        ...         isrc_result = await client.lookup_by_isrc("USGF19942501")
        >>>
        >>> asyncio.run(main())
    """

    # Default configuration constants
    DEFAULT_BASE_URL = "https://musicbrainz.org/ws/2"
    DEFAULT_REQUESTS_PER_MINUTE = 60  # 1 request per second
    DEFAULT_BURST_SIZE = 1  # No bursting allowed
    DEFAULT_MAX_CONCURRENT = 1  # One request at a time
    DEFAULT_INCLUDES = "artist-credits+releases+tags+release-groups+labels"  # Sensible defaults for recording queries
    # ISRC endpoint only supports a subset of includes (no release-groups or labels)
    ISRC_INCLUDES = "tags"
    CACHE_DATABASE = "musicbrainz_cache.sqlite"

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ):
        """
        Initialize the MusicBrainz API client.

        Args:
            *args: Positional arguments for RateLimitedAPIClient
            **kwargs: Keyword arguments for RateLimitedAPIClient
        """
        super().__init__(*args, **kwargs)

        self.logger.info(
            "musicbrainz_client_initialized",
            base_url=self.base_url,
        )

    @classmethod
    def from_config(
        cls, config: Optional[APIClientConfig] = None, config_dir: Optional[Path] = None
    ) -> "MusicBrainzClient":
        """
        Create MusicBrainz client from APIClientConfig.

        Uses hardcoded defaults for base URL, rate limiting, and concurrency.
        No authentication is required for MusicBrainz API.

        Args:
            config: API client configuration (not used, MusicBrainz requires no config)
            config_dir: Optional directory for cache storage

        Returns:
            Configured MusicBrainzClient instance

        Example:
            >>> from fuzzbin.common.config import APIClientConfig
            >>> config = APIClientConfig(name="musicbrainz")
            >>> client = MusicBrainzClient.from_config(config)
        """
        # Create rate limiter with hardcoded defaults (1 req/sec)
        from ..common.rate_limiter import RateLimiter

        rate_limiter = RateLimiter(
            requests_per_minute=cls.DEFAULT_REQUESTS_PER_MINUTE,
            burst_size=cls.DEFAULT_BURST_SIZE,
        )

        # Create concurrency limiter with hardcoded defaults
        from ..common.concurrency_limiter import ConcurrencyLimiter

        concurrency_limiter = ConcurrencyLimiter(max_concurrent=cls.DEFAULT_MAX_CONCURRENT)

        # Use default HTTP config
        from ..common.config import HTTPConfig

        http_config = HTTPConfig()

        # Set required User-Agent header
        version = _get_version()
        auth_headers = {
            "User-Agent": f"fuzzbin/{version} (https://github.com/asotbz/Fuzzbin)",
            "Accept": "application/json",
        }

        # Configure cache with dedicated database
        cache_config = CacheConfig(
            enabled=True,
            database=cls.CACHE_DATABASE,
            ttl_seconds=86400,  # 24 hours default
        )

        return cls(
            http_config=http_config,
            base_url=cls.DEFAULT_BASE_URL,
            rate_limiter=rate_limiter,
            concurrency_limiter=concurrency_limiter,
            auth_headers=auth_headers,
            cache_config=cache_config,
            config_dir=config_dir,
        )

    @staticmethod
    def _escape_lucene_value(value: str) -> str:
        """
        Escape special characters in a Lucene query value.

        MusicBrainz uses Lucene syntax for search queries. Special characters
        that have meaning in Lucene must be escaped.

        Args:
            value: The value to escape

        Returns:
            Escaped value safe for use in Lucene queries
        """
        # Lucene special characters that need escaping
        # + - && || ! ( ) { } [ ] ^ " ~ * ? : \ /
        special_chars = r'([+\-&|!(){}[\]^"~*?:\\/])'
        return re.sub(special_chars, r"\\\1", value)

    @classmethod
    def _build_query(
        cls,
        artist: Optional[str] = None,
        recording: Optional[str] = None,
        isrc: Optional[str] = None,
        rgid: Optional[str] = None,
    ) -> str:
        """
        Build a Lucene-style query string for MusicBrainz search.

        Constructs a properly escaped query using MusicBrainz's supported
        Lucene query fields. When searching by artist+recording, automatically
        excludes live recordings to prefer studio versions.

        Args:
            artist: Artist name to search for
            recording: Recording/track title to search for
            isrc: ISRC code to search for
            rgid: Release group MBID to filter by

        Returns:
            Lucene query string

        Raises:
            ValueError: If no search criteria provided

        Example:
            >>> MusicBrainzClient._build_query(artist="Nirvana", recording="Smells Like Teen Spirit")
            'recording:"Smells Like Teen Spirit" AND artist:"Nirvana" AND NOT comment:(live OR concert OR "live at")'

            >>> MusicBrainzClient._build_query(isrc="USGF19942501")
            'isrc:USGF19942501'
        """
        parts = []

        if isrc:
            # ISRC doesn't need quoting or escaping (format: CCXXXYYNNNNN)
            parts.append(f"isrc:{isrc}")

        if recording:
            escaped = cls._escape_lucene_value(recording)
            parts.append(f'recording:"{escaped}"')

        if artist:
            escaped = cls._escape_lucene_value(artist)
            parts.append(f'artist:"{escaped}"')

        if rgid:
            # MBID doesn't need escaping (UUID format)
            parts.append(f"rgid:{rgid}")

        if not parts:
            raise ValueError("At least one search criterion must be provided")

        query = " AND ".join(parts)

        # When searching by artist+recording (not ISRC), exclude live recordings
        # to prefer studio versions. ISRC searches are already specific enough.
        if (artist or recording) and not isrc:
            query += ' AND NOT comment:(live OR concert OR "live at")'

        return query

    async def search_recordings(
        self,
        artist: Optional[str] = None,
        recording: Optional[str] = None,
        isrc: Optional[str] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> MusicBrainzRecordingSearchResponse:
        """
        Search for recordings by artist, title, and/or ISRC.

        Args:
            artist: Artist name to search for
            recording: Recording/track title to search for
            isrc: ISRC code to search for
            limit: Maximum number of results to return (default: 25, max: 100)
            offset: Number of results to skip for pagination (default: 0)

        Returns:
            MusicBrainzRecordingSearchResponse containing:
            - count: Total number of matching recordings
            - offset: Current offset
            - recordings: List of MusicBrainzRecording objects

        Raises:
            ValueError: If no search criteria provided
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> results = await client.search_recordings(
            ...     artist="Nirvana",
            ...     recording="Smells Like Teen Spirit",
            ...     limit=10
            ... )
            >>> print(f"Found {results.count} recordings")
            >>> for rec in results.recordings:
            ...     print(f"{rec.title} by {rec.artist_name}")
        """
        query = self._build_query(artist=artist, recording=recording, isrc=isrc)

        params = {
            "query": query,
            "fmt": "json",
            "limit": min(limit, 100),  # API max is 100
            "offset": offset,
            "inc": self.DEFAULT_INCLUDES,
        }

        self.logger.info(
            "musicbrainz_search_recordings",
            query=query,
            limit=limit,
            offset=offset,
        )

        response = await self.get("/recording", params=params)
        response.raise_for_status()
        return MusicBrainzParser.parse_recording_search_results(response.json())

    async def lookup_by_isrc(self, isrc: str) -> MusicBrainzISRCResponse:
        """
        Look up recordings by ISRC code using the dedicated ISRC endpoint.

        This is more direct than searching by ISRC and returns all recordings
        associated with the given ISRC code.

        Args:
            isrc: ISRC code (format: CCXXXYYNNNNN, e.g., USGF19942501)

        Returns:
            MusicBrainzISRCResponse containing:
            - isrc: The ISRC code
            - recordings: List of recordings with this ISRC

        Raises:
            RecordingNotFoundError: If no recordings found for the ISRC
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> result = await client.lookup_by_isrc("USGF19942501")
            >>> print(f"Found {len(result.recordings)} recordings for ISRC")
        """
        params = {
            "fmt": "json",
            "inc": self.ISRC_INCLUDES,
        }

        self.logger.info(
            "musicbrainz_lookup_by_isrc",
            isrc=isrc,
        )

        response = await self.get(f"/isrc/{isrc}", params=params)

        if response.status_code == 404:
            raise RecordingNotFoundError(isrc=isrc)

        response.raise_for_status()
        return MusicBrainzParser.parse_isrc_response(response.json())

    async def get_recording(
        self,
        mbid: str,
        includes: Optional[str] = None,
    ) -> MusicBrainzRecording:
        """
        Get detailed information about a specific recording by MBID.

        Args:
            mbid: MusicBrainz recording ID (UUID format)
            includes: Optional override for inc parameter (default: artist-credits+releases+tags)

        Returns:
            MusicBrainzRecording with full details

        Raises:
            RecordingNotFoundError: If recording not found
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> recording = await client.get_recording("5fb524f1-8cc8-4c04-a921-e34c0a911ea7")
            >>> print(f"{recording.title} - {recording.artist_name}")
            >>> print(f"Duration: {recording.duration_seconds}s")
        """
        params = {
            "fmt": "json",
            "inc": includes or self.DEFAULT_INCLUDES,
        }

        self.logger.info(
            "musicbrainz_get_recording",
            mbid=mbid,
        )

        response = await self.get(f"/recording/{mbid}", params=params)

        if response.status_code == 404:
            raise RecordingNotFoundError(mbid=mbid)

        response.raise_for_status()
        return MusicBrainzParser.parse_recording(response.json())

    async def get_release(
        self,
        mbid: str,
        includes: str = "labels",
    ) -> MusicBrainzRelease:
        """
        Get detailed information about a specific release by MBID.

        Args:
            mbid: MusicBrainz release ID (UUID format)
            includes: Include parameters (default: labels)

        Returns:
            MusicBrainzRelease with full details including label info

        Raises:
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> release = await client.get_release("ff565cd7-acf8-4dc0-9603-72d1b7ae284b")
            >>> if release.label_info:
            ...     print(f"Label: {release.label_info[0].label.name}")
        """
        params = {
            "fmt": "json",
            "inc": includes,
        }

        self.logger.info(
            "musicbrainz_get_release",
            mbid=mbid,
        )

        response = await self.get(f"/release/{mbid}", params=params)
        response.raise_for_status()
        return MusicBrainzParser.parse_release(response.json())
