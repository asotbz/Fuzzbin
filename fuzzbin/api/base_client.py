"""Base API client with rate limiting and concurrency control."""

from pathlib import Path
from typing import Any, Optional, Dict

import httpx
import structlog

from ..common.http_client import AsyncHTTPClient
from ..common.rate_limiter import RateLimiter
from ..common.concurrency_limiter import ConcurrencyLimiter
from ..common.config import APIClientConfig, HTTPConfig, CacheConfig

logger = structlog.get_logger(__name__)


class RateLimitedAPIClient(AsyncHTTPClient):
    """
    HTTP client with built-in rate limiting and concurrency control.

    This client extends AsyncHTTPClient to add rate limiting and concurrency
    control, making it suitable for API integrations with strict limits.

    Features:
    - Token bucket rate limiting
    - Concurrent request limiting
    - All features from AsyncHTTPClient (retries, connection pooling, etc.)

    Note: For production use, use the API-specific clients (IMVDbClient,
    DiscogsClient, SpotifyClient) which provide sensible defaults for
    rate limiting and authentication.
    """

    def __init__(
        self,
        http_config: HTTPConfig,
        base_url: str = "",
        rate_limiter: Optional[RateLimiter] = None,
        concurrency_limiter: Optional[ConcurrencyLimiter] = None,
        auth_headers: Optional[Dict[str, str]] = None,
        cache_config: Optional[CacheConfig] = None,
        config_dir: Optional[Path] = None,
    ):
        """
        Initialize the rate-limited API client.

        Args:
            http_config: HTTP configuration (timeout, retries, etc.)
            base_url: Base URL for all requests
            rate_limiter: Optional rate limiter instance
            concurrency_limiter: Optional concurrency limiter instance
            auth_headers: Optional authentication headers to include in all requests
            cache_config: Optional cache configuration
            config_dir: Directory for resolving relative cache paths (optional)
        """
        super().__init__(http_config, base_url, cache_config, config_dir)
        self.rate_limiter = rate_limiter
        self.concurrency_limiter = concurrency_limiter
        self.auth_headers = auth_headers or {}

        self.logger.info(
            "rate_limited_api_client_initialized",
            base_url=base_url,
            has_rate_limiter=rate_limiter is not None,
            has_concurrency_limiter=concurrency_limiter is not None,
            has_cache=cache_config is not None and cache_config.enabled,
        )

    @classmethod
    def from_config(
        cls, config: APIClientConfig, config_dir: Optional[Path] = None
    ) -> "RateLimitedAPIClient":
        """
        Create a client from APIClientConfig.

        Note: This base implementation creates a minimal client without rate limiting
        or concurrency control. Subclasses (IMVDbClient, DiscogsClient, SpotifyClient)
        override this method to provide API-specific defaults.

        Args:
            config: API client configuration (typically just contains auth)
            config_dir: Directory for resolving relative cache paths (optional)

        Returns:
            Configured RateLimitedAPIClient instance
        """
        # Use default HTTP config if not provided through some mechanism
        http_config = HTTPConfig()

        return cls(
            http_config=http_config,
            base_url="",  # Base URL must be set by subclass or caller
            rate_limiter=None,
            concurrency_limiter=None,
            auth_headers=config.auth,
            cache_config=None,
            config_dir=config_dir,
        )

    async def _apply_limiters_and_auth(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """
        Apply rate limiting, concurrency control, and auth before making request.

        Cache hits bypass rate limiters to avoid consuming rate limit quota
        for responses served from cache.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments

        Returns:
            httpx.Response object
        """
        # Add auth headers if configured
        if self.auth_headers:
            headers = kwargs.get("headers", {})
            headers.update(self.auth_headers)
            kwargs["headers"] = headers

        # For cached responses, we bypass rate limiting by making the request
        # and checking if it came from cache
        if self.cache_config and self.cache_config.enabled:
            # Apply concurrency limit if configured
            if self.concurrency_limiter:
                async with self.concurrency_limiter:
                    response = await self._make_request_with_retry(method, url, **kwargs)
            else:
                response = await self._make_request_with_retry(method, url, **kwargs)

            # Check if response came from cache
            if not self._is_cached_response(response):
                # Only apply rate limiting for non-cached responses
                if self.rate_limiter:
                    await self.rate_limiter.acquire()

            return response
        else:
            # Original behavior when cache is not enabled
            # Wait for rate limit if configured
            if self.rate_limiter:
                await self.rate_limiter.acquire()

            # Apply concurrency limit if configured
            if self.concurrency_limiter:
                async with self.concurrency_limiter:
                    return await self._make_request_with_retry(method, url, **kwargs)

            return await self._make_request_with_retry(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """
        Make a GET request with rate limiting and concurrency control.

        Args:
            url: Request URL
            **kwargs: Additional arguments (params, headers, etc.)

        Returns:
            httpx.Response object
        """
        self.logger.debug("api_request", method="GET", url=str(url))
        return await self._apply_limiters_and_auth("GET", url, **kwargs)

    async def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make a POST request with rate limiting and concurrency control.

        Args:
            url: Request URL
            json: JSON data to send in request body
            data: Form data to send in request body
            **kwargs: Additional arguments (headers, etc.)

        Returns:
            httpx.Response object
        """
        self.logger.debug("api_request", method="POST", url=str(url))
        return await self._apply_limiters_and_auth("POST", url, json=json, data=data, **kwargs)

    async def put(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make a PUT request with rate limiting and concurrency control.

        Args:
            url: Request URL
            json: JSON data to send in request body
            data: Form data to send in request body
            **kwargs: Additional arguments (headers, etc.)

        Returns:
            httpx.Response object
        """
        self.logger.debug("api_request", method="PUT", url=str(url))
        return await self._apply_limiters_and_auth("PUT", url, json=json, data=data, **kwargs)

    async def patch(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make a PATCH request with rate limiting and concurrency control.

        Args:
            url: Request URL
            json: JSON data to send in request body
            data: Form data to send in request body
            **kwargs: Additional arguments (headers, etc.)

        Returns:
            httpx.Response object
        """
        self.logger.debug("api_request", method="PATCH", url=str(url))
        return await self._apply_limiters_and_auth("PATCH", url, json=json, data=data, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """
        Make a DELETE request with rate limiting and concurrency control.

        Args:
            url: Request URL
            **kwargs: Additional arguments (headers, etc.)

        Returns:
            httpx.Response object
        """
        self.logger.debug("api_request", method="DELETE", url=str(url))
        return await self._apply_limiters_and_auth("DELETE", url, **kwargs)

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make an HTTP request with rate limiting and concurrency control.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE, etc.)
            url: Request URL
            **kwargs: Additional arguments

        Returns:
            httpx.Response object
        """
        self.logger.debug("api_request", method=method.upper(), url=str(url))
        return await self._apply_limiters_and_auth(method.upper(), url, **kwargs)

    async def clear_cache(self) -> None:
        """
        Clear all cached responses for this API client.

        This method delegates to the underlying HTTP client's cache clearing
        functionality. Only available when caching is enabled.

        Example:
            >>> config = APIClientConfig(
            ...     name="myapi",
            ...     base_url="https://api.example.com",
            ...     cache=CacheConfig(enabled=True)
            ... )
            >>> async with RateLimitedAPIClient.from_config(config) as client:
            ...     # Make some requests
            ...     await client.get("/data")
            ...     # Clear the cache
            ...     await client.clear_cache()
        """
        await super().clear_cache()
