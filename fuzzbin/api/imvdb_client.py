"""IMVDb API client for music video database access."""

import os
from typing import Any, Dict, Optional

import httpx
import structlog

from .base_client import RateLimitedAPIClient
from ..common.config import APIClientConfig
from ..common.string_utils import normalize_for_matching
from ..parsers.imvdb_models import (
    IMVDbEntity,
    IMVDbEntitySearchResponse,
    IMVDbVideo,
    IMVDbVideoSearchResult,
)
from ..parsers.imvdb_parser import IMVDbParser

logger = structlog.get_logger(__name__)


class IMVDbClient(RateLimitedAPIClient):
    """
    Client for IMVDb (Internet Music Video Database) API.

    IMVDb provides comprehensive music video data including artist information,
    video metadata, credits, sources, and featured artists.

    API Rate Limit: 1000 requests per minute

    Features:
    - Video search by artist and track title
    - Entity (artist/director/etc.) search and details
    - Video metadata with credits, sources, and featured artists
    - Automatic pagination support
    - Rate limiting and concurrency control

    Authentication:
    - Requires API key via IMVDB_APP_KEY environment variable or config
    - Environment variable takes precedence over config

    Example:
        >>> import asyncio
        >>> from fuzzbin.api.imvdb_client import IMVDbClient
        >>> from fuzzbin.common.config import APIClientConfig, RateLimitConfig
        >>>
        >>> async def main():
        ...     config = APIClientConfig(
        ...         name="imvdb",
        ...         base_url="https://imvdb.com/api/v1",
        ...         rate_limit=RateLimitConfig(rate=1000, period=60)
        ...     )
        ...
        ...     async with IMVDbClient.from_config(config) as client:
        ...         # Search for videos
        ...         results = await client.search_videos("Robin Thicke", "Blurred Lines")
        ...
        ...         # Get video details
        ...         video = await client.get_video(121779770452)
        ...
        ...         # Search for entities
        ...         entities = await client.search_entities("Robin Thicke")
        ...
        ...         # Get entity details
        ...         entity = await client.get_entity(838673)
        >>>
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        *args: Any,
        app_key: Optional[str] = None,
        **kwargs: Any,
    ):
        """
        Initialize the IMVDb API client.

        Args:
            *args: Positional arguments for RateLimitedAPIClient
            app_key: IMVDb API key (optional, can use IMVDB_APP_KEY env var)
            **kwargs: Keyword arguments for RateLimitedAPIClient
        """
        # Get API key from env variable or parameter
        # Environment variable takes precedence
        api_key = os.environ.get("IMVDB_APP_KEY") or app_key

        # Add IMVDb-specific auth header
        auth_headers = kwargs.get("auth_headers", {})
        if api_key:
            auth_headers["IMVDB-APP-KEY"] = api_key
        kwargs["auth_headers"] = auth_headers

        super().__init__(*args, **kwargs)

        self.logger.info(
            "imvdb_client_initialized",
            base_url=self.base_url,
            has_api_key=bool(api_key),
        )

    @classmethod
    def from_config(cls, config: APIClientConfig) -> "IMVDbClient":
        """
        Create IMVDb client from APIClientConfig.

        Args:
            config: API client configuration

        Returns:
            Configured IMVDbClient instance

        Example:
            >>> from fuzzbin.common.config import APIClientConfig
            >>> config = APIClientConfig(
            ...     name="imvdb",
            ...     base_url="https://imvdb.com/api/v1"
            ... )
            >>> client = IMVDbClient.from_config(config)
        """
        # Extract API key from config.custom if present
        app_key = None
        if config.custom:
            app_key = config.custom.get("app_key")

        # Create rate limiter if configured
        rate_limiter = None
        if config.rate_limit and config.rate_limit.enabled:
            from ..common.rate_limiter import RateLimiter

            rate_limiter = RateLimiter(
                requests_per_minute=config.rate_limit.requests_per_minute,
                requests_per_second=config.rate_limit.requests_per_second,
                requests_per_hour=config.rate_limit.requests_per_hour,
                burst_size=config.rate_limit.burst_size,
            )

        # Create concurrency limiter if configured
        concurrency_limiter = None
        if config.concurrency:
            from ..common.concurrency_limiter import ConcurrencyLimiter

            concurrency_limiter = ConcurrencyLimiter(
                max_concurrent=config.concurrency.max_concurrent_requests
            )

        return cls(
            http_config=config.http,
            base_url=config.base_url,
            rate_limiter=rate_limiter,
            concurrency_limiter=concurrency_limiter,
            app_key=app_key,
        )

    async def search_videos(
        self,
        artist: str,
        track_title: str,
        page: int = 1,
        per_page: int = 25,
    ) -> IMVDbVideoSearchResult:
        """
        Search for music videos by artist and track title.

        Args:
            artist: Artist name to search for
            track_title: Track title to search for
            page: Page number for pagination (default: 1)
            per_page: Results per page (default: 25)

        Returns:
            IMVDbVideoSearchResult containing:
            - pagination: Pagination metadata
            - results: List of IMVDbEntityVideo objects

        Raises:
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> results = await client.search_videos("Robin Thicke", "Blurred Lines")
            >>> print(f"Found {results.pagination.total_results} videos")
            >>> for video in results.results:
            ...     print(f"{video.song_title} ({video.year})")
        """
        # Build search query
        query = f"{artist} {track_title}"

        params = {
            "q": query,
            "page": page,
            "per_page": per_page,
        }

        self.logger.info(
            "imvdb_search_videos",
            artist=artist,
            track_title=track_title,
            page=page,
            per_page=per_page,
        )

        response = await self.get("/search/videos", params=params)
        response.raise_for_status()
        return IMVDbParser.parse_search_results(response.json())

    async def search_entities(
        self,
        artist_name: str,
        page: int = 1,
        per_page: int = 25,
    ) -> IMVDbEntitySearchResponse:
        """
        Search for entities (artists, directors, etc.) by name.

        Args:
            artist_name: Entity name to search for
            page: Page number for pagination (default: 1)
            per_page: Results per page (default: 25)

        Returns:
            IMVDbEntitySearchResponse containing:
            - pagination: Pagination metadata (total_results, current_page, per_page, total_pages)
            - results: List of IMVDbEntitySearchResult objects with id, name, slug, discogs_id, etc.

        Raises:
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> results = await client.search_entities("Robin Thicke")
            >>> for entity in results.results:
            ...     print(f"{entity.slug} (ID: {entity.id}, Discogs: {entity.discogs_id})")
        """
        params = {
            "q": artist_name,
            "page": page,
            "per_page": per_page,
        }

        self.logger.info(
            "imvdb_search_entities",
            artist_name=artist_name,
            page=page,
            per_page=per_page,
        )

        response = await self.get("/search/entities", params=params)
        response.raise_for_status()
        return IMVDbParser.parse_entity_search_results(response.json())

    async def get_video(self, video_id: int) -> IMVDbVideo:
        """
        Get detailed information about a specific video.

        Includes credits, featured artists, and video sources.

        Args:
            video_id: IMVDb video ID

        Returns:
            IMVDbVideo containing:
            - id: Video ID
            - song_title: Track title
            - year: Release year
            - artists: List of primary artists
            - featured_artists: List of featured artists
            - directors: List of directors
            - credits: Detailed crew and cast credits
            - sources: Video source URLs (YouTube, Vimeo, etc.)
            - image: Video thumbnail images

        Raises:
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> video = await client.get_video(121779770452)
            >>> print(f"{video.song_title} by {video.artists[0].name}")
            >>> print(f"Director: {video.directors[0].entity_name}")
            >>> for source in video.sources:
            ...     print(f"{source.source}: {source.source_data}")
        """
        # Include credits, featured artists, and sources
        params = {"include": "credits,featured,sources"}

        self.logger.info("imvdb_get_video", video_id=video_id)

        response = await self.get(f"/video/{video_id}", params=params)
        response.raise_for_status()
        return IMVDbParser.parse_video(response.json())

    async def get_entity(self, entity_id: int) -> IMVDbEntity:
        """
        Get detailed information about a specific entity (artist, director, etc.).

        Includes videos where the entity is the primary artist or featured.

        Args:
            entity_id: IMVDb entity ID

        Returns:
            IMVDbEntity containing:
            - id: Entity ID
            - name: Entity name
            - slug: URL-friendly slug
            - artist_video_count: Number of videos as primary artist
            - featured_video_count: Number of videos as featured artist
            - artist_videos: List of videos as primary artist
            - featured_artist_videos: List of videos as featured artist
            - artist_videos_total: Total artist videos (for pagination)
            - featured_videos_total: Total featured videos (for pagination)

        Raises:
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> entity = await client.get_entity(838673)
            >>> print(f"{entity.slug}: {entity.artist_video_count} videos")
            >>> for video in entity.artist_videos:
            ...     print(f"  - {video.song_title} ({video.year})")
        """
        # Include artist videos and featured videos
        params = {"include": "artist_videos,featured_videos"}

        self.logger.info("imvdb_get_entity", entity_id=entity_id)

        response = await self.get(f"/entity/{entity_id}", params=params)
        response.raise_for_status()
        return IMVDbParser.parse_entity(response.json())

    async def search_video_by_artist_title(
        self,
        artist: str,
        title: str,
        threshold: float = 0.8,
    ) -> IMVDbVideo:
        """
        Search for a specific video by artist and title with automatic matching.

        This convenience method combines search and matching logic. It automatically
        strips featured artists from both artist and title parameters before searching,
        then uses exact or fuzzy matching to find the best result.

        Args:
            artist: Artist name (featured artists will be stripped, e.g., "Artist ft. Other" → "Artist")
            title: Song title (featured artists will be stripped)
            threshold: Minimum similarity score for fuzzy matching (0.0-1.0, default: 0.8)

        Returns:
            IMVDbVideo with best match, includes is_exact_match field indicating match quality

        Raises:
            EmptySearchResultsError: If search returns no results
            VideoNotFoundError: If no match found above threshold
            httpx.HTTPStatusError: If the API returns an error status

        Example:
            >>> # Exact match
            >>> video = await client.search_video_by_artist_title("Robin Thicke", "Blurred Lines")
            >>> print(video.is_exact_match)  # True
            >>>
            >>> # Works with featured artists in query
            >>> video = await client.search_video_by_artist_title("Robin Thicke ft. T.I.", "Blurred Lines")
            >>>
            >>> # Fuzzy match with warning
            >>> video = await client.search_video_by_artist_title("Robin Thick", "Blured Lines")
            >>> print(video.is_exact_match)  # False (warning logged)
        """
        # Normalize artist and title by removing featured artists
        normalized_artist = normalize_for_matching(artist, remove_featured=True)
        normalized_title = normalize_for_matching(title, remove_featured=True)

        self.logger.info(
            "imvdb_search_video_by_artist_title",
            artist=artist,
            title=title,
            normalized_artist=normalized_artist,
            normalized_title=normalized_title,
        )

        # Search for videos
        search_results = await self.search_videos(normalized_artist, normalized_title)

        # Find best match using parser logic
        return IMVDbParser.find_best_video_match(
            results=search_results.results,
            artist=normalized_artist,
            title=normalized_title,
            threshold=threshold,
        )
