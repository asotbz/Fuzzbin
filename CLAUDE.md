# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fuzzbin is a music video library manager with a FastAPI backend (async Python), SQLite database, background job queue, and React frontend. It provides API integrations (Discogs, IMVDb, Spotify), file organization, NFO import/export, and real-time WebSocket updates.

## Essential Commands

### Backend (Python)

```bash
# Setup
python -m venv .venv
source .venv/bin/activate            # Fish: source .venv/bin/activate.fish
pip install -e ".[dev]"              # Install with dev dependencies

# Running
fuzzbin-api                          # Start FastAPI server

# Testing
pytest                               # Run all tests with coverage
pytest tests/unit/test_discogs_client.py  # Run specific test file
pytest -k "test_rate_limiter"        # Run tests matching pattern
pytest -m "not live"                 # Exclude tests marked with @pytest.mark.live

# Code Quality
black src/ tests/                    # Format code
ruff check src/ tests/               # Lint
mypy src/                            # Type check
```

### Frontend (React/TypeScript)

```bash
cd frontend

# Setup
npm install

# Development
npm run dev                          # Start dev server with HMR
npm run build                        # Type-check + production build
npm run type-check                   # TypeScript check only

# Testing
npm run test                         # Vitest in watch mode
npm run test:run                     # Run tests once
npm run test:coverage                # Run with coverage
npm run test:e2e                     # Playwright E2E tests
npm run test:e2e:ui                  # Playwright UI mode

# API Types
./utils/generate_openapi_docs.sh     # Regenerate OpenAPI spec from backend
npm run generate-types               # Generate TypeScript types from OpenAPI
```

### CLI Tools

```bash
fuzzbin-user set-password -u admin   # Reset user password (interactive)
fuzzbin-user list                    # List all users
```

## Architecture

### Five-Layer Backend Design

```
fuzzbin/
├── common/       # Shared utilities (HTTP client, rate limiting, config, logging)
├── api/          # External API clients (Discogs, IMVDb, Spotify)
├── core/         # Core infrastructure (SQLite/aiosqlite, event bus, file manager, organizer)
├── services/     # Business logic (VideoService, SearchService, ImportService)
├── tasks/        # Background job queue with handlers
├── web/          # FastAPI routes, middleware, WebSocket, schemas
└── workflows/    # High-level orchestration (NFOImporter, SpotifyImporter)
```

### Critical Data Flow

1. **Web → Services**: Routes delegate to services for all business logic
2. **Services → Repository**: Services use `VideoRepository` for ALL database operations (never call repository directly from routes)
3. **Background Jobs**: Long operations use `JobQueue` → handlers → services
4. **Real-time Updates**: `EventBus` emits events → WebSocket `ConnectionManager` → clients

### Key Components

- **VideoRepository** (`fuzzbin/core/db/repository.py`): Async SQLite with FTS5 full-text search, soft delete, fluent query builder
- **JobQueue** (`fuzzbin/tasks/queue.py`): Priority heap with cron scheduling, max_workers concurrency control
- **EventBus** (`fuzzbin/core/event_bus.py`): Debounced progress events (250ms) for WebSocket broadcast
- **RateLimitedAPIClient** (`fuzzbin/api/base_client.py`): Token bucket + semaphore + Hishel HTTP caching

## Configuration

### Two Root Directories

- **config_dir**: Database, caches, thumbnails, backups (default: `~/Fuzzbin/config`)
- **library_dir**: Video files, NFO metadata, trash (default: `~/Fuzzbin/music_videos`)

### Environment Variables

```bash
FUZZBIN_CONFIG_DIR=/custom/config    # Override config_dir
FUZZBIN_LIBRARY_DIR=/custom/videos   # Override library_dir
FUZZBIN_DOCKER=1                     # Use Docker defaults (/config, /music_videos)

# API credentials (override config.yaml)
IMVDB_APP_KEY=xxx
DISCOGS_API_KEY=xxx
DISCOGS_API_SECRET=xxx
SPOTIFY_CLIENT_ID=xxx
SPOTIFY_CLIENT_SECRET=xxx
```

## Critical Development Patterns

### Service Layer Pattern

Services extend `BaseService` and receive `VideoRepository`:

```python
class VideoService(BaseService):
    def __init__(self, repository: VideoRepository, callback: Optional[ServiceCallback] = None):
        super().__init__(repository, callback)
```

- Services raise domain exceptions: `NotFoundError`, `ValidationError`, `ConflictError`
- Routes map these to HTTP status codes
- Use `ServiceCallback` protocol for progress/failure hooks in long operations

### Background Job Handler Pattern

Handlers in `fuzzbin/tasks/handlers.py` follow this contract:

```python
async def handle_xxx(job: Job) -> None:
    """
    1. Read params from job.metadata
    2. Call job.update_progress(current, total, message) periodically
    3. Check job.status for cancellation
    4. Call job.mark_completed(result) on success
    5. Raise exception on failure (queue calls job.mark_failed())
    """
```

### API Client Creation Pattern

All API clients extend `RateLimitedAPIClient`:

```python
class DiscogsClient(RateLimitedAPIClient):
    @classmethod
    def from_config(cls, config: APIClientConfig) -> "DiscogsClient":
        # 1. Check env vars first (DISCOGS_API_KEY, DISCOGS_API_SECRET)
        # 2. Fall back to config.custom dict
        # 3. Pass auth_headers to parent __init__
```

### Request Flow Through Limiters

```python
# Rate limiter → Concurrency limiter → HTTP retry → Cache
async with client.rate_limiter:           # Token bucket
    async with client.concurrency_limiter: # Semaphore
        response = await client._request(...)  # Tenacity retries + Hishel cache
```

### Repository Access Pattern

**CRITICAL**: Always use `await fuzzbin.get_repository()`, never instantiate `VideoRepository` directly. The repository is a singleton managed by the fuzzbin module.

## Testing Patterns

### Fixtures

- Shared fixtures in `tests/conftest.py`
- Module-specific fixtures in `tests/unit/conftest.py` or `tests/api/conftest.py`
- Use `test_db` fixture for isolated VideoRepository instances
- Async tests run automatically (no `@pytest.mark.asyncio` needed due to `asyncio_mode = "auto"`)

### Mocking HTTP Requests

Use `respx` library for httpx mocking:

```python
import respx
from httpx import Response

@respx.mock
async def test_api_client():
    respx.get("https://api.example.com/endpoint").mock(return_value=Response(200, json={"data": "value"}))
    # ... test code
```

### Critical Test Pattern for API Clients

**REQUIRED**: Clear environment variables to prevent real credentials from interfering with mocks:

```python
@pytest.fixture(autouse=True)
def clear_api_env_vars(monkeypatch):
    """Clear env vars to prevent real credentials interfering with mocks."""
    monkeypatch.delenv("DISCOGS_API_KEY", raising=False)
    monkeypatch.delenv("DISCOGS_API_SECRET", raising=False)
```

## Database

### Migrations

Migrations in `fuzzbin/core/db/migrations/` as numbered SQL files:
- `001_initial_schema.sql` - Complete schema including all tables, indexes, triggers, FTS5 full-text search, and seed data
- Run automatically on startup

### Full-Text Search

The repository uses SQLite FTS5 for searching. The `VideoQuery` builder provides `.where_search(query)` for full-text queries across artist, title, album, and genre fields.

## Job Types

Key background job types in `JobType` enum (`fuzzbin/tasks/models.py`):
- `IMPORT_NFO`: Import from NFO files with IMVDb/Discogs enrichment
- `IMPORT_SPOTIFY`: Import from Spotify playlist
- `DOWNLOAD_YOUTUBE`: Download video via yt-dlp
- `VIDEO_POST_PROCESS`: FFProbe analysis, thumbnail generation, organize
- `BACKUP`: Scheduled database backup
- `TRASH_CLEANUP`: Automatic trash cleanup

## Frontend Architecture

### Stack

- **Vite** build system with React 19
- **TanStack Query** for server state management
- **React Router** v7 for routing
- **Vitest** + Testing Library for unit tests
- **Playwright** for E2E tests

### Structure

```
frontend/src/
├── api/          # API client hooks (TanStack Query)
├── components/   # Reusable UI components
├── features/     # Feature-specific components
├── hooks/        # Custom React hooks
├── lib/          # Utilities and generated types
├── pages/        # Route page components
└── mocks/        # MSW handlers for testing
```

### API Type Generation

API types are generated from `docs/openapi.json`:
1. Run `./utils/generate_openapi_docs.sh` to regenerate OpenAPI spec from FastAPI app
2. Run `npm run generate-types` to create `src/lib/api/generated.ts`

## WebSocket Events

Real-time job progress uses WebSocket. Connection endpoint: `/ws`

Event types:
- `job.progress` - Job progress updates
- `job.completed` - Job completed successfully
- `job.failed` - Job failed with error

See `docs/websocket-spec.md` for full specification.

## Adding New Features

### New API Integration

1. Create `fuzzbin/api/{service}_client.py` extending `RateLimitedAPIClient`
2. Implement `from_config()` with env var priority
3. Add config section to `config.example.yaml` under `apis.{service}`
4. Create parser in `fuzzbin/parsers/` for response models
5. Add tests in `tests/unit/test_{service}_client.py`
6. Export in `fuzzbin/__init__.py`

### New Background Job

1. Add to `JobType` enum in `fuzzbin/tasks/models.py`
2. Create handler function in `fuzzbin/tasks/handlers.py`
3. Register in `register_all_handlers()` function
4. Add API endpoint in appropriate route file to submit jobs

### New Service

1. Create `fuzzbin/services/{name}_service.py` extending `BaseService`
2. Inject via FastAPI dependency in `fuzzbin/web/dependencies.py`
3. Use in routes, never call repository directly from routes

## Common Pitfalls

- **Clear env vars in tests**: API client tests MUST clear credential env vars to prevent real credentials from being used
- **Unique cache databases**: Each API needs separate SQLite file in `.cache/` (e.g., `.cache/discogs.db`, `.cache/imvdb.db`)
- **Don't retry auth errors**: Exclude 401/403/404 from `retry.status_codes` in HTTP config
- **Async context managers**: Both `rate_limiter` and `concurrency_limiter` require `async with`
- **Repository access**: Use `await fuzzbin.get_repository()`, not direct instantiation

## Logging Standards

- Logger: `logger = structlog.get_logger(__name__)`
- Events: `snake_case` (e.g., `"job_started"`, `"request_complete"`)
- Context binding: `logger.bind(job_id=job.id, video_id=123)`
