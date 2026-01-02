"""Concurrency limiting using asyncio semaphores."""

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ConcurrencyLimiter:
    """
    Limit the number of concurrent operations using a semaphore.

    This limiter ensures that no more than a specified number of operations
    run concurrently, preventing resource exhaustion and respecting API limits.

    Example:
        >>> limiter = ConcurrencyLimiter(max_concurrent=10)
        >>> async with limiter:
        ...     # Only 10 of these blocks can run simultaneously
        ...     response = await client.get("/endpoint")

    Attributes:
        max_concurrent: Maximum number of concurrent operations
        semaphore: Asyncio semaphore controlling access
    """

    def __init__(self, max_concurrent: int):
        """
        Initialize the concurrency limiter.

        Args:
            max_concurrent: Maximum number of concurrent operations

        Raises:
            ValueError: If max_concurrent is less than 1

        Example:
            >>> # Allow up to 5 concurrent requests
            >>> limiter = ConcurrencyLimiter(max_concurrent=5)
        """
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")

        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0

        logger.debug("concurrency_limiter_initialized", max_concurrent=max_concurrent)

    async def acquire(self) -> None:
        """
        Acquire permission to run a concurrent operation.

        This method will wait if the maximum number of concurrent operations
        is already running.

        Example:
            >>> limiter = ConcurrencyLimiter(max_concurrent=5)
            >>> await limiter.acquire()
            >>> try:
            ...     # Do work
            ...     await some_async_operation()
            ... finally:
            ...     limiter.release()
        """
        await self.semaphore.acquire()
        self._active_count += 1
        logger.debug(
            "concurrency_acquired",
            active=self._active_count,
            max=self.max_concurrent,
        )

    def release(self) -> None:
        """
        Release a concurrent operation slot.

        This should be called after an operation completes to allow another
        operation to proceed.
        """
        self.semaphore.release()
        self._active_count -= 1
        logger.debug(
            "concurrency_released",
            active=self._active_count,
            max=self.max_concurrent,
        )

    async def __aenter__(self) -> "ConcurrencyLimiter":
        """Context manager entry - acquire a slot."""
        await self.acquire()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Context manager exit - release the slot."""
        self.release()

    def try_acquire(self) -> bool:
        """
        Try to acquire a slot without waiting.

        Returns:
            True if slot was acquired, False otherwise

        Example:
            >>> limiter = ConcurrencyLimiter(max_concurrent=5)
            >>> if limiter.try_acquire():
            ...     try:
            ...         # Do work immediately
            ...         result = await some_operation()
            ...     finally:
            ...         limiter.release()
            ... else:
            ...     # Too many concurrent operations
            ...     print("Concurrency limit reached")
        """
        if self.semaphore.locked():
            return False

        # Check if a slot is available by inspecting the semaphore's internal value
        if self.semaphore._value > 0:
            # Manually decrement the semaphore counter
            self.semaphore._value -= 1
            self._active_count += 1
            logger.debug(
                "concurrency_try_acquired",
                active=self._active_count,
                max=self.max_concurrent,
            )
            return True
        return False

    def get_active_count(self) -> int:
        """
        Get the current number of active concurrent operations.

        Returns:
            Number of currently active operations

        Example:
            >>> limiter = ConcurrencyLimiter(max_concurrent=10)
            >>> active = limiter.get_active_count()
            >>> print(f"{active}/{limiter.max_concurrent} slots in use")
        """
        return self._active_count

    def get_available_slots(self) -> int:
        """
        Get the number of available concurrent operation slots.

        Returns:
            Number of available slots

        Example:
            >>> limiter = ConcurrencyLimiter(max_concurrent=10)
            >>> available = limiter.get_available_slots()
            >>> print(f"{available} concurrent operations can start immediately")
        """
        return self.max_concurrent - self._active_count
