"""
Example demonstrating HTTP response caching with Hishel.

This example shows how to:
1. Enable caching for API clients
2. Configure per-API cache settings (TTL, storage)
3. Clear cache when needed
4. Monitor cache hits/misses through logging
5. Use shared cache storage across multiple APIs

Run this example:
    python examples/cache_example.py
"""

import asyncio
from pathlib import Path

import fuzzbin
from fuzzbin.common.config import (
    Config,
    APIClientConfig,
    HTTPConfig,
    CacheConfig,
    RateLimitConfig,
    ConcurrencyConfig,
)
from fuzzbin.api.base_client import RateLimitedAPIClient


async def example_basic_caching():
    """Example 1: Basic caching with default settings."""
    print("\n=== Example 1: Basic Caching ===")

    # Create cache configuration
    cache_config = CacheConfig(
        enabled=True,
        storage_path=".cache/example_cache.db",
        ttl=300,  # 5 minutes
        stale_while_revalidate=30,  # 30 seconds
    )

    # Create API client configuration with caching
    config = APIClientConfig(
        name="jsonplaceholder",
        base_url="https://jsonplaceholder.typicode.com",
        http=HTTPConfig(timeout=10),
        cache=cache_config,
    )

    async with RateLimitedAPIClient.from_config(config) as client:
        print("\n1. First request (cache miss):")
        response1 = await client.get("/posts/1")
        print(f"   Status: {response1.status_code}")
        print(f"   Title: {response1.json()['title']}")
        print(f"   From cache: {client._is_cached_response(response1)}")

        print("\n2. Second request (cache hit):")
        response2 = await client.get("/posts/1")
        print(f"   Status: {response2.status_code}")
        print(f"   Title: {response2.json()['title']}")
        print(f"   From cache: {client._is_cached_response(response2)}")

        print("\n3. Different endpoint (cache miss):")
        response3 = await client.get("/posts/2")
        print(f"   Status: {response3.status_code}")
        print(f"   Title: {response3.json()['title']}")
        print(f"   From cache: {client._is_cached_response(response3)}")


async def example_cache_clearing():
    """Example 2: Clearing the cache."""
    print("\n\n=== Example 2: Cache Clearing ===")

    cache_config = CacheConfig(
        enabled=True,
        storage_path=".cache/example_cache.db",
        ttl=3600,
    )

    config = APIClientConfig(
        name="jsonplaceholder",
        base_url="https://jsonplaceholder.typicode.com",
        http=HTTPConfig(timeout=10),
        cache=cache_config,
    )

    async with RateLimitedAPIClient.from_config(config) as client:
        print("\n1. First request:")
        response1 = await client.get("/users/1")
        print(f"   Name: {response1.json()['name']}")
        print(f"   From cache: {client._is_cached_response(response1)}")

        print("\n2. Second request (should be cached):")
        response2 = await client.get("/users/1")
        print(f"   Name: {response2.json()['name']}")
        print(f"   From cache: {client._is_cached_response(response2)}")

        print("\n3. Clearing cache...")
        await client.clear_cache()
        print("   Cache cleared!")

        print("\n4. Third request (cache was cleared, so miss):")
        response3 = await client.get("/users/1")
        print(f"   Name: {response3.json()['name']}")
        print(f"   From cache: {client._is_cached_response(response3)}")


async def example_per_api_cache_config():
    """Example 3: Different cache settings per API."""
    print("\n\n=== Example 3: Per-API Cache Configuration ===")

    # API 1: Short TTL for frequently changing data
    api1_config = APIClientConfig(
        name="comments_api",
        base_url="https://jsonplaceholder.typicode.com",
        http=HTTPConfig(timeout=10),
        cache=CacheConfig(
            enabled=True,
            storage_path=".cache/comments_api.db",
            ttl=60,  # 1 minute (frequently changing)
            stale_while_revalidate=10,
        ),
    )

    # API 2: Long TTL for stable data
    api2_config = APIClientConfig(
        name="users_api",
        base_url="https://jsonplaceholder.typicode.com",
        http=HTTPConfig(timeout=10),
        cache=CacheConfig(
            enabled=True,
            storage_path=".cache/users_api.db",
            ttl=3600,  # 1 hour (stable data)
            stale_while_revalidate=300,
        ),
    )

    print("\n1. Comments API (short TTL = 60s):")
    async with RateLimitedAPIClient.from_config(api1_config) as client1:
        response = await client1.get("/comments/1")
        print(f"   Email: {response.json()['email']}")
        print(f"   TTL: {api1_config.cache.ttl} seconds")

    print("\n2. Users API (long TTL = 3600s):")
    async with RateLimitedAPIClient.from_config(api2_config) as client2:
        response = await client2.get("/users/1")
        print(f"   Name: {response.json()['name']}")
        print(f"   TTL: {api2_config.cache.ttl} seconds")

    print("\n   Note: Each API client uses its own isolated cache database!")


async def example_cache_with_rate_limiting():
    """Example 4: Cache bypassing rate limits."""
    print("\n\n=== Example 4: Cache with Rate Limiting ===")

    config = APIClientConfig(
        name="rate_limited_api",
        base_url="https://jsonplaceholder.typicode.com",
        http=HTTPConfig(timeout=10),
        rate_limit=RateLimitConfig(
            enabled=True,
            requests_per_minute=10,  # Very low limit for demo
            burst_size=3,
        ),
        cache=CacheConfig(
            enabled=True,
            storage_path=".cache/rate_limit_cache.db",
            ttl=600,
        ),
    )

    async with RateLimitedAPIClient.from_config(config) as client:
        print("\n1. Making 5 requests for the same resource:")
        print("   (Only the first should consume rate limit quota)")

        for i in range(5):
            response = await client.get("/posts/1")
            from_cache = client._is_cached_response(response)
            tokens = client.rate_limiter.get_available_tokens() if client.rate_limiter else "N/A"
            
            print(f"\n   Request {i+1}:")
            print(f"     Title: {response.json()['title'][:50]}...")
            print(f"     From cache: {from_cache}")
            print(f"     Available rate limit tokens: {tokens}")

        print("\n   Note: Cached requests don't consume rate limit quota!")


async def example_from_config_file():
    """Example 5: Loading cache configuration from YAML."""
    print("\n\n=== Example 5: Configuration from YAML ===")

    # Load configuration from config.yaml
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("   config.yaml not found. Skipping this example.")
        return

    config = Config.from_yaml(config_path)

    # Use Discogs API configuration (which includes cache settings)
    if config.apis and "discogs" in config.apis:
        discogs_config = config.apis["discogs"]
        
        print(f"\n   Discogs API cache settings:")
        if discogs_config.cache:
            print(f"     Enabled: {discogs_config.cache.enabled}")
            print(f"     Storage: {discogs_config.cache.storage_path}")
            print(f"     TTL: {discogs_config.cache.ttl} seconds ({discogs_config.cache.ttl // 3600} hours)")
            print(f"     Stale-while-revalidate: {discogs_config.cache.stale_while_revalidate} seconds")
        else:
            print("     Cache not configured")

    # Use IMVDb API configuration (which includes cache settings)
    if config.apis and "imvdb" in config.apis:
        imvdb_config = config.apis["imvdb"]
        
        print(f"\n   IMVDb API cache settings:")
        if imvdb_config.cache:
            print(f"     Enabled: {imvdb_config.cache.enabled}")
            print(f"     Storage: {imvdb_config.cache.storage_path}")
            print(f"     TTL: {imvdb_config.cache.ttl} seconds ({imvdb_config.cache.ttl // 60} minutes)")
            print(f"     Stale-while-revalidate: {imvdb_config.cache.stale_while_revalidate} seconds")
        else:
            print("     Cache not configured")

    print("\n   Note: Each API uses its own isolated cache database!")


async def example_cache_disabled():
    """Example 6: Disabling cache for specific scenarios."""
    print("\n\n=== Example 6: Cache Disabled ===")

    # Configuration without cache
    config = APIClientConfig(
        name="no_cache_api",
        base_url="https://jsonplaceholder.typicode.com",
        http=HTTPConfig(timeout=10),
        cache=CacheConfig(enabled=False),  # Explicitly disable cache
    )

    async with RateLimitedAPIClient.from_config(config) as client:
        print("\n1. First request:")
        response1 = await client.get("/posts/1")
        print(f"   Title: {response1.json()['title']}")

        print("\n2. Second request (no caching):")
        response2 = await client.get("/posts/1")
        print(f"   Title: {response2.json()['title']}")
        print("   Each request hits the API directly (no cache)")


async def main():
    """Run all examples."""
    print("=" * 70)
    print("HTTP Response Caching Examples with Hishel")
    print("=" * 70)

    try:
        await example_basic_caching()
        await example_cache_clearing()
        await example_per_api_cache_config()
        await example_cache_with_rate_limiting()
        await example_from_config_file()
        await example_cache_disabled()

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("Examples complete!")
    print("=" * 70)
    print("\nCheck the .cache directory for the SQLite cache databases.")
    print("Run with logging enabled to see cache hit/miss events:")
    print("  FUZZBIN_LOG_LEVEL=DEBUG python examples/cache_example.py")


if __name__ == "__main__":
    asyncio.run(main())
