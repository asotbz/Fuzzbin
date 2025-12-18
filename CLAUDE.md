# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fuzzbin is a production-ready Python async HTTP client library with automatic retry logic, rate limiting, response caching, and structured logging. It's built on httpx and designed for robust API integrations.

## Development Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
pip install -e ".[dev]"
```

### Testing
```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/unit/test_http_client.py

# Run specific test
pytest tests/unit/test_http_client.py::test_function_name

# Run tests without coverage report
pytest --no-cov

# Run only unit tests (skip slow integration tests)
pytest -m "not slow"
```

### Code Quality
```bash
# Format code (line length: 100)
black src/ tests/

# Type checking
mypy src/

# Linting
ruff src/ tests/
```

### Running Examples
```bash
# Basic HTTP client usage
python examples/usage_example.py

# API client with rate limiting
python examples/api_client_example.py

# Response caching demonstration
python examples/cache_example.py

# IMVDb API client
python examples/imvdb_usage_example.py

# Discogs API client
python examples/discogs_usage_example.py
```

## Architecture

### Core Components

**Configuration System** (`src/fuzzbin/common/config.py`)
- Pydantic models for YAML-based configuration with validation
- `Config.from_yaml()` loads and validates configuration from YAML files
- Hierarchical config: global HTTP/logging settings + per-API client overrides
- Configuration can be loaded from `config.yaml` or programmatically via `fuzzbin.configure()`

**HTTP Client** (`src/fuzzbin/common/http_client.py`)
- `AsyncHTTPClient`: Base async HTTP client built on httpx
- Automatic retry logic with exponential backoff (configurable via `HTTPConfig.retry`)
- Smart retry strategy: retries 5xx and network errors, skips 4xx except 408/429
- Connection pooling with configurable limits
- Optional response caching via Hishel (SQLite-backed, per-client databases)
- Cache-aware: cache hits are logged and tracked via response extensions

**Rate Limiting** (`src/fuzzbin/common/rate_limiter.py`)
- Token bucket algorithm supporting per-second, per-minute, and per-hour limits
- Configurable burst size for short-term traffic spikes
- Async-safe with `await rate_limiter.acquire()`

**Concurrency Control** (`src/fuzzbin/common/concurrency_limiter.py`)
- `ConcurrencyLimiter`: Semaphore-based concurrent request limiting
- Use as async context manager: `async with concurrency_limiter:`

**API Client Base** (`src/fuzzbin/api/base_client.py`)
- `RateLimitedAPIClient`: Extends `AsyncHTTPClient` with rate limiting and concurrency control
- Cache-aware rate limiting: cache hits bypass rate limiters to preserve quota
- Automatic auth header injection via `auth_headers` parameter
- Factory method `from_config()` for creating clients from `APIClientConfig`

### Client Architecture Pattern

New API clients should extend `RateLimitedAPIClient`:

1. Override `__init__` to handle API-specific authentication (extract from env vars or config)
2. Override `from_config()` classmethod to extract custom config from `APIClientConfig.custom`
3. Add API-specific methods that call inherited HTTP methods (get/post/put/delete)
4. Use structured logging: `self.logger.info("operation_name", param=value)`

See `src/fuzzbin/api/imvdb_client.py` and `src/fuzzbin/api/discogs_client.py` for reference implementations.

### Response Caching

- Powered by Hishel library (optional dependency: `hishel[async]`)
- Each API client can have its own SQLite cache database (configured via `CacheConfig.storage_path`)
- Configurable TTL, stale-while-revalidate, cacheable methods, and status codes
- Cache hits/misses logged automatically for observability
- Cache status available in `response.extensions['from_cache']` or `response.extensions['hishel_from_cache']`
- Clear cache: `await client.clear_cache()`

### Logging

- Structured JSON logging via structlog (configurable in `config.yaml`)
- Use `format: "text"` for development, `format: "json"` for production
- Context binding: `bind_context(request_id=..., user_id=...)` adds fields to all logs in scope
- Configure via `LoggingConfig`: level, format, handlers, third-party log levels

## Configuration Structure

The `config.yaml` file has three main sections:

1. **http**: Global HTTP client settings (timeout, retries, connection limits)
2. **logging**: Logging configuration (level, format, handlers)
3. **cache**: Global cache settings (can be overridden per API)
4. **apis**: Per-API client configurations with rate limits, concurrency, auth headers, and custom fields

### API Client Configuration Pattern

Each entry in `config.yaml` under `apis.*` maps to an `APIClientConfig`:
- `name`: Identifier for the API client
- `base_url`: Base URL for all requests
- `http`: Optional HTTP config override (inherits from global if not specified)
- `rate_limit`: Rate limiting config (requests_per_second/minute/hour, burst_size)
- `concurrency`: Concurrency control (max_concurrent_requests)
- `cache`: Cache config override (enabled, storage_path, ttl, cacheable_methods/status_codes)
- `auth`: Dict of authentication headers to inject (e.g., `Authorization: "Bearer token"`)
- `custom`: API-specific configuration (e.g., API keys, model settings)

## Important Patterns

### Initialization Pattern

```python
import fuzzbin
from pathlib import Path

# Initialize package (loads config, sets up logging)
fuzzbin.configure(config_path=Path("config.yaml"))

# Or use default configuration
fuzzbin.configure()

# Get configuration
config = fuzzbin.get_config()
```

### Basic HTTP Client Usage

```python
from fuzzbin.common.http_client import AsyncHTTPClient

async with AsyncHTTPClient(config.http, base_url="https://api.example.com") as client:
    response = await client.get("/endpoint", params={"key": "value"})
    data = response.json()
```

### API Client with Rate Limiting

```python
from fuzzbin.api.base_client import RateLimitedAPIClient

# From configuration
config = fuzzbin.get_config()
api_config = config.apis["github"]  # Assumes "github" in config.yaml
async with RateLimitedAPIClient.from_config(api_config) as client:
    response = await client.get("/users/octocat")
```

### Creating New API Clients

1. Create new file in `src/fuzzbin/api/` (e.g., `myapi_client.py`)
2. Extend `RateLimitedAPIClient`
3. Handle authentication in `__init__` (check env vars first, fall back to config)
4. Override `from_config()` to extract from `config.custom`
5. Add API-specific methods that use inherited HTTP methods
6. Add configuration to `config.yaml` under `apis.myapi`
7. Add client to `src/fuzzbin/__init__.py` exports

### Environment Variable Priority

API keys and secrets should support environment variables with precedence:
1. Check environment variable first: `os.environ.get("API_KEY")`
2. Fall back to `config.custom["api_key"]` or function parameter
3. Document required env vars in docstrings

### Testing Pattern

- Unit tests in `tests/unit/` with fixtures in `conftest.py`
- Use `respx` library for mocking httpx requests
- Mark slow/integration tests: `@pytest.mark.slow` or `@pytest.mark.integration`
- Test configuration uses `Config.from_yaml_string()` for inline YAML

## Key Files

- `src/fuzzbin/__init__.py`: Package initialization, exports, `configure()` and `get_config()` functions
- `src/fuzzbin/common/config.py`: Pydantic configuration models
- `src/fuzzbin/common/http_client.py`: Base async HTTP client with retry logic and caching
- `src/fuzzbin/common/rate_limiter.py`: Token bucket rate limiter
- `src/fuzzbin/common/concurrency_limiter.py`: Semaphore-based concurrency control
- `src/fuzzbin/api/base_client.py`: Rate-limited API client base class
- `config.yaml`: Main configuration file with examples for GitHub, Stripe, OpenAI, IMVDb, Discogs APIs
