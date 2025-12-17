"""Unit tests for rate limiter."""

import asyncio
import time
import pytest

from fuzzbin.common.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.mark.asyncio
    async def test_basic_rate_limiting(self):
        """Test basic rate limiting functionality."""
        # 10 requests per second
        limiter = RateLimiter(requests_per_second=10)

        start_time = time.monotonic()
        
        # Make 3 requests - should be immediate due to burst
        for _ in range(3):
            await limiter.acquire()
        
        elapsed = time.monotonic() - start_time
        # Should complete very quickly (< 0.1s)
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self):
        """Test that rate limiting actually enforces limits."""
        # 2 requests per second
        limiter = RateLimiter(requests_per_second=2, burst_size=2)

        start_time = time.monotonic()
        
        # Make 4 requests
        for _ in range(4):
            await limiter.acquire()
        
        elapsed = time.monotonic() - start_time
        
        # First 2 immediate (burst), next 2 should wait ~1 second total
        # Allow some margin for timing variations
        assert elapsed >= 0.9  # Should take at least 0.9 seconds
        assert elapsed < 1.5   # But not too long

    @pytest.mark.asyncio
    async def test_burst_size(self):
        """Test burst size configuration."""
        # 10 requests/second, but only allow burst of 3
        limiter = RateLimiter(requests_per_second=10, burst_size=3)

        start_time = time.monotonic()
        
        # First 3 should be immediate
        for _ in range(3):
            await limiter.acquire()
        
        elapsed = time.monotonic() - start_time
        assert elapsed < 0.1  # Very fast

        # 4th request should wait
        start_wait = time.monotonic()
        await limiter.acquire()
        wait_time = time.monotonic() - start_wait
        
        assert wait_time > 0.05  # Should have waited a bit

    @pytest.mark.asyncio
    async def test_requests_per_minute(self):
        """Test requests per minute configuration."""
        # 60 requests per minute = 1 per second
        limiter = RateLimiter(requests_per_minute=60, burst_size=2)

        start_time = time.monotonic()
        
        # Make 3 requests
        for _ in range(3):
            await limiter.acquire()
        
        elapsed = time.monotonic() - start_time
        
        # First 2 immediate, 3rd waits ~1 second
        assert elapsed >= 0.9
        assert elapsed < 1.5

    @pytest.mark.asyncio
    async def test_requests_per_hour(self):
        """Test requests per hour configuration (scaled down for testing)."""
        # 3600 requests per hour = 1 per second
        limiter = RateLimiter(requests_per_hour=3600, burst_size=2)

        start_time = time.monotonic()
        
        # Make 3 requests
        for _ in range(3):
            await limiter.acquire()
        
        elapsed = time.monotonic() - start_time
        
        # Similar to requests_per_minute test
        assert elapsed >= 0.9
        assert elapsed < 1.5

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using rate limiter as context manager."""
        limiter = RateLimiter(requests_per_second=10)

        start_time = time.monotonic()
        
        async with limiter:
            # Request is rate limited
            pass
        
        async with limiter:
            pass
        
        elapsed = time.monotonic() - start_time
        assert elapsed < 0.2  # Should be fast due to burst

    @pytest.mark.asyncio
    async def test_try_acquire_success(self):
        """Test try_acquire when tokens are available."""
        limiter = RateLimiter(requests_per_second=10, burst_size=5)

        # Should succeed immediately
        result = await limiter.try_acquire()
        assert result is True

        # Should succeed multiple times due to burst
        result = await limiter.try_acquire()
        assert result is True

    @pytest.mark.asyncio
    async def test_try_acquire_failure(self):
        """Test try_acquire when no tokens available."""
        limiter = RateLimiter(requests_per_second=1, burst_size=1)

        # First should succeed
        result = await limiter.try_acquire()
        assert result is True

        # Immediately after, should fail (no tokens left)
        result = await limiter.try_acquire()
        assert result is False

        # After waiting, should succeed
        await asyncio.sleep(1.1)
        result = await limiter.try_acquire()
        assert result is True

    @pytest.mark.asyncio
    async def test_get_available_tokens(self):
        """Test getting available tokens."""
        limiter = RateLimiter(requests_per_second=10, burst_size=5)

        # Initially should have burst_size tokens
        available = limiter.get_available_tokens()
        assert available == 5

        # After acquiring, should have fewer
        await limiter.acquire()
        available = limiter.get_available_tokens()
        assert 3 <= available <= 5  # May have regenerated some

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test rate limiter with concurrent requests."""
        limiter = RateLimiter(requests_per_second=5, burst_size=2)

        start_time = time.monotonic()
        
        async def make_request(request_id: int):
            await limiter.acquire()
            return request_id

        # Make 5 concurrent requests
        results = await asyncio.gather(*[make_request(i) for i in range(5)])
        
        elapsed = time.monotonic() - start_time
        
        # All requests completed
        assert len(results) == 5
        
        # Should have taken time due to rate limiting
        # First 2 immediate (burst), then 3 more at 5/sec = ~0.6s more
        assert elapsed >= 0.5

    @pytest.mark.asyncio
    async def test_multiple_tokens_acquire(self):
        """Test acquiring multiple tokens at once."""
        limiter = RateLimiter(requests_per_second=10, burst_size=10)

        # Acquire 3 tokens at once
        await limiter.acquire(tokens=3)
        
        # Should have consumed 3 tokens
        available = limiter.get_available_tokens()
        assert 6 <= available <= 8  # Allow for small regeneration

    @pytest.mark.asyncio
    async def test_no_rate_limit_error(self):
        """Test that error is raised if no rate limit specified."""
        with pytest.raises(ValueError, match="At least one rate limit"):
            RateLimiter()

    @pytest.mark.asyncio
    async def test_token_regeneration(self):
        """Test that tokens regenerate over time."""
        limiter = RateLimiter(requests_per_second=10, burst_size=5)

        # Consume all tokens
        for _ in range(5):
            await limiter.acquire()
        
        # Should have ~0 tokens
        available = limiter.get_available_tokens()
        assert available < 1

        # Wait for regeneration
        await asyncio.sleep(0.5)
        
        # Should have regenerated ~5 tokens (10/sec * 0.5sec)
        available = limiter.get_available_tokens()
        assert 4 <= available <= 5
