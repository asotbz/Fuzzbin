"""Spotify OAuth 2.0 token management with Client Credentials flow."""

import json
import time
from pathlib import Path
from typing import Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)


class SpotifyTokenManager:
    """
    Manages Spotify OAuth 2.0 access tokens with automatic refresh.

    Uses the Client Credentials flow for server-to-server authentication.
    This flow is suitable for accessing public playlists and doesn't require
    user authorization.

    Tokens are automatically refreshed when they expire and cached to disk
    to minimize API calls.

    Example:
        >>> import asyncio
        >>> from fuzzbin.api.spotify_auth import SpotifyTokenManager
        >>>
        >>> async def main():
        ...     manager = SpotifyTokenManager(
        ...         client_id="your_client_id",
        ...         client_secret="your_client_secret",
        ...     )
        ...
        ...     # Get token (automatically obtains or refreshes as needed)
        ...     token = await manager.get_access_token()
        ...     print(f"Token: {token[:20]}...")
        >>>
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_cache_path: Optional[Path] = None,
    ):
        """
        Initialize token manager.

        Args:
            client_id: Spotify client ID (from developer dashboard)
            client_secret: Spotify client secret (from developer dashboard)
            token_cache_path: Path to cache tokens (default: .cache/spotify_tokens.json)

        Note:
            Get client credentials from: https://developer.spotify.com/dashboard
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_cache_path = token_cache_path or Path(".cache/spotify_tokens.json")

        self._access_token: Optional[str] = None
        self._expires_at: Optional[float] = None

        # Load cached tokens if available
        self._load_cached_tokens()

    async def get_access_token(self) -> str:
        """
        Get valid access token, refreshing if needed.

        This method checks if the current token is still valid. If not, it
        automatically obtains a new token using the Client Credentials flow.

        Returns:
            Valid access token

        Raises:
            httpx.HTTPStatusError: If token request fails
            Exception: If unable to get token

        Example:
            >>> token = await manager.get_access_token()
        """
        # Check if current token is still valid (with 60 second buffer)
        if self._access_token and self._expires_at:
            if time.time() < self._expires_at - 60:
                logger.debug(
                    "spotify_token_valid",
                    expires_in=int(self._expires_at - time.time()),
                )
                return self._access_token

        # Need to get new token
        await self._obtain_token()
        return self._access_token

    async def _obtain_token(self) -> None:
        """
        Get token using Client Credentials flow.

        This flow is for server-to-server authentication without user context.
        It's suitable for accessing public playlists.

        The token is valid for 1 hour and is automatically cached to disk.

        Raises:
            httpx.HTTPStatusError: If token request fails
        """
        logger.info("spotify_oauth_requesting_token")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://accounts.spotify.com/api/token",
                data={
                    "grant_type": "client_credentials",
                },
                auth=(self.client_id, self.client_secret),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response.raise_for_status()

            data = response.json()
            self._access_token = data["access_token"]
            expires_in = data["expires_in"]  # Usually 3600 (1 hour)
            self._expires_at = time.time() + expires_in

            # Cache the token
            self._save_tokens()

            logger.info(
                "spotify_oauth_token_obtained",
                expires_in=expires_in,
            )

    def _load_cached_tokens(self) -> None:
        """
        Load tokens from cache file if it exists.

        If the cache file doesn't exist or is invalid, tokens will be
        obtained fresh on the next get_access_token() call.
        """
        if not self.token_cache_path.exists():
            logger.debug(
                "spotify_token_cache_not_found",
                cache_path=str(self.token_cache_path),
            )
            return

        try:
            with open(self.token_cache_path, "r") as f:
                data = json.load(f)

            self._access_token = data.get("access_token")
            self._expires_at = data.get("expires_at")

            logger.info(
                "spotify_tokens_loaded_from_cache",
                cache_path=str(self.token_cache_path),
                expires_in=int(self._expires_at - time.time())
                if self._expires_at
                else 0,
            )
        except Exception as e:
            logger.warning(
                "spotify_token_cache_load_failed",
                error=str(e),
                cache_path=str(self.token_cache_path),
            )

    def _save_tokens(self) -> None:
        """
        Save tokens to cache file.

        Creates the cache directory if it doesn't exist.
        """
        self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "access_token": self._access_token,
            "expires_at": self._expires_at,
        }

        with open(self.token_cache_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug(
            "spotify_tokens_cached",
            cache_path=str(self.token_cache_path),
        )

    def clear_cache(self) -> None:
        """
        Clear cached tokens.

        Use this to force obtaining a fresh token on the next request.
        """
        if self.token_cache_path.exists():
            self.token_cache_path.unlink()
            logger.info(
                "spotify_token_cache_cleared",
                cache_path=str(self.token_cache_path),
            )

        self._access_token = None
        self._expires_at = None
