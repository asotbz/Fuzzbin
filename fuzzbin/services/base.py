"""Base service infrastructure with callbacks, caching, and error handling.

This module provides the foundation for all service classes:
- BaseService: Common functionality for repository access, logging, config
- ServiceCallback: Protocol for progress/failure monitoring hooks
- Caching utilities: In-memory LRU cache with TTL support
- Service-specific exceptions: ValidationError, NotFoundError, ConflictError
"""

import asyncio
import time
from abc import ABC
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)

import structlog

import fuzzbin
from fuzzbin.core.db.repository import VideoRepository

logger = structlog.get_logger(__name__)

T = TypeVar("T")


# ==================== Exceptions ====================


class ServiceError(Exception):
    """Base exception for all service errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(ServiceError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, details={"field": field, **kwargs})
        self.field = field


class NotFoundError(ServiceError):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        message: str,
        resource_type: str,
        resource_id: Optional[Any] = None,
    ):
        super().__init__(
            message,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class ConflictError(ServiceError):
    """Raised when an operation would create a conflict (e.g., duplicate)."""

    def __init__(self, message: str, conflicting_id: Optional[Any] = None, **kwargs):
        super().__init__(message, details={"conflicting_id": conflicting_id, **kwargs})
        self.conflicting_id = conflicting_id


# ==================== Callback Protocol ====================


@runtime_checkable
class ServiceCallback(Protocol):
    """
    Protocol for service operation callbacks.

    Implement this protocol to receive progress updates and failure notifications
    from long-running service operations. This is used for monitoring progress
    and catching failures quickly.

    Example:
        >>> class MyProgressHandler:
        ...     async def on_progress(self, current: int, total: int, message: str) -> None:
        ...         print(f"Progress: {current}/{total} - {message}")
        ...
        ...     async def on_failure(self, error: Exception, context: dict) -> None:
        ...         logger.error("Operation failed", error=str(error), **context)
        ...
        ...     async def on_complete(self, result: Any) -> None:
        ...         print(f"Completed with result: {result}")
    """

    async def on_progress(self, current: int, total: int, message: str) -> None:
        """
        Called to report progress during long-running operations.

        Args:
            current: Current item number (1-indexed)
            total: Total number of items to process
            message: Human-readable progress message
        """
        ...

    async def on_failure(self, error: Exception, context: Dict[str, Any]) -> None:
        """
        Called when an operation fails (but may continue with next item).

        Args:
            error: The exception that occurred
            context: Additional context about the failure (item being processed, etc.)
        """
        ...

    async def on_complete(self, result: Any) -> None:
        """
        Called when the entire operation completes successfully.

        Args:
            result: The result of the operation
        """
        ...


class NullCallback:
    """No-op callback implementation for when no callback is provided."""

    async def on_progress(self, current: int, total: int, message: str) -> None:
        pass

    async def on_failure(self, error: Exception, context: Dict[str, Any]) -> None:
        pass

    async def on_complete(self, result: Any) -> None:
        pass


# ==================== Caching Utilities ====================


class CacheEntry(Generic[T]):
    """A single cache entry with value and expiration time."""

    def __init__(self, value: T, ttl_seconds: float):
        self.value = value
        self.expires_at = time.monotonic() + ttl_seconds

    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at


class AsyncLRUCache(Generic[T]):
    """
    Simple async-compatible LRU cache with TTL support.

    Thread-safe for async operations via asyncio.Lock.
    """

    def __init__(self, maxsize: int = 128, ttl_seconds: float = 60.0):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[T]:
        """Get a value from the cache, returning None if expired or missing."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            return entry.value

    async def set(self, key: str, value: T) -> None:
        """Set a value in the cache, evicting oldest entries if at capacity."""
        async with self._lock:
            # Evict expired entries first
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for k in expired_keys:
                del self._cache[k]

            # Evict oldest if at capacity
            while len(self._cache) >= self.maxsize:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

            self._cache[key] = CacheEntry(value, self.ttl_seconds)

    async def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all entries from the cache."""
        async with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        """Current number of entries in the cache."""
        return len(self._cache)


def cached_async(
    ttl_seconds: float = 60.0,
    maxsize: int = 128,
    key_func: Optional[Callable[..., str]] = None,
):
    """
    Decorator for caching async method results.

    Creates a per-method cache that stores results with TTL expiration.

    Args:
        ttl_seconds: Time-to-live for cache entries (default: 60 seconds)
        maxsize: Maximum cache entries (default: 128)
        key_func: Optional function to generate cache key from args.
                  If not provided, uses str representation of args.

    Example:
        >>> class MyService(BaseService):
        ...     @cached_async(ttl_seconds=300, maxsize=100)
        ...     async def get_expensive_data(self, query: str) -> dict:
        ...         # This result will be cached for 5 minutes
        ...         return await self._slow_operation(query)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = AsyncLRUCache[T](maxsize=maxsize, ttl_seconds=ttl_seconds)

        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Skip 'self' argument for instance methods
                key_args = args[1:] if args else args
                cache_key = f"{func.__name__}:{str(key_args)}:{str(sorted(kwargs.items()))}"

            # Check cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug("cache_hit", method=func.__name__, key=cache_key[:50])
                return cached_value

            # Execute and cache
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result)
            logger.debug("cache_miss", method=func.__name__, key=cache_key[:50])
            return result

        # Attach cache to wrapper for manual invalidation
        wrapper.cache = cache  # type: ignore
        wrapper.invalidate = cache.invalidate  # type: ignore
        wrapper.clear_cache = cache.clear  # type: ignore

        return wrapper

    return decorator


# ==================== Base Service ====================


class BaseService(ABC):
    """
    Abstract base class for all service classes.

    Provides common functionality:
    - Repository access
    - Structured logging with bound context
    - Configuration access
    - Callback management for progress reporting

    Subclasses should override methods to implement domain-specific logic
    while using the base infrastructure for consistency.

    Example:
        >>> class VideoService(BaseService):
        ...     async def get_by_id(self, video_id: int) -> dict:
        ...         video = await self.repository.get_video_by_id(video_id)
        ...         if not video:
        ...             raise NotFoundError("Video not found", "video", video_id)
        ...         return video
    """

    def __init__(
        self,
        repository: VideoRepository,
        callback: Optional[ServiceCallback] = None,
    ):
        """
        Initialize the service.

        Args:
            repository: VideoRepository for database operations
            callback: Optional callback for progress/failure hooks
        """
        self._repository = repository
        self._callback = callback or NullCallback()
        self._logger = structlog.get_logger(self.__class__.__name__)

    @property
    def repository(self) -> VideoRepository:
        """Access the video repository."""
        return self._repository

    @property
    def callback(self) -> ServiceCallback:
        """Access the service callback."""
        return self._callback

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Access the bound logger."""
        return self._logger

    def _get_config(self):
        """Get the fuzzbin configuration."""
        return fuzzbin.get_config()

    def _get_library_dir(self) -> Path:
        """Get the library directory for media files."""
        config = self._get_config()
        if config.library_dir:
            return config.library_dir
        # Fallback to default if not resolved
        from fuzzbin.common.config import _get_default_library_dir

        return _get_default_library_dir()

    def _get_config_dir(self) -> Path:
        """Get the config directory for database, cache, thumbnails."""
        config = self._get_config()
        if config.config_dir:
            return config.config_dir
        # Fallback to default if not resolved
        from fuzzbin.common.config import _get_default_config_dir

        return _get_default_config_dir()

    async def _report_progress(
        self,
        current: int,
        total: int,
        message: str,
    ) -> None:
        """
        Report progress via callback.

        Safe to call even if callback is not provided (uses NullCallback).
        """
        try:
            await self._callback.on_progress(current, total, message)
        except Exception as e:
            self._logger.warning("callback_progress_failed", error=str(e))

    async def _report_failure(
        self,
        error: Exception,
        context: Dict[str, Any],
    ) -> None:
        """
        Report a failure via callback.

        Safe to call even if callback is not provided (uses NullCallback).
        """
        try:
            await self._callback.on_failure(error, context)
        except Exception as e:
            self._logger.warning("callback_failure_failed", error=str(e))

    async def _report_complete(self, result: Any) -> None:
        """
        Report completion via callback.

        Safe to call even if callback is not provided (uses NullCallback).
        """
        try:
            await self._callback.on_complete(result)
        except Exception as e:
            self._logger.warning("callback_complete_failed", error=str(e))
