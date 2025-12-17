"""Async HTTP client with automatic retry logic using httpx and tenacity."""

from typing import Any, Optional, Dict, Callable

import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
    RetryCallState,
)

from .config import HTTPConfig

logger = structlog.get_logger(__name__)


class AsyncHTTPClient:
    """
    Async HTTP client with connection pooling and automatic retry logic.

    This client provides a context manager interface for making HTTP requests
    with automatic retries on transient failures (network errors and 5xx status
    codes). It uses exponential backoff with configurable parameters.

    Features:
    - Connection pooling with httpx
    - Automatic retries with exponential backoff
    - Smart retry logic (skips 4xx except 408/429, retries 5xx and network errors)
    - Configurable timeouts and connection limits
    - Structured logging for observability

    Example:
        >>> import asyncio
        >>> from fuzzbin.common.config import HTTPConfig
        >>> 
        >>> async def main():
        ...     config = HTTPConfig()
        ...     async with AsyncHTTPClient(config) as client:
        ...         response = await client.get("https://api.example.com/data")
        ...         print(response.json())
        >>> 
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        config: HTTPConfig,
        base_url: str = "",
    ):
        """
        Initialize the async HTTP client.

        Args:
            config: HTTPConfig object with client settings
            base_url: Base URL for all requests (optional)
        """
        self.config = config
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
        self.logger = logger.bind(component="http_client")

    async def __aenter__(self) -> "AsyncHTTPClient":
        """Enter async context manager."""
        limits = httpx.Limits(
            max_connections=self.config.max_connections,
            max_keepalive_connections=self.config.max_keepalive_connections,
        )

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(float(self.config.timeout)),
            limits=limits,
            follow_redirects=True,
            max_redirects=self.config.max_redirects,
            verify=self.config.verify_ssl,
        )

        self.logger.info(
            "http_client_initialized",
            base_url=self.base_url,
            timeout=self.config.timeout,
            max_connections=self.config.max_connections,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()
            self.logger.info("http_client_closed")

    def _should_retry_status(self, response: httpx.Response) -> bool:
        """
        Determine if an HTTP status code should trigger a retry.

        Args:
            response: httpx Response object

        Returns:
            True if the status code should be retried, False otherwise
        """
        return response.status_code in self.config.retry.status_codes

    def _log_retry_attempt(self, retry_state: RetryCallState) -> None:
        """
        Log retry attempts with structured logging.

        Args:
            retry_state: Tenacity retry state object
        """
        self.logger.warning(
            "http_retry_attempt",
            attempt=retry_state.attempt_number,
            seconds_since_start=round(retry_state.seconds_since_start, 2),
        )

    async def _make_request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make an HTTP request with retry logic.

        This internal method handles the actual request and applies retry logic
        for network errors and retryable status codes.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments to pass to httpx

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPStatusError: For non-retryable errors (4xx except 408/429)
            httpx.RequestError: After exhausting retries for network errors
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with context manager.")

        # Define retryable network exceptions
        retryable_network_exceptions = (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.PoolTimeout,
            httpx.NetworkError,
        )

        def should_retry_http_error(exception: BaseException) -> bool:
            """Determine if an HTTPStatusError should trigger a retry."""
            if isinstance(exception, httpx.HTTPStatusError):
                return exception.response.status_code in self.config.retry.status_codes
            return False

        @retry(
            stop=stop_after_attempt(self.config.retry.max_attempts),
            wait=wait_exponential(
                multiplier=self.config.retry.backoff_multiplier,
                min=self.config.retry.min_wait,
                max=self.config.retry.max_wait,
            ),
            retry=(
                retry_if_exception_type(retryable_network_exceptions) |
                retry_if_exception(should_retry_http_error)
            ),
            before_sleep=self._log_retry_attempt,
            reraise=True,
        )
        async def _request() -> httpx.Response:
            response = await self._client.request(method, url, **kwargs)

            # Check if status code should trigger retry
            if self._should_retry_status(response):
                self.logger.warning(
                    "http_retryable_status",
                    method=method,
                    url=str(url),
                    status_code=response.status_code,
                )
                # Raise to trigger retry
                response.raise_for_status()

            return response

        return await _request()

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """
        Make a GET request with automatic retry logic.

        Args:
            url: Request URL
            **kwargs: Additional arguments (params, headers, etc.)

        Returns:
            httpx.Response object

        Example:
            >>> async with AsyncHTTPClient(config) as client:
            ...     response = await client.get("/users", params={"page": 1})
            ...     data = response.json()
        """
        self.logger.debug("http_request", method="GET", url=str(url))
        return await self._make_request_with_retry("GET", url, **kwargs)

    async def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make a POST request with automatic retry logic.

        Args:
            url: Request URL
            json: JSON data to send in request body
            data: Form data to send in request body
            **kwargs: Additional arguments (headers, etc.)

        Returns:
            httpx.Response object

        Example:
            >>> async with AsyncHTTPClient(config) as client:
            ...     response = await client.post(
            ...         "/users",
            ...         json={"name": "John", "email": "john@example.com"}
            ...     )
        """
        self.logger.debug("http_request", method="POST", url=str(url))
        return await self._make_request_with_retry(
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
        Make a PUT request with automatic retry logic.

        Args:
            url: Request URL
            json: JSON data to send in request body
            data: Form data to send in request body
            **kwargs: Additional arguments (headers, etc.)

        Returns:
            httpx.Response object
        """
        self.logger.debug("http_request", method="PUT", url=str(url))
        return await self._make_request_with_retry(
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
        Make a PATCH request with automatic retry logic.

        Args:
            url: Request URL
            json: JSON data to send in request body
            data: Form data to send in request body
            **kwargs: Additional arguments (headers, etc.)

        Returns:
            httpx.Response object
        """
        self.logger.debug("http_request", method="PATCH", url=str(url))
        return await self._make_request_with_retry(
            "PATCH", url, json=json, data=data, **kwargs
        )

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """
        Make a DELETE request with automatic retry logic.

        Args:
            url: Request URL
            **kwargs: Additional arguments (headers, etc.)

        Returns:
            httpx.Response object
        """
        self.logger.debug("http_request", method="DELETE", url=str(url))
        return await self._make_request_with_retry("DELETE", url, **kwargs)

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make an HTTP request with the specified method and automatic retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE, etc.)
            url: Request URL
            **kwargs: Additional arguments

        Returns:
            httpx.Response object

        Example:
            >>> async with AsyncHTTPClient(config) as client:
            ...     response = await client.request("HEAD", "/status")
        """
        self.logger.debug("http_request", method=method.upper(), url=str(url))
        return await self._make_request_with_retry(method.upper(), url, **kwargs)
