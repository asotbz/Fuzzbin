# Fuzzbin

A production-ready Python async HTTP client with automatic retry logic, exponential backoff, and structured logging.

## Features

- **Async HTTP Client**: Built on `httpx` for high-performance async HTTP requests
- **Automatic Retries**: Configurable retry logic with exponential backoff
- **Smart Retry Strategy**: 
  - Retries on network errors (timeouts, connection failures)
  - Retries on 5xx server errors and specific 4xx codes (408, 429)
  - Skips retries on 4xx client errors (except 408, 429)
- **YAML Configuration**: Centralized configuration with Pydantic validation
- **Structured Logging**: JSON logging with `structlog` for observability
- **Connection Pooling**: Efficient connection management with configurable limits
- **Type Safe**: Full type hints with Pydantic models

## Installation

```bash
# Install in development mode
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"
```

## Quick Start

```python
import asyncio
from pathlib import Path
import fuzzbin
from fuzzbin.common.http_client import AsyncHTTPClient

async def main():
    # Configure fuzzbin (loads config.yaml and sets up logging)
    fuzzbin.configure(config_path=Path("config.yaml"))
    
    # Get configuration
    config = fuzzbin.get_config()
    
    # Create HTTP client with automatic retries
    async with AsyncHTTPClient(
        config.http, 
        base_url="https://api.example.com"
    ) as client:
        # Make requests - retries happen automatically
        response = await client.get("/users", params={"page": 1})
        users = response.json()
        
        # POST request
        response = await client.post("/users", json={
            "name": "John Doe",
            "email": "john@example.com"
        })

asyncio.run(main())
```

## Configuration

Edit `config.yaml` to customize behavior:

```yaml
http:
  timeout: 30
  max_connections: 100
  retry:
    max_attempts: 3
    backoff_multiplier: 1.0
    min_wait: 1.0
    max_wait: 10.0
    status_codes: [408, 429, 500, 502, 503, 504]

logging:
  level: INFO
  format: json  # or "text" for development
  handlers: [console]
```

## Project Structure

```
Fuzzbin/
├── src/fuzzbin/
│   ├── __init__.py           # Package initialization
│   ├── common/               # Shared components
│   │   ├── config.py         # Pydantic configuration models
│   │   ├── http_client.py    # Async HTTP client with retries
│   │   └── logging_config.py # Structured logging setup
│   ├── api/                  # API interaction layer (future)
│   └── core/                 # Core business logic (future)
├── tests/
│   ├── conftest.py           # Shared test fixtures
│   └── unit/
│       └── test_http_client.py
├── examples/
│   └── usage_example.py      # Usage examples
├── config.yaml               # Configuration file
└── pyproject.toml            # Project metadata and dependencies
```

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=fuzzbin --cov-report=html

# Run specific test file
pytest tests/unit/test_http_client.py

# Format code
black src/ tests/

# Type checking
mypy src/
```

## Examples

See [examples/usage_example.py](examples/usage_example.py) for comprehensive examples including:

- Basic HTTP requests (GET, POST, PUT, DELETE)
- Loading configuration from YAML
- Retry behavior demonstration
- Context binding for request tracing
- Concurrent requests
- Error handling patterns

Run the examples:

```bash
python examples/usage_example.py
```

## License

MIT
