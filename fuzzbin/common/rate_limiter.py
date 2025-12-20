"""Rate limiting using token bucket algorithm for async operations."""

import asyncio
import time
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for controlling request rates.

    This implementation uses the token bucket algorithm, which allows for
    smooth rate limiting while supporting short bursts of traffic.

    The limiter accumulates tokens over time at a specified rate. Each
    request consumes one token. If no tokens are available, the request
    waits until a token becomes available.

    Example:
        >>> limiter = RateLimiter(requests_per_minute=60)
        >>> async with limiter:
        ...     # Make rate-limited request
        ...     response = await client.get("/endpoint")

    Attributes:
        rate: Number of tokens added per second
        burst_size: Maximum number of tokens that can accumulate
        tokens: Current number of available tokens
    """

    def __init__(
        self,
        requests_per_minute: Optional[int] = None,
        requests_per_second: Optional[int] = None,
        requests_per_hour: Optional[int] = None,
        burst_size: Optional[int] = None,
    ):
        """
        Initialize the rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute
            requests_per_second: Maximum requests per second
            requests_per_hour: Maximum requests per hour
            burst_size: Maximum burst size (defaults to rate limit)

        Note:
            Only one of requests_per_* should be specified. If multiple are
            provided, they are combined (which may not be desired).

        Example:
            >>> # 60 requests per minute, allow bursts of 10
            >>> limiter = RateLimiter(requests_per_minute=60, burst_size=10)
            >>>
            >>> # 5000 requests per hour
            >>> limiter = RateLimiter(requests_per_hour=5000)
        """
        # Calculate rate in requests per second
        rate = 0.0
        if requests_per_second:
            rate += requests_per_second
        if requests_per_minute:
            rate += requests_per_minute / 60.0
        if requests_per_hour:
            rate += requests_per_hour / 3600.0

        if rate == 0:
            raise ValueError(
                "At least one rate limit must be specified "
                "(requests_per_second, requests_per_minute, or requests_per_hour)"
            )

        self.rate = rate  # tokens per second
        self.burst_size = burst_size if burst_size is not None else int(rate * 60)
        self.tokens = float(self.burst_size)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

        logger.debug(
            "rate_limiter_initialized",
            rate_per_second=round(self.rate, 2),
            burst_size=self.burst_size,
        )

    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire permission to make one or more requests.

        This method will wait if necessary until enough tokens are available.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Example:
            >>> limiter = RateLimiter(requests_per_minute=60)
            >>> await limiter.acquire()  # Wait for permission
            >>> # Now safe to make request
        """
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_update

                # Add tokens based on elapsed time
                self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    logger.debug(
                        "rate_limit_acquired",
                        tokens_acquired=tokens,
                        tokens_remaining=round(self.tokens, 2),
                    )
                    return

                # Calculate wait time for next token
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate

                logger.debug(
                    "rate_limit_waiting",
                    tokens_needed=round(tokens_needed, 2),
                    wait_seconds=round(wait_time, 2),
                )

                # Release lock while waiting
                self._lock.release()
                try:
                    await asyncio.sleep(wait_time)
                finally:
                    await self._lock.acquire()

    async def __aenter__(self) -> "RateLimiter":
        """Context manager entry - acquire a token."""
        await self.acquire()
        return self

    async def __aexit__(self, *args: any) -> None:
        """Context manager exit."""
        pass

    def get_available_tokens(self) -> float:
        """
        Get the current number of available tokens (non-blocking).

        Returns:
            Number of available tokens

        Example:
            >>> limiter = RateLimiter(requests_per_minute=60)
            >>> available = limiter.get_available_tokens()
            >>> print(f"Can make {int(available)} immediate requests")
        """
        now = time.monotonic()
        elapsed = now - self.last_update
        return min(self.burst_size, self.tokens + elapsed * self.rate)

    async def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False otherwise

        Example:
            >>> if await limiter.try_acquire():
            ...     # Make request immediately
            ...     response = await client.get("/endpoint")
            ... else:
            ...     # Rate limit would be exceeded
            ...     print("Rate limit reached, skipping request")
        """
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update

            # Add tokens based on elapsed time
            self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(
                    "rate_limit_try_acquired",
                    tokens_acquired=tokens,
                    tokens_remaining=round(self.tokens, 2),
                )
                return True

            logger.debug(
                "rate_limit_try_failed",
                tokens_needed=tokens,
                tokens_available=round(self.tokens, 2),
            )
            return False
