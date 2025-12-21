"""Unit tests for the service layer base classes."""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from fuzzbin.services.base import (
    AsyncLRUCache,
    BaseService,
    CacheEntry,
    ConflictError,
    NotFoundError,
    NullCallback,
    ServiceCallback,
    ServiceError,
    ValidationError,
    cached_async,
)


# ==================== Exception Tests ====================


class TestServiceExceptions:
    """Tests for service-specific exceptions."""

    def test_service_error_basic(self):
        """Test ServiceError with message only."""
        error = ServiceError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.details == {}

    def test_service_error_with_details(self):
        """Test ServiceError with details dict."""
        error = ServiceError("Failed", details={"code": 500, "reason": "timeout"})
        assert error.message == "Failed"
        assert error.details == {"code": 500, "reason": "timeout"}

    def test_validation_error(self):
        """Test ValidationError with field."""
        error = ValidationError("Title is required", field="title")
        assert error.field == "title"
        assert error.details["field"] == "title"

    def test_not_found_error(self):
        """Test NotFoundError with resource info."""
        error = NotFoundError(
            "Video not found",
            resource_type="video",
            resource_id=123,
        )
        assert error.resource_type == "video"
        assert error.resource_id == 123
        assert error.details["resource_type"] == "video"
        assert error.details["resource_id"] == 123

    def test_conflict_error(self):
        """Test ConflictError with conflicting ID."""
        error = ConflictError(
            "Duplicate video",
            conflicting_id=456,
            path="/media/video.mp4",
        )
        assert error.conflicting_id == 456
        assert error.details["conflicting_id"] == 456
        assert error.details["path"] == "/media/video.mp4"


# ==================== Callback Tests ====================


class TestNullCallback:
    """Tests for NullCallback (no-op implementation)."""

    @pytest.mark.asyncio
    async def test_on_progress_does_nothing(self):
        """Test that on_progress completes without error."""
        callback = NullCallback()
        await callback.on_progress(1, 10, "Processing...")
        # No assertion - just verify it doesn't raise

    @pytest.mark.asyncio
    async def test_on_failure_does_nothing(self):
        """Test that on_failure completes without error."""
        callback = NullCallback()
        await callback.on_failure(ValueError("test"), {"key": "value"})
        # No assertion - just verify it doesn't raise

    @pytest.mark.asyncio
    async def test_on_complete_does_nothing(self):
        """Test that on_complete completes without error."""
        callback = NullCallback()
        await callback.on_complete({"result": "success"})
        # No assertion - just verify it doesn't raise


class TestServiceCallbackProtocol:
    """Tests for ServiceCallback protocol implementation."""

    def test_null_callback_implements_protocol(self):
        """Test that NullCallback implements ServiceCallback protocol."""
        callback = NullCallback()
        assert isinstance(callback, ServiceCallback)

    def test_custom_callback_implements_protocol(self):
        """Test that custom callbacks can implement the protocol."""

        class MyCallback:
            async def on_progress(self, current: int, total: int, message: str) -> None:
                pass

            async def on_failure(self, error: Exception, context: Dict[str, Any]) -> None:
                pass

            async def on_complete(self, result: Any) -> None:
                pass

        callback = MyCallback()
        assert isinstance(callback, ServiceCallback)


# ==================== Cache Tests ====================


class TestCacheEntry:
    """Tests for CacheEntry."""

    def test_entry_not_expired_immediately(self):
        """Test that new entries are not expired."""
        entry = CacheEntry(value="test", ttl_seconds=60.0)
        assert not entry.is_expired()
        assert entry.value == "test"

    def test_entry_expires_after_ttl(self):
        """Test that entries expire after TTL."""
        entry = CacheEntry(value="test", ttl_seconds=0.0)
        # With 0 TTL, should be immediately expired
        assert entry.is_expired()


class TestAsyncLRUCache:
    """Tests for AsyncLRUCache."""

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self):
        """Test that cache miss returns None."""
        cache = AsyncLRUCache[str](maxsize=10, ttl_seconds=60.0)
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_returns_value(self):
        """Test that cache hit returns stored value."""
        cache = AsyncLRUCache[str](maxsize=10, ttl_seconds=60.0)
        await cache.set("key", "value")
        result = await cache.get("key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_cache_invalidate_removes_key(self):
        """Test that invalidate removes specific key."""
        cache = AsyncLRUCache[str](maxsize=10, ttl_seconds=60.0)
        await cache.set("key", "value")
        await cache.invalidate("key")
        result = await cache.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_clear_removes_all(self):
        """Test that clear removes all entries."""
        cache = AsyncLRUCache[str](maxsize=10, ttl_seconds=60.0)
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        assert cache.size == 2

        await cache.clear()
        assert cache.size == 0
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_cache_evicts_oldest_at_capacity(self):
        """Test that oldest entries are evicted at capacity."""
        cache = AsyncLRUCache[str](maxsize=2, ttl_seconds=60.0)
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")  # Should evict key1

        assert cache.size == 2
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"

    @pytest.mark.asyncio
    async def test_cache_returns_none_for_expired(self):
        """Test that expired entries return None."""
        cache = AsyncLRUCache[str](maxsize=10, ttl_seconds=0.0)
        await cache.set("key", "value")
        # With 0 TTL, should be immediately expired
        result = await cache.get("key")
        assert result is None


class TestCachedAsyncDecorator:
    """Tests for @cached_async decorator."""

    @pytest.mark.asyncio
    async def test_decorator_caches_result(self):
        """Test that decorator caches function results."""
        call_count = 0

        class TestClass:
            @cached_async(ttl_seconds=60.0, maxsize=10)
            async def expensive_method(self, arg: str) -> str:
                nonlocal call_count
                call_count += 1
                return f"result_{arg}"

        obj = TestClass()
        result1 = await obj.expensive_method("test")
        result2 = await obj.expensive_method("test")

        assert result1 == "result_test"
        assert result2 == "result_test"
        assert call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_decorator_different_args_cache_separately(self):
        """Test that different arguments cache separately."""
        call_count = 0

        class TestClass:
            @cached_async(ttl_seconds=60.0, maxsize=10)
            async def method(self, arg: str) -> str:
                nonlocal call_count
                call_count += 1
                return f"result_{arg}"

        obj = TestClass()
        await obj.method("a")
        await obj.method("b")
        await obj.method("a")  # Should be cached

        assert call_count == 2  # Called for "a" and "b", third call cached

    @pytest.mark.asyncio
    async def test_decorator_exposes_cache_methods(self):
        """Test that decorator exposes cache control methods."""

        class TestClass:
            @cached_async(ttl_seconds=60.0, maxsize=10)
            async def method(self) -> str:
                return "value"

        obj = TestClass()
        await obj.method()

        # Should have cache attribute
        assert hasattr(obj.method, "cache")
        assert hasattr(obj.method, "clear_cache")


# ==================== BaseService Tests ====================


class ConcreteService(BaseService):
    """Concrete implementation of BaseService for testing."""

    async def do_work(self, value: int) -> int:
        return value * 2


@pytest.fixture
def mock_repository():
    """Mock VideoRepository for testing."""
    repository = AsyncMock()
    repository.query = MagicMock(return_value=AsyncMock())
    return repository


class TestBaseService:
    """Tests for BaseService."""

    def test_init_with_repository_only(self, mock_repository):
        """Test initialization with repository only."""
        service = ConcreteService(repository=mock_repository)
        assert service.repository is mock_repository
        assert isinstance(service.callback, NullCallback)

    def test_init_with_callback(self, mock_repository):
        """Test initialization with custom callback."""
        callback = NullCallback()
        service = ConcreteService(repository=mock_repository, callback=callback)
        assert service.callback is callback

    def test_repository_property(self, mock_repository):
        """Test repository property access."""
        service = ConcreteService(repository=mock_repository)
        assert service.repository is mock_repository

    def test_logger_property(self, mock_repository):
        """Test logger property access."""
        service = ConcreteService(repository=mock_repository)
        assert service.logger is not None

    @pytest.mark.asyncio
    async def test_report_progress_uses_callback(self, mock_repository):
        """Test that _report_progress calls callback."""
        callback = AsyncMock()
        callback.on_progress = AsyncMock()
        service = ConcreteService(repository=mock_repository, callback=callback)

        await service._report_progress(1, 10, "Processing...")
        callback.on_progress.assert_called_once_with(1, 10, "Processing...")

    @pytest.mark.asyncio
    async def test_report_progress_handles_callback_error(self, mock_repository):
        """Test that _report_progress handles callback errors gracefully."""
        callback = AsyncMock()
        callback.on_progress = AsyncMock(side_effect=Exception("callback error"))
        service = ConcreteService(repository=mock_repository, callback=callback)

        # Should not raise
        await service._report_progress(1, 10, "Processing...")

    @pytest.mark.asyncio
    async def test_report_failure_uses_callback(self, mock_repository):
        """Test that _report_failure calls callback."""
        callback = AsyncMock()
        callback.on_failure = AsyncMock()
        service = ConcreteService(repository=mock_repository, callback=callback)

        error = ValueError("test error")
        context = {"key": "value"}
        await service._report_failure(error, context)
        callback.on_failure.assert_called_once_with(error, context)

    @pytest.mark.asyncio
    async def test_report_complete_uses_callback(self, mock_repository):
        """Test that _report_complete calls callback."""
        callback = AsyncMock()
        callback.on_complete = AsyncMock()
        service = ConcreteService(repository=mock_repository, callback=callback)

        result = {"success": True}
        await service._report_complete(result)
        callback.on_complete.assert_called_once_with(result)
