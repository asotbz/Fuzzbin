"""Quick verification script to test the setup."""

import asyncio
from pathlib import Path

import fuzzbin
from fuzzbin.common.http_client import AsyncHTTPClient
from fuzzbin.common.logging_config import get_logger

logger = get_logger(__name__)


async def main():
    """Quick verification of the HTTP client."""
    print("=" * 60)
    print("Fuzzbin Quick Verification")
    print("=" * 60)

    # Configure with default settings
    fuzzbin.configure()
    
    print(f"\n✓ Package version: {fuzzbin.__version__}")
    print(f"✓ Configuration loaded successfully")

    # Get configuration
    config = fuzzbin.get_config()
    print(f"✓ HTTP timeout: {config.http.timeout}s")
    print(f"✓ Max retry attempts: {config.http.retry.max_attempts}")
    print(f"✓ Log level: {config.logging.level}")

    # Test HTTP client with a real API
    print("\nTesting HTTP client with httpbin.org...")
    try:
        async with AsyncHTTPClient(
            config.http,
            base_url="https://httpbin.org"
        ) as client:
            # Test GET request
            response = await client.get("/get", params={"test": "value"})
            print(f"✓ GET request successful (status: {response.status_code})")

            # Test POST request
            response = await client.post("/post", json={"message": "test"})
            print(f"✓ POST request successful (status: {response.status_code})")

            # Test status endpoint
            response = await client.get("/status/200")
            print(f"✓ Status check successful (status: {response.status_code})")

    except Exception as e:
        print(f"✗ HTTP client test failed: {e}")
        return False

    print("\n" + "=" * 60)
    print("All verification checks passed! ✓")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
