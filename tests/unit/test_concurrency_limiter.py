"""Unit tests for concurrency limiter."""

import asyncio
import pytest

from fuzzbin.common.concurrency_limiter import ConcurrencyLimiter


class TestConcurrencyLimiter:
    """Tests for ConcurrencyLimiter class."""

    @pytest.mark.asyncio
    async def test_basic_concurrency_limiting(self):
        """Test basic concurrency limiting."""
        limiter = ConcurrencyLimiter(max_concurrent=2)

        active_count = 0
        max_concurrent_seen = 0

        async def task():
            nonlocal active_count, max_concurrent_seen
            async with limiter:
                active_count += 1
                max_concurrent_seen = max(max_concurrent_seen, active_count)
                await asyncio.sleep(0.1)
                active_count -= 1

        # Run 5 tasks concurrently
        await asyncio.gather(*[task() for _ in range(5)])

        # Should never have exceeded max_concurrent
        assert max_concurrent_seen == 2

    @pytest.mark.asyncio
    async def test_get_active_count(self):
        """Test getting active operation count."""
        limiter = ConcurrencyLimiter(max_concurrent=3)

        assert limiter.get_active_count() == 0

        async with limiter:
            assert limiter.get_active_count() == 1
            
            async with limiter:
                assert limiter.get_active_count() == 2

        assert limiter.get_active_count() == 0

    @pytest.mark.asyncio
    async def test_get_available_slots(self):
        """Test getting available concurrency slots."""
        limiter = ConcurrencyLimiter(max_concurrent=5)

        assert limiter.get_available_slots() == 5

        async with limiter:
            assert limiter.get_available_slots() == 4
            
            async with limiter:
                assert limiter.get_available_slots() == 3

        assert limiter.get_available_slots() == 5

    @pytest.mark.asyncio
    async def test_try_acquire_success(self):
        """Test try_acquire when slots available."""
        limiter = ConcurrencyLimiter(max_concurrent=2)

        # Should succeed
        result = limiter.try_acquire()
        assert result is True
        assert limiter.get_active_count() == 1

        # Clean up
        limiter.release()

    @pytest.mark.asyncio
    async def test_try_acquire_failure(self):
        """Test try_acquire when no slots available."""
        limiter = ConcurrencyLimiter(max_concurrent=1)

        # First should succeed
        result = limiter.try_acquire()
        assert result is True

        # Second should fail
        result = limiter.try_acquire()
        assert result is False

        # After release, should succeed
        limiter.release()
        result = limiter.try_acquire()
        assert result is True

        # Clean up
        limiter.release()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using concurrency limiter as context manager."""
        limiter = ConcurrencyLimiter(max_concurrent=2)

        async with limiter:
            assert limiter.get_active_count() == 1

        assert limiter.get_active_count() == 0

    @pytest.mark.asyncio
    async def test_concurrent_tasks_blocking(self):
        """Test that excess tasks block until slots available."""
        limiter = ConcurrencyLimiter(max_concurrent=2)
        
        results = []
        
        async def task(task_id: int):
            async with limiter:
                results.append(("start", task_id))
                await asyncio.sleep(0.1)
                results.append(("end", task_id))

        # Start 4 tasks
        await asyncio.gather(*[task(i) for i in range(4)])

        # All tasks should complete
        starts = [r for r in results if r[0] == "start"]
        ends = [r for r in results if r[0] == "end"]
        assert len(starts) == 4
        assert len(ends) == 4

    @pytest.mark.asyncio
    async def test_invalid_max_concurrent(self):
        """Test that invalid max_concurrent raises error."""
        with pytest.raises(ValueError, match="must be at least 1"):
            ConcurrencyLimiter(max_concurrent=0)

        with pytest.raises(ValueError, match="must be at least 1"):
            ConcurrencyLimiter(max_concurrent=-1)

    @pytest.mark.asyncio
    async def test_single_slot(self):
        """Test with single concurrent slot."""
        limiter = ConcurrencyLimiter(max_concurrent=1)

        execution_order = []

        async def task(task_id: int):
            async with limiter:
                execution_order.append(task_id)
                await asyncio.sleep(0.05)

        # Tasks should execute sequentially
        await asyncio.gather(*[task(i) for i in range(3)])

        # All tasks executed
        assert len(execution_order) == 3

    @pytest.mark.asyncio
    async def test_high_concurrency(self):
        """Test with high concurrency limit."""
        limiter = ConcurrencyLimiter(max_concurrent=100)

        active_count = 0
        max_concurrent_seen = 0

        async def task():
            nonlocal active_count, max_concurrent_seen
            async with limiter:
                active_count += 1
                max_concurrent_seen = max(max_concurrent_seen, active_count)
                await asyncio.sleep(0.01)
                active_count -= 1

        # Run 50 tasks - all should run concurrently
        await asyncio.gather(*[task() for _ in range(50)])

        # Should have run with high concurrency
        assert max_concurrent_seen >= 40  # Most tasks ran concurrently
