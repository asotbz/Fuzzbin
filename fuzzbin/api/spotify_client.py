"""Spotify Web API client for playlist and track metadata access."""

import os
from typing import Any, Dict, List, Optional

import httpx
import structlog

from .base_client import RateLimitedAPIClient
from ..common.config import APIClientConfig
from ..parsers.spotify_models import (
    SpotifyPlaylist,
    SpotifyPlaylistTracksResponse,
    SpotifyTrack,
)
from ..parsers.spotify_parser import SpotifyParser

logger = structlog.get_logger(__name__)


class SpotifyClient(RateLimitedAPIClient):
    """
    Client for Spotify Web API.

    The Spotify Web API provides access to playlist data, track metadata,
    artist information, and album details.

    API Rate Limit: ~180 requests per minute (conservative estimate)
    Note: Spotify does not publish exact rate limits. The API uses 429 responses
    to indicate rate limiting.

    Features:
    - Playlist retrieval with metadata
    - Paginated track fetching from playlists
    - Automatic pagination handling
    - Rate limiting and concurrency control
    - Response caching support

    Authentication:
    - Supports two authentication methods:
      1. Manual token: SPOTIFY_ACCESS_TOKEN environment variable or config
      2. OAuth Client Credentials: Automatic token management with client_id/secret
    - OAuth is recommended for production use (tokens auto-refresh)
    - Manual tokens expire after 1 hour and must be manually refreshed
    - Environment variable takes precedence over config

    Example:
        >>> import asyncio
        >>> from fuzzbin.api.spotify_client import SpotifyClient
        >>> from fuzzbin.common.config import APIClientConfig
        >>>
        >>> async def main():
        ...     config = APIClientConfig(
        ...         name="spotify",
        ...         base_url="https://api.spotify.com/v1",
        ...         custom={"access_token": "YOUR_TOKEN"}
        ...     )
        ...
        ...     async with SpotifyClient.from_config(config) as client:
        ...         # Get playlist
        ...         playlist = await client.get_playlist("37i9dQZF1DXcBWIGoYBM5M")
        ...         print(f"Playlist: {playlist.name}")
        ...
        ...         # Get all tracks
        ...         tracks = await client.get_all_playlist_tracks("37i9dQZF1DXcBWIGoYBM5M")
        ...         for track in tracks:
        ...             print(f"  {track.name} by {track.artists[0].name}")
        >>>
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        *args: Any,
        access_token: Optional[str] = None,
        token_manager: Optional["SpotifyTokenManager"] = None,
        **kwargs: Any,
    ):
        """
        Initialize the Spotify API client.

        Args:
            *args: Positional arguments for RateLimitedAPIClient
            access_token: Spotify OAuth access token (optional, can use SPOTIFY_ACCESS_TOKEN env var)
            token_manager: SpotifyTokenManager for automatic token refresh (optional)
            **kwargs: Keyword arguments for RateLimitedAPIClient

        Note:
            If token_manager is provided, it will be used for automatic token management.
            Otherwise, access_token will be used (from env var or parameter).
        """
        self.token_manager = token_manager

        # Get access token from env variable or parameter
        # Environment variable takes precedence
        token = os.environ.get("SPOTIFY_ACCESS_TOKEN") or access_token

        # Add Spotify-specific auth header if using manual token
        # If using token_manager, headers will be set dynamically per request
        auth_headers = kwargs.get("auth_headers", {})
        if token and not token_manager:
            auth_headers["Authorization"] = f"Bearer {token}"
        kwargs["auth_headers"] = auth_headers

        super().__init__(*args, **kwargs)

        self.logger.info(
            "spotify_client_initialized",
            base_url=self.base_url,
            has_token=bool(token),
            has_token_manager=bool(token_manager),
        )

    # Default configuration constants
    DEFAULT_BASE_URL = "https://api.spotify.com/v1"
    DEFAULT_REQUESTS_PER_MINUTE = 180
    DEFAULT_BURST_SIZE = 10
    DEFAULT_MAX_CONCURRENT = 5

    @classmethod
    def from_config(cls, config: APIClientConfig) -> "SpotifyClient":
        """
        Create Spotify client from APIClientConfig.

        Uses hardcoded defaults for base URL, rate limiting, and concurrency.
        Only authentication can be configured via the config object.

        Args:
            config: API client configuration (only auth field is used)

        Returns:
            Configured SpotifyClient instance

        Example:
            >>> from fuzzbin.common.config import APIClientConfig
            >>> # Using OAuth (recommended)
            >>> config = APIClientConfig(auth={"client_id": "...", "client_secret": "..."})
            >>> client = SpotifyClient.from_config(config)
            >>>
            >>> # Or using manual token
            >>> config = APIClientConfig(auth={"access_token": "YOUR_TOKEN"})
            >>> client = SpotifyClient.from_config(config)
        """
        # Extract credentials from config.auth and environment variables
        # Environment variables take precedence
        access_token = None
        client_id = None
        client_secret = None

        if config.auth:
            access_token = config.auth.get("access_token")
            client_id = config.auth.get("client_id")
            client_secret = config.auth.get("client_secret")

        # Environment variables override config
        client_id = os.environ.get("SPOTIFY_CLIENT_ID") or client_id
        client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET") or client_secret

        # Create token manager if we have client credentials
        token_manager = None
        if client_id and client_secret:
            from .spotify_auth import SpotifyTokenManager

            token_manager = SpotifyTokenManager(
                client_id=client_id,
                client_secret=client_secret,
            )
            logger.info(
                "spotify_token_manager_created",
                has_cached_token=token_manager._access_token is not None,
            )

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
            access_token=access_token,
            token_manager=token_manager,
        )

    async def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authorization headers with current token.

        If using token_manager, this will automatically fetch a fresh token
        if the current one has expired.

        Returns:
            Dictionary of authorization headers
        """
        if self.token_manager:
            token = await self.token_manager.get_access_token()
            return {"Authorization": f"Bearer {token}"}
        return {}

    async def get(self, path: str, **kwargs) -> httpx.Response:
        """
        Override GET to inject fresh token when using token manager.

        Args:
            path: API endpoint path
            **kwargs: Additional arguments for the request

        Returns:
            HTTP response
        """
        if self.token_manager:
            headers = kwargs.get("headers", {})
            headers.update(await self._get_auth_headers())
            kwargs["headers"] = headers
        return await super().get(path, **kwargs)

    async def post(self, path: str, **kwargs) -> httpx.Response:
        """
        Override POST to inject fresh token when using token manager.

        Args:
            path: API endpoint path
            **kwargs: Additional arguments for the request

        Returns:
            HTTP response
        """
        if self.token_manager:
            headers = kwargs.get("headers", {})
            headers.update(await self._get_auth_headers())
            kwargs["headers"] = headers
        return await super().post(path, **kwargs)

    async def get_playlist(self, playlist_id: str) -> SpotifyPlaylist:
        """
        Get detailed information about a Spotify playlist.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            SpotifyPlaylist containing:
            - id: Playlist ID
            - name: Playlist name
            - description: Playlist description
            - owner: Playlist owner information
            - tracks: Track listing (if included)
            - public: Public visibility
            - collaborative: Collaborative flag

        Raises:
            httpx.HTTPStatusError: If the API returns an error status
            - 401: Invalid or expired access token
            - 404: Playlist not found

        Example:
            >>> playlist = await client.get_playlist("37i9dQZF1DXcBWIGoYBM5M")
            >>> print(f"{playlist.name}: {playlist.description}")
        """
        self.logger.info("spotify_get_playlist", playlist_id=playlist_id)

        response = await self.get(f"/playlists/{playlist_id}")
        response.raise_for_status()
        return SpotifyParser.parse_playlist(response.json())

    async def get_playlist_tracks(
        self,
        playlist_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> SpotifyPlaylistTracksResponse:
        """
        Get tracks from a Spotify playlist (paginated).

        Spotify returns a maximum of 100 tracks per request. Use the `next`
        field in the response to fetch additional pages, or use
        `get_all_playlist_tracks()` for automatic pagination.

        Args:
            playlist_id: Spotify playlist ID
            limit: Number of tracks to return (max 100, default 50)
            offset: Index of first track to return (default 0)

        Returns:
            SpotifyPlaylistTracksResponse containing:
            - items: List of playlist tracks
            - total: Total number of tracks
            - limit: Items per page
            - offset: Offset of first item
            - next: URL for next page (if available)
            - previous: URL for previous page (if available)

        Raises:
            httpx.HTTPStatusError: If the API returns an error status
            - 401: Invalid or expired access token
            - 404: Playlist not found

        Example:
            >>> # Get first 50 tracks
            >>> response = await client.get_playlist_tracks("37i9dQZF1DXcBWIGoYBM5M", limit=50)
            >>> print(f"Total tracks: {response.total}")
            >>> print(f"Fetched: {len(response.items)}")
            >>>
            >>> # Get next page
            >>> if response.next:
            ...     next_response = await client.get_playlist_tracks(
            ...         "37i9dQZF1DXcBWIGoYBM5M",
            ...         limit=50,
            ...         offset=response.offset + response.limit
            ...     )
        """
        params = {
            "limit": min(limit, 100),  # Spotify max is 100
            "offset": offset,
        }

        self.logger.info(
            "spotify_get_playlist_tracks",
            playlist_id=playlist_id,
            limit=params["limit"],
            offset=offset,
        )

        response = await self.get(f"/playlists/{playlist_id}/tracks", params=params)
        response.raise_for_status()
        return SpotifyParser.parse_playlist_tracks(response.json())

    async def get_all_playlist_tracks(self, playlist_id: str) -> List[SpotifyTrack]:
        """
        Get all tracks from a Spotify playlist with automatic pagination.

        This is a convenience method that handles pagination automatically,
        fetching all tracks across multiple API requests if necessary.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            List of SpotifyTrack objects containing all tracks in the playlist

        Raises:
            httpx.HTTPStatusError: If the API returns an error status
            - 401: Invalid or expired access token
            - 404: Playlist not found

        Example:
            >>> tracks = await client.get_all_playlist_tracks("37i9dQZF1DXcBWIGoYBM5M")
            >>> print(f"Fetched {len(tracks)} tracks")
            >>> for track in tracks:
            ...     artist = track.artists[0].name if track.artists else "Unknown"
            ...     print(f"  {track.name} by {artist}")
        """
        all_tracks = []
        offset = 0
        limit = 50  # Fetch 50 tracks per request

        self.logger.info("spotify_get_all_playlist_tracks_start", playlist_id=playlist_id)

        while True:
            response = await self.get_playlist_tracks(playlist_id, limit=limit, offset=offset)

            # Extract tracks from playlist track items
            for item in response.items:
                all_tracks.append(item.track)

            # Check if we've fetched all tracks
            if response.next is None or len(response.items) == 0:
                break

            # Move to next page
            offset += len(response.items)

            self.logger.debug(
                "spotify_pagination",
                playlist_id=playlist_id,
                offset=offset,
                total=response.total,
                fetched=len(all_tracks),
            )

        self.logger.info(
            "spotify_get_all_playlist_tracks_complete",
            playlist_id=playlist_id,
            total_tracks=len(all_tracks),
        )

        return all_tracks

    async def get_track(self, track_id: str) -> SpotifyTrack:
        """
        Get detailed information about a specific track.

        Args:
            track_id: Spotify track ID

        Returns:
            SpotifyTrack containing:
            - id: Track ID
            - name: Track title
            - artists: List of artists
            - album: Album information
            - duration_ms: Track duration
            - popularity: Popularity score (0-100)
            - explicit: Explicit content flag

        Raises:
            httpx.HTTPStatusError: If the API returns an error status
            - 401: Invalid or expired access token
            - 404: Track not found

        Example:
            >>> track = await client.get_track("0c6xIDDpzE81m2q797ordA")
            >>> print(f"{track.name} by {track.artists[0].name}")
            >>> print(f"Album: {track.album.name} ({track.album.release_date})")
        """
        self.logger.info("spotify_get_track", track_id=track_id)

        response = await self.get(f"/tracks/{track_id}")
        response.raise_for_status()
        return SpotifyParser.parse_track(response.json())

    async def get_albums(self, album_ids: List[str]) -> List[SpotifyAlbum]:
        """
        Get detailed information about multiple albums.

        Fetches album metadata including label information for up to 20 albums
        per request. Automatically batches larger requests.

        Args:
            album_ids: List of Spotify album IDs (max 20 per API call)

        Returns:
            List of SpotifyAlbum objects containing:
            - id: Album ID
            - name: Album name
            - label: Record label (if available)
            - release_date: Release date
            - artists: Album artists
            - images: Album artwork

        Raises:
            httpx.HTTPStatusError: If the API returns an error status
            - 401: Invalid or expired access token
            - 404: One or more albums not found

        Example:
            >>> album_ids = ["6dVIqQ8qmQ5GBnJ9shOYGE", "3a0UOgDWw2pTajw85QPMiz"]
            >>> albums = await client.get_albums(album_ids)
            >>> for album in albums:
            ...     print(f"{album.name} - {album.label or 'Unknown Label'}")
        """
        if not album_ids:
            return []

        # Spotify allows up to 20 album IDs per request
        MAX_IDS_PER_REQUEST = 20
        all_albums = []

        # Batch into groups of 20
        for i in range(0, len(album_ids), MAX_IDS_PER_REQUEST):
            batch = album_ids[i : i + MAX_IDS_PER_REQUEST]
            ids_param = ",".join(batch)

            self.logger.info(
                "spotify_get_albums",
                album_count=len(batch),
                batch_index=i // MAX_IDS_PER_REQUEST,
            )

            response = await self.get(f"/albums", params={"ids": ids_param})
            response.raise_for_status()

            data = response.json()
            albums = data.get("albums", [])

            for album_data in albums:
                if album_data:  # API returns null for invalid IDs
                    all_albums.append(SpotifyParser.parse_album(album_data))

        self.logger.info(
            "spotify_get_albums_complete",
            requested=len(album_ids),
            fetched=len(all_albums),
        )

        return all_albums
