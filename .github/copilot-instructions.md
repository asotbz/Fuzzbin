# Fuzzbin AI Coding Agent Instructions

## Project Overview
Fuzzbin is a production-ready async HTTP client library with automatic retry logic, rate limiting, response caching, and structured logging. It's designed for building robust API integrations with external services (Discogs, IMVDb, etc.).

## Architecture

### Three-Layer Design
1. **Common Layer** (`src/fuzzbin/common/`): Core HTTP client with retry logic, rate limiting, concurrency control, and caching
2. **API Layer** (`src/fuzzbin/api/`): Service-specific clients extending `RateLimitedAPIClient`
3. **Configuration** (`config.yaml`): Centralized YAML config with per-API settings

### Key Components
- **AsyncHTTPClient**: Base HTTP client with tenacity-based retry logic (retries 5xx + 408/429, skips other 4xx)
- **RateLimitedAPIClient**: Extends AsyncHTTPClient with token bucket rate limiting and semaphore-based concurrency control
- **Caching**: Uses Hishel with per-API SQLite databases (see `cache_config` in config.yaml)
- **Config System**: Pydantic models with YAML loading and env var overrides (pattern: `{SERVICE}_API_KEY` env vars take precedence)

## Development Workflows

### Running Tests
```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/unit/test_discogs_client.py

# Run tests matching pattern
pytest -k "test_rate_limiter"

# Run with coverage report
pytest --cov=fuzzbin --cov-report=html
```

### Verification
```bash
# Quick sanity check (tests httpbin.org)
python verify.py
```

### Building
```bash
# Install in development mode
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"
```

## Critical Patterns

### API Client Creation Pattern
All API clients follow this inheritance pattern:
1. Extend `RateLimitedAPIClient` (never `AsyncHTTPClient` directly)
2. Implement `from_config(cls, config: APIClientConfig)` class method
3. Extract credentials from env vars (priority) OR config.custom dict
4. Example: [imvdb_client.py](../src/fuzzbin/api/imvdb_client.py#L90-L145), [discogs_client.py](../src/fuzzbin/api/discogs_client.py#L112-L155)

### Environment Variable Override Convention
- Service-specific env vars ALWAYS override config.yaml values
- Pattern: `{SERVICE}_API_KEY`, `{SERVICE}_API_SECRET`
- Example: `IMVDB_APP_KEY`, `DISCOGS_API_KEY`, `DISCOGS_API_SECRET`
- See [imvdb_client.py](../src/fuzzbin/api/imvdb_client.py#L67-L70)

### Request Context Flow
```python
# Rate limiter → Concurrency limiter → HTTP retry logic → Cache
async with client.rate_limiter:      # Token bucket
    async with client.concurrency_limiter:  # Semaphore
        response = await client._request(...)  # Tenacity retries + Hishel cache
```

### Configuration Hierarchy
- Global `http` config in config.yaml
- Per-API overrides in `apis.{service}.http`
- Caching per-API: `apis.{service}.cache` with isolated SQLite DBs
- See [config.yaml](../config.yaml#L74-L245) for examples

### Retry Logic Specifics
- Retries: Network errors + status codes in `retry.status_codes` list
- Default retries: `[408, 429, 500, 502, 503, 504]`
- Custom per-API: See Discogs/IMVDb configs excluding 403/404 from retries
- Implementation: [http_client.py](../src/fuzzbin/common/http_client.py#L158-L215)

## Testing Conventions

### Test Structure
- **Fixtures**: Shared in [tests/conftest.py](../tests/conftest.py), per-module in `tests/unit/conftest.py`
- **Mock HTTP**: Use `respx` library, pattern in [test_discogs_client.py](../tests/unit/test_discogs_client.py#L70-L100)
- **Real Response Files**: JSON examples in `examples/` directory (e.g., `discogs_search_response.json`)
- **Async Tests**: Mark with `@pytest.mark.asyncio`, fixtures with `@pytest_asyncio.fixture`

### Test Organization
- Group related tests in classes: `class TestDiscogsClient`
- Test names: `test_{method_name}_{scenario}` (e.g., `test_from_config`)
- Test env overrides: Use `monkeypatch` fixture, see [test_discogs_client.py](../tests/unit/test_discogs_client.py#L88-L93)

### Coverage Expectations
- Target: High coverage for common/ and api/ layers
- Exclude: `__pycache__`, `conftest.py` (see [pyproject.toml](../pyproject.toml#L54-L55))
- HTML report: `htmlcov/index.html`

## Logging Standards

### Structured Logging with Structlog
- Use JSON format in production, text in development
- Logger creation: `logger = structlog.get_logger(__name__)`
- Event naming: `snake_case` with context (e.g., `"rate_limiter_initialized"`, `"request_complete"`)
- Bind context: `logger.bind(user_id=123)` for request tracing
- Example: [rate_limiter.py](../src/fuzzbin/common/rate_limiter.py#L79-L82)

### Third-Party Log Levels
- Configure in config.yaml `logging.third_party`
- httpx/httpcore: WARNING (reduce noise)
- tenacity: INFO (see retry attempts)

## Adding New API Integrations

1. **Create client class** in `src/fuzzbin/api/{service}_client.py`
2. **Extend RateLimitedAPIClient** with service-specific methods
3. **Add config section** to config.yaml under `apis.{service}`
4. **Environment variables**: Document in docstring, implement in `__init__`
5. **Auth headers**: Set in `auth_headers` dict, passed to parent `__init__`
6. **Rate limits**: Research API docs, configure `rate_limit` section
7. **Cache settings**: Consider data freshness, set `cache.ttl` appropriately
8. **Tests**: Create `test_{service}_client.py`, use example JSON responses
9. **Export**: Add to `__all__` in [__init__.py](../src/fuzzbin/__init__.py)

## Common Pitfalls

- **Don't call AsyncHTTPClient directly for APIs**: Always use RateLimitedAPIClient for proper rate limiting
- **Cache databases must be unique**: Each API needs its own SQLite file to avoid conflicts
- **Context managers required**: Both rate_limiter and concurrency_limiter use `async with`
- **Retry status codes**: Don't include auth errors (401/403) or not found (404) in retry lists
- **User-Agent required**: Some APIs (Discogs) require User-Agent header with contact info
