"""Base API client with rate limiting and concurrency control."""

from typing import Any, Optional, Dict

import httpx
import structlog

from ..common.http_client import AsyncHTTPClient
from ..common.rate_limiter import RateLimiter
from ..common.concurrency_limiter import ConcurrencyLimiter
from ..common.config import APIClientConfig, HTTPConfig

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

    Example:
        >>> config = APIClientConfig(
        ...     name="github",
        ...     base_url="https://api.github.com",
        ...     rate_limit=RateLimitConfig(requests_per_minute=60),
        ...     concurrency=ConcurrencyConfig(max_concurrent_requests=10)
        ... )
        >>> 
        >>> async with RateLimitedAPIClient.from_config(config) as client:
        ...     # Automatically rate limited and concurrency controlled
        ...     response = await client.get("/users/octocat")
    """

    def __init__(
        self,
        http_config: HTTPConfig,
        base_url: str = "",
        rate_limiter: Optional[RateLimiter] = None,
        concurrency_limiter: Optional[ConcurrencyLimiter] = None,
        auth_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the rate-limited API client.

        Args:
            http_config: HTTP configuration (timeout, retries, etc.)
            base_url: Base URL for all requests
            rate_limiter: Optional rate limiter instance
            concurrency_limiter: Optional concurrency limiter instance
            auth_headers: Optional authentication headers to include in all requests
        """
        super().__init__(http_config, base_url)
        self.rate_limiter = rate_limiter
        self.concurrency_limiter = concurrency_limiter
        self.auth_headers = auth_headers or {}

        self.logger.info(
            "rate_limited_api_client_initialized",
            base_url=base_url,
            has_rate_limiter=rate_limiter is not None,
            has_concurrency_limiter=concurrency_limiter is not None,
        )

    @classmethod
    def from_config(cls, config: APIClientConfig) -> "RateLimitedAPIClient":
        """
        Create a client from APIClientConfig.

        Args:
            config: API client configuration

        Returns:
            Configured RateLimitedAPIClient instance

        Example:
            >>> config = APIClientConfig(
            ...     name="myapi",
            ...     base_url="https://api.example.com",
            ...     rate_limit=RateLimitConfig(requests_per_minute=100)
            ... )
            >>> client = RateLimitedAPIClient.from_config(config)
        """
        rate_limiter = None
        if config.rate_limit and config.rate_limit.enabled:
            rate_limiter = RateLimiter(
                requests_per_minute=config.rate_limit.requests_per_minute,
                requests_per_second=config.rate_limit.requests_per_second,
                requests_per_hour=config.rate_limit.requests_per_hour,
                burst_size=config.rate_limit.burst_size,
            )

        concurrency_limiter = None
        if config.concurrency:
            concurrency_limiter = ConcurrencyLimiter(
                max_concurrent=config.concurrency.max_concurrent_requests
            )

        return cls(
            http_config=config.http,
            base_url=config.base_url,
            rate_limiter=rate_limiter,
            concurrency_limiter=concurrency_limiter,
            auth_headers=config.auth,
        )

    async def _apply_limiters_and_auth(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """
        Apply rate limiting, concurrency control, and auth before making request.

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
        return await self._apply_limiters_and_auth(
            "POST", url, json=json, data=data, **kwargs
        )

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
        return await self._apply_limiters_and_auth(
            "PUT", url, json=json, data=data, **kwargs
        )

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
        return await self._apply_limiters_and_auth(
            "PATCH", url, json=json, data=data, **kwargs
        )

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
