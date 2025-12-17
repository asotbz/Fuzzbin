"""API interaction layer for Fuzzbin.

This package contains API client implementations with rate limiting and
concurrency control for integrations with external services.
"""

from .base_client import RateLimitedAPIClient

__all__ = ["RateLimitedAPIClient"]
