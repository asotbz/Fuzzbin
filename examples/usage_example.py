"""
Example usage of the Fuzzbin HTTP client.

This example demonstrates:
1. Loading configuration from YAML
2. Setting up structured logging
3. Making async HTTP requests with automatic retries
4. Handling responses and errors
"""

import asyncio
from pathlib import Path

import fuzzbin
from fuzzbin.common.config import Config
from fuzzbin.common.http_client import AsyncHTTPClient
from fuzzbin.common.logging_config import get_logger, bind_context

# Get a logger for this module
logger = get_logger(__name__)


async def example_basic_usage():
    """Example: Basic HTTP client usage with default configuration."""
    logger.info("example_started", example="basic_usage")

    # Use default configuration
    config = Config()

    # Create and use the HTTP client
    async with AsyncHTTPClient(
        config.http, base_url="https://httpbin.org"
    ) as client:
        # Make a GET request
        response = await client.get("/get", params={"key": "value"})
        logger.info(
            "get_request_complete",
            status_code=response.status_code,
            url=str(response.url),
        )
        print(f"GET Response: {response.json()}")

        # Make a POST request
        response = await client.post(
            "/post",
            json={"message": "Hello from Fuzzbin!", "timestamp": "2025-12-16"},
        )
        logger.info("post_request_complete", status_code=response.status_code)
        print(f"POST Response: {response.json()}")


async def example_with_yaml_config():
    """Example: Load configuration from YAML file."""
    logger.info("example_started", example="yaml_config")

    # Load configuration from YAML file
    config_path = Path("config.yaml")
    config = Config.from_yaml(config_path)

    logger.info(
        "config_loaded",
        timeout=config.http.timeout,
        max_retries=config.http.retry.max_attempts,
    )

    async with AsyncHTTPClient(
        config.http, base_url="https://httpbin.org"
    ) as client:
        response = await client.get("/status/200")
        logger.info("status_check", status_code=response.status_code)
        print(f"Status check: {response.status_code}")


async def example_retry_behavior():
    """Example: Demonstrate retry behavior on transient failures."""
    logger.info("example_started", example="retry_behavior")

    config = Config()

    async with AsyncHTTPClient(
        config.http, base_url="https://httpbin.org"
    ) as client:
        # This endpoint returns the specified status code
        # Try a 503 (Service Unavailable) which will be retried
        try:
            # Note: httpbin.org won't actually retry, this is just to show the API
            response = await client.get("/status/503")
            logger.info("request_succeeded_after_retry", status=response.status_code)
        except Exception as e:
            logger.error("request_failed", error=str(e), error_type=type(e).__name__)
            print(f"Request failed: {e}")

        # Try a 404 (Not Found) which will NOT be retried
        response = await client.get("/status/404")
        logger.info("client_error_no_retry", status_code=response.status_code)
        print(f"Client error (no retry): {response.status_code}")


async def example_with_context_binding():
    """Example: Use context binding for request tracing."""
    logger.info("example_started", example="context_binding")

    # Bind a request ID to the logging context
    request_id = "req-12345-abc"
    bind_context(request_id=request_id, user_id=42)

    config = Config()

    async with AsyncHTTPClient(
        config.http, base_url="https://httpbin.org"
    ) as client:
        # All logs in this scope will include request_id and user_id
        response = await client.get("/get")
        logger.info(
            "user_request_complete",
            endpoint="/get",
            status=response.status_code,
        )
        print(f"Response with context: {response.status_code}")


async def example_multiple_requests():
    """Example: Make multiple concurrent requests."""
    logger.info("example_started", example="multiple_requests")

    config = Config()

    async with AsyncHTTPClient(
        config.http, base_url="https://httpbin.org"
    ) as client:
        # Make multiple requests concurrently
        tasks = [
            client.get("/get"),
            client.get("/uuid"),
            client.get("/user-agent"),
        ]

        responses = await asyncio.gather(*tasks)

        logger.info("concurrent_requests_complete", count=len(responses))

        for i, response in enumerate(responses):
            print(f"Response {i + 1}: {response.status_code}")


async def example_error_handling():
    """Example: Proper error handling with the HTTP client."""
    logger.info("example_started", example="error_handling")

    config = Config()

    async with AsyncHTTPClient(
        config.http, base_url="https://httpbin.org"
    ) as client:
        try:
            # Try to access an endpoint that doesn't exist
            response = await client.get("/this-does-not-exist")
            print(f"Unexpected success: {response.status_code}")
        except Exception as e:
            # Handle errors appropriately
            logger.warning(
                "request_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            print(f"Handled error: {type(e).__name__}: {e}")


async def main():
    """Run all examples."""
    # Configure the fuzzbin package (loads config and sets up logging)
    fuzzbin.configure(config_path=Path("config.yaml"))

    logger.info("examples_started", version=fuzzbin.__version__)

    print("=" * 60)
    print("Fuzzbin HTTP Client Examples")
    print("=" * 60)

    # Run examples
    try:
        print("\n1. Basic Usage")
        print("-" * 60)
        await example_basic_usage()

        print("\n2. YAML Configuration")
        print("-" * 60)
        await example_with_yaml_config()

        print("\n3. Retry Behavior")
        print("-" * 60)
        await example_retry_behavior()

        print("\n4. Context Binding")
        print("-" * 60)
        await example_with_context_binding()

        print("\n5. Multiple Concurrent Requests")
        print("-" * 60)
        await example_multiple_requests()

        print("\n6. Error Handling")
        print("-" * 60)
        await example_error_handling()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        logger.error("examples_failed", error=str(e), error_type=type(e).__name__)
        print(f"\nExamples failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
