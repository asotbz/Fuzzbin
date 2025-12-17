"""
Example usage of rate-limited API clients.

This example demonstrates:
1. Creating rate-limited API clients from configuration
2. Making concurrent requests with rate limiting
3. Using rate and concurrency limiters directly
4. Monitoring limiter status
"""

import asyncio
from pathlib import Path

import fuzzbin
from fuzzbin.api.base_client import RateLimitedAPIClient
from fuzzbin.common.config import APIClientConfig, RateLimitConfig, ConcurrencyConfig
from fuzzbin.common.rate_limiter import RateLimiter
from fuzzbin.common.concurrency_limiter import ConcurrencyLimiter
from fuzzbin.common.logging_config import get_logger

logger = get_logger(__name__)


async def example_basic_rate_limited_client():
    """Example: Basic rate-limited API client usage."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Rate-Limited API Client")
    print("=" * 60)

    # Create a simple API client config
    config = APIClientConfig(
        name="httpbin",
        base_url="https://httpbin.org",
        rate_limit=RateLimitConfig(
            enabled=True,
            requests_per_minute=30,  # 30 requests per minute
            burst_size=5,  # Allow bursts of 5
        ),
        concurrency=ConcurrencyConfig(
            max_concurrent_requests=3  # Max 3 concurrent requests
        ),
    )

    async with RateLimitedAPIClient.from_config(config) as client:
        print(f"Created client for {config.base_url}")
        print(f"Rate limit: {config.rate_limit.requests_per_minute} req/min")
        print(f"Concurrency limit: {config.concurrency.max_concurrent_requests}")

        # Make a few requests
        print("\nMaking 5 requests...")
        for i in range(5):
            response = await client.get("/get", params={"request": i + 1})
            print(f"  Request {i + 1}: {response.status_code}")


async def example_concurrent_requests():
    """Example: Make many concurrent requests with rate limiting."""
    print("\n" + "=" * 60)
    print("Example 2: Concurrent Requests with Rate Limiting")
    print("=" * 60)

    config = APIClientConfig(
        name="httpbin",
        base_url="https://httpbin.org",
        rate_limit=RateLimitConfig(
            enabled=True,
            requests_per_second=5,  # 5 requests per second
            burst_size=10,
        ),
        concurrency=ConcurrencyConfig(
            max_concurrent_requests=5
        ),
    )

    async with RateLimitedAPIClient.from_config(config) as client:
        async def make_request(request_id: int):
            """Make a single request."""
            response = await client.get("/delay/0.1")
            return request_id, response.status_code

        # Make 20 concurrent requests
        print(f"Making 20 concurrent requests (limited to 5 req/sec)...")
        import time
        start = time.time()

        tasks = [make_request(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        elapsed = time.time() - start
        print(f"Completed {len(results)} requests in {elapsed:.2f} seconds")
        print(f"Average rate: {len(results) / elapsed:.2f} requests/second")


async def example_from_yaml_config():
    """Example: Load API client from YAML configuration."""
    print("\n" + "=" * 60)
    print("Example 3: API Client from YAML Config")
    print("=" * 60)

    # Configure fuzzbin and load config.yaml
    fuzzbin.configure(config_path=Path("config.yaml"))
    config = fuzzbin.get_config()

    if config.apis and "github" in config.apis:
        github_config = config.apis["github"]
        print(f"Loaded GitHub API config:")
        print(f"  Base URL: {github_config.base_url}")
        print(f"  Rate limit: {github_config.rate_limit.requests_per_hour} req/hour")
        print(f"  Concurrency: {github_config.concurrency.max_concurrent_requests}")

        # Note: This example doesn't actually call GitHub API
        # (would need authentication)
        print("\n(Skipping actual GitHub API calls - auth required)")
    else:
        print("GitHub API config not found in config.yaml")


async def example_manual_limiters():
    """Example: Using rate and concurrency limiters directly."""
    print("\n" + "=" * 60)
    print("Example 4: Manual Rate and Concurrency Limiters")
    print("=" * 60)

    # Create limiters manually
    rate_limiter = RateLimiter(requests_per_second=2, burst_size=5)
    concurrency_limiter = ConcurrencyLimiter(max_concurrent=3)

    print("Created manual limiters:")
    print(f"  Rate: 2 req/sec, burst: 5")
    print(f"  Concurrency: 3 max concurrent")

    async def limited_operation(op_id: int):
        """Perform an operation with both limiters."""
        # Wait for rate limit
        await rate_limiter.acquire()
        
        # Limit concurrency
        async with concurrency_limiter:
            print(f"  Operation {op_id}: Running "
                  f"(active: {concurrency_limiter.get_active_count()})")
            await asyncio.sleep(0.5)  # Simulate work

    print("\nRunning 10 operations with limiters...")
    import time
    start = time.time()

    await asyncio.gather(*[limited_operation(i) for i in range(10)])

    elapsed = time.time() - start
    print(f"Completed in {elapsed:.2f} seconds")


async def example_try_acquire():
    """Example: Non-blocking try_acquire for rate limiting."""
    print("\n" + "=" * 60)
    print("Example 5: Non-blocking Rate Limiting")
    print("=" * 60)

    limiter = RateLimiter(requests_per_second=2, burst_size=3)

    print("Attempting rapid-fire requests with try_acquire...")
    
    successful = 0
    skipped = 0

    for i in range(10):
        if await limiter.try_acquire():
            successful += 1
            print(f"  Request {i + 1}: Sent")
        else:
            skipped += 1
            print(f"  Request {i + 1}: Skipped (rate limited)")

    print(f"\nSuccessful: {successful}, Skipped: {skipped}")
    print("Waiting for rate limit to reset...")
    await asyncio.sleep(2)
    
    # Try again
    if await limiter.try_acquire():
        print("After wait: Request successful!")


async def example_monitoring_limiters():
    """Example: Monitoring limiter status."""
    print("\n" + "=" * 60)
    print("Example 6: Monitoring Limiter Status")
    print("=" * 60)

    rate_limiter = RateLimiter(requests_per_second=5, burst_size=10)
    concurrency_limiter = ConcurrencyLimiter(max_concurrent=5)

    print("Initial status:")
    print(f"  Available tokens: {rate_limiter.get_available_tokens():.2f}")
    print(f"  Available slots: {concurrency_limiter.get_available_slots()}")

    # Use some capacity
    await rate_limiter.acquire(tokens=3)
    async with concurrency_limiter:
        print("\nAfter acquiring:")
        print(f"  Available tokens: {rate_limiter.get_available_tokens():.2f}")
        print(f"  Available slots: {concurrency_limiter.get_available_slots()}")
        print(f"  Active operations: {concurrency_limiter.get_active_count()}")

    print("\nAfter releasing:")
    print(f"  Available tokens: {rate_limiter.get_available_tokens():.2f}")
    print(f"  Available slots: {concurrency_limiter.get_available_slots()}")


async def main():
    """Run all examples."""
    # Configure logging
    fuzzbin.configure()

    print("=" * 60)
    print("Rate-Limited API Client Examples")
    print("=" * 60)

    try:
        await example_basic_rate_limited_client()
        await example_concurrent_requests()
        await example_from_yaml_config()
        await example_manual_limiters()
        await example_try_acquire()
        await example_monitoring_limiters()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        logger.error("examples_failed", error=str(e), error_type=type(e).__name__)
        print(f"\nExamples failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
