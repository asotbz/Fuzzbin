"""Discogs API client for music release database access."""

import os
from typing import Any, Dict, Optional

import httpx
import structlog

from .base_client import RateLimitedAPIClient
from ..common.config import APIClientConfig

logger = structlog.get_logger(__name__)


class DiscogsClient(RateLimitedAPIClient):
    """
    Client for Discogs API.

    Discogs provides comprehensive music release data including artist information,
    releases, masters, labels, and detailed track listings.

    API Rate Limit: 60 requests per minute (authenticated)

    Features:
    - Search for masters and releases by artist and track
    - Get detailed artist release listings
    - Fetch master release details
    - Fetch specific release details
    - Automatic rate limit adjustment based on API response headers
    - Rate limiting and concurrency control

    Authentication:
    - Requires API key and secret via DISCOGS_API_KEY and DISCOGS_API_SECRET
      environment variables or config
    - Environment variables take precedence over config
    - User-Agent header is automatically set to fuzzbin/{version}

    Example:
        >>> import asyncio
        >>> from fuzzbin.api.discogs_client import DiscogsClient
        >>> from fuzzbin.common.config import APIClientConfig, RateLimitConfig
        >>>
        >>> async def main():
        ...     config = APIClientConfig(
        ...         name="discogs",
        ...         base_url="https://api.discogs.com",
        ...         rate_limit=RateLimitConfig(requests_per_minute=60)
        ...     )
        ...
        ...     async with DiscogsClient.from_config(config) as client:
        ...         # Search for releases
        ...         results = await client.search("nirvana", "smells like teen spirit")
        ...
        ...         # Get master details
        ...         master = await client.get_master(13814)
        ...
        ...         # Get release details
        ...         release = await client.get_release(25823602)
        ...
        ...         # Get artist releases
        ...         releases = await client.get_artist_releases(125246)
        >>>
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        *args: Any,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize the Discogs API client.

        Args:
            *args: Positional arguments for RateLimitedAPIClient
            api_key: Discogs API key (optional, can use DISCOGS_API_KEY env var)
            api_secret: Discogs API secret (optional, can use DISCOGS_API_SECRET env var)
            **kwargs: Keyword arguments for RateLimitedAPIClient
        """
        # Get API credentials from env variables or parameters
        # Environment variables take precedence
        key = os.environ.get("DISCOGS_API_KEY") or api_key
        secret = os.environ.get("DISCOGS_API_SECRET") or api_secret

        # Add Discogs-specific auth headers
        auth_headers = kwargs.get("auth_headers", {})

        # Set User-Agent (required by Discogs API)
        # Get version from package
        try:
            from importlib.metadata import version as get_version

            fuzzbin_version = get_version("fuzzbin")
        except Exception:
            fuzzbin_version = "0.1.0"  # Fallback version

        auth_headers["User-Agent"] = f"fuzzbin/{fuzzbin_version} +https://github.com/asotbz/Fuzzbin"

        # Set Authorization header if credentials provided
        if key and secret:
            auth_headers["Authorization"] = f"Discogs key={key}, secret={secret}"

        kwargs["auth_headers"] = auth_headers

        super().__init__(*args, **kwargs)

        self.logger.info(
            "discogs_client_initialized",
            base_url=self.base_url,
            has_credentials=bool(key and secret),
            user_agent=auth_headers["User-Agent"],
        )

    # Default configuration constants
    DEFAULT_BASE_URL = "https://api.discogs.com"
    DEFAULT_REQUESTS_PER_MINUTE = 60
    DEFAULT_BURST_SIZE = 10
    DEFAULT_MAX_CONCURRENT = 5

    @classmethod
    def from_config(cls, config: APIClientConfig) -> "DiscogsClient":
        """
        Create Discogs client from APIClientConfig.

        Uses hardcoded defaults for base URL, rate limiting, and concurrency.
        Only authentication can be configured via the config object.

        Args:
            config: API client configuration (only auth field is used)

        Returns:
            Configured DiscogsClient instance

        Example:
            >>> from fuzzbin.common.config import APIClientConfig
            >>> config = APIClientConfig(auth={"api_key": "KEY", "api_secret": "SECRET"})
            >>> client = DiscogsClient.from_config(config)
        """
        # Extract API credentials from config.auth if present
        api_key = None
        api_secret = None
        if config.auth:
            api_key = config.auth.get("api_key")
            api_secret = config.auth.get("api_secret")

        # Create rate limiter with hardcoded defaults
        from ..common.rate_limiter import RateLimiter

        rate_limiter = RateLimiter(
            requests_per_minute=cls.DEFAULT_REQUESTS_PER_MINUTE,
            burst_size=cls.DEFAULT_BURST_SIZE,
        )

        # Create concurrency limiter with hardcoded defaults
        from ..common.concurrency_limiter import ConcurrencyLimiter

        concurrency_limiter = ConcurrencyLimiter(
            max_concurrent=cls.DEFAULT_MAX_CONCURRENT
        )

        # Use default HTTP config
        from ..common.config import HTTPConfig
        http_config = HTTPConfig()

        return cls(
            http_config=http_config,
            base_url=cls.DEFAULT_BASE_URL,
            rate_limiter=rate_limiter,
            concurrency_limiter=concurrency_limiter,
            api_key=api_key,
            api_secret=api_secret,
        )

    async def _apply_limiters_and_auth(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Apply limiters/auth and track Discogs rate limit headers.

        This method wraps the parent's method to monitor and log
        Discogs-specific rate limit headers, and dynamically adjust the
        rate limiter if needed.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments

        Returns:
            HTTP response
        """
        response = await super()._apply_limiters_and_auth(method, url, **kwargs)

        # Extract and log Discogs rate limit headers
        rate_limit = response.headers.get("X-Discogs-Ratelimit")
        rate_limit_used = response.headers.get("X-Discogs-Ratelimit-Used")
        rate_limit_remaining = response.headers.get("X-Discogs-Ratelimit-Remaining")

        if rate_limit:
            self.logger.debug(
                "discogs_rate_limit_headers",
                total=rate_limit,
                used=rate_limit_used,
                remaining=rate_limit_remaining,
            )

            # Dynamically adjust rate limiter if the API-reported limit differs
            # from our configured limit
            if self.rate_limiter:
                try:
                    api_limit = int(rate_limit)
                    # Calculate current limit from rate (rate is in requests per second)
                    current_limit = int(self.rate_limiter.rate * 60)
                    # Only adjust if significantly different (more than 10% variance)
                    if current_limit and abs(api_limit - current_limit) > (current_limit * 0.1):
                        self.logger.info(
                            "discogs_rate_limit_adjusted",
                            old_limit=current_limit,
                            new_limit=api_limit,
                        )
                        # Update the rate limiter's rate (convert to requests per second)
                        self.rate_limiter.rate = api_limit / 60.0
                except (ValueError, TypeError):
                    pass  # Ignore if header value is not a valid integer

        return response

    async def search(
        self,
        artist: str,
        track: str,
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        """
        Search for master releases by artist and track title.

        Always searches for type=master,format=album as per requirements.

        Args:
            artist: Artist name to search for
            track: Track title to search for
            page: Page number for pagination (default: 1)
            per_page: Results per page (default: 50, max: 100)

        Returns:
            Dict containing search results with pagination metadata:
            - pagination: Object with page, pages, per_page, items, urls
            - results: List of master release objects with id, title, year, etc.

        Raises:
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> results = await client.search("nirvana", "smells like teen spirit")
            >>> for result in results['results']:
            ...     print(f"{result['title']} ({result['year']})")
            ...     if result['type'] == 'master':
            ...         print(f"  Master ID: {result['id']}")
        """
        params = {
            "type": "master",
            "format": "album",
            "artist": artist,
            "track": track,
            "page": page,
            "per_page": per_page,
        }

        self.logger.info(
            "discogs_search",
            artist=artist,
            track=track,
            page=page,
            per_page=per_page,
        )

        response = await self.get("/database/search", params=params)
        response.raise_for_status()
        return response.json()

    async def get_artist_releases(
        self,
        artist_id: int,
        page: int = 1,
        per_page: int = 50,
        sort: str = "year",
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """
        Get all releases by a specific artist.

        Args:
            artist_id: Discogs artist ID
            page: Page number for pagination (default: 1)
            per_page: Results per page (default: 50, max: 100)
            sort: Sort field - 'year', 'title', 'format' (default: 'year')
            sort_order: Sort order - 'asc' or 'desc' (default: 'asc')

        Returns:
            Dict containing artist releases with pagination metadata:
            - pagination: Object with page, pages, per_page, items, urls
            - releases: List of release objects with id, title, year, role, type, etc.

        Raises:
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> releases = await client.get_artist_releases(125246)
            >>> print(f"Total: {releases['pagination']['items']} releases")
            >>> for release in releases['releases']:
            ...     print(f"{release['title']} ({release['year']}) - {release['type']}")
        """
        params = {
            "page": page,
            "per_page": per_page,
            "sort": sort,
            "sort_order": sort_order,
        }

        self.logger.info(
            "discogs_get_artist_releases",
            artist_id=artist_id,
            page=page,
            per_page=per_page,
        )

        response = await self.get(f"/artists/{artist_id}/releases", params=params)
        response.raise_for_status()
        return response.json()

    async def get_master(self, master_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a master release.

        Args:
            master_id: Discogs master release ID

        Returns:
            Dict containing master release details:
            - id: Master ID
            - title: Album title
            - artists: List of artist objects
            - year: Release year
            - genres: List of genres
            - styles: List of styles
            - tracklist: List of track objects
            - images: List of image URLs
            - videos: List of video objects (YouTube, etc.)
            - main_release: ID of the main release version
            - versions_url: URL to get all versions

        Raises:
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> master = await client.get_master(13814)
            >>> print(f"{master['title']} by {master['artists'][0]['name']}")
            >>> print(f"Released: {master['year']}")
            >>> print(f"Genres: {', '.join(master['genres'])}")
            >>> for track in master['tracklist']:
            ...     print(f"{track['position']}. {track['title']} - {track['duration']}")
        """
        self.logger.info("discogs_get_master", master_id=master_id)

        response = await self.get(f"/masters/{master_id}")
        response.raise_for_status()
        return response.json()

    async def get_release(self, release_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a specific release.

        Args:
            release_id: Discogs release ID

        Returns:
            Dict containing release details:
            - id: Release ID
            - title: Album title
            - artists: List of artist objects
            - year: Release year
            - country: Country of release
            - labels: List of label objects
            - formats: List of format objects (Vinyl, CD, etc.)
            - genres: List of genres
            - styles: List of styles
            - tracklist: List of track objects
            - images: List of image URLs
            - videos: List of video objects
            - master_id: ID of the master release
            - identifiers: List of barcode/matrix identifiers
            - companies: List of company credits

        Raises:
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> release = await client.get_release(25823602)
            >>> print(f"{release['title']} ({release['country']}, {release['year']})")
            >>> print(f"Format: {release['formats'][0]['name']}")
            >>> print(f"Label: {release['labels'][0]['name']}")
            >>> for identifier in release['identifiers']:
            ...     print(f"{identifier['type']}: {identifier['value']}")
        """
        self.logger.info("discogs_get_release", release_id=release_id)

        response = await self.get(f"/releases/{release_id}")
        response.raise_for_status()
        return response.json()
