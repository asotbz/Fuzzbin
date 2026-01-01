# Fuzzbin AI Coding Agent Instructions

## Project Overview
Fuzzbin is a music video library manager with a FastAPI backend, async job queue, SQLite database, and React frontend. It provides API integrations (Discogs, IMVDb, Spotify), file organization, NFO import/export, and real-time WebSocket updates.

## Architecture

### Five-Layer Design
```
fuzzbin/
├── common/       # HTTP client, rate limiting, config, logging (shared utilities)
├── api/          # External API clients (Discogs, IMVDb, Spotify)
├── core/         # Database (SQLite/aiosqlite), event bus, file manager, organizer
├── services/     # Business logic (VideoService, SearchService, ImportService)
├── tasks/        # Background job queue with handlers for async operations
├── web/          # FastAPI routes, middleware, WebSocket, schemas
└── workflows/    # High-level orchestration (NFOImporter, SpotifyImporter)
```

### Key Data Flow
1. **Web → Services**: Routes delegate to services for business logic
2. **Services → Repository**: Services use `VideoRepository` for all DB operations
3. **Background Jobs**: Long operations use `JobQueue` → handlers → services
4. **Real-time Updates**: `EventBus` emits events → WebSocket `ConnectionManager` → clients

### Critical Components
- **VideoRepository** ([fuzzbin/core/db/](fuzzbin/core/db/)): Async SQLite with FTS5 search, soft delete, fluent query builder
- **JobQueue** ([fuzzbin/tasks/queue.py](fuzzbin/tasks/queue.py)): Priority heap with cron scheduling, max_workers concurrency
- **EventBus** ([fuzzbin/core/event_bus.py](fuzzbin/core/event_bus.py)): Debounced progress events (250ms) for WebSocket broadcast
- **RateLimitedAPIClient** ([fuzzbin/api/base_client.py](fuzzbin/api/base_client.py)): Token bucket + semaphore + Hishel caching

## Configuration

### Two Root Directories
- **config_dir**: Database, caches, thumbnails, backups (default: `~/Fuzzbin/config`)
- **library_dir**: Video files, NFO metadata, trash (default: `~/Fuzzbin/music_videos`)

### Environment Variables
```bash
FUZZBIN_CONFIG_DIR=/custom/config    # Override config_dir
FUZZBIN_LIBRARY_DIR=/custom/videos   # Override library_dir
FUZZBIN_DOCKER=1                     # Use Docker defaults (/config, /music_videos)
IMVDB_APP_KEY=xxx                    # API keys override config.yaml
DISCOGS_API_KEY=xxx / DISCOGS_API_SECRET=xxx
SPOTIFY_CLIENT_ID=xxx / SPOTIFY_CLIENT_SECRET=xxx
```

## Development Workflows

### Setup
```bash
python -m venv .venv                 # Create virtual environment
source .venv/bin/activate            # Activate venv (fish: source .venv/bin/activate.fish)
pip install -e ".[dev]"              # Install with dev dependencies
```

### Running
```bash
fuzzbin-api                          # Start FastAPI server (uvicorn)
pytest                               # Run tests with coverage
pytest tests/unit/test_discogs_client.py  # Run specific test
pytest -k "test_rate_limiter"        # Pattern matching
```

### Test Structure
- **Fixtures**: Shared in [tests/conftest.py](tests/conftest.py), module-specific in `tests/unit/conftest.py`
- **Mock HTTP**: Use `respx` library for httpx mocking
- **Async Tests**: `asyncio_mode = "auto"` in pyproject.toml (no decorator needed)
- **Database Tests**: Use `test_db` fixture which provides isolated VideoRepository

### Critical Test Pattern for API Clients
```python
@pytest.fixture(autouse=True)
def clear_api_env_vars(monkeypatch):
    """REQUIRED: Clear env vars to prevent real credentials interfering with mocks."""
    monkeypatch.delenv("DISCOGS_API_KEY", raising=False)
    monkeypatch.delenv("DISCOGS_API_SECRET", raising=False)
```

## Critical Patterns

### Service Layer Pattern
Services extend `BaseService` and receive `VideoRepository`:
```python
class VideoService(BaseService):
    def __init__(self, repository: VideoRepository, callback: Optional[ServiceCallback] = None):
        super().__init__(repository, callback)
```
- Services raise `NotFoundError`, `ValidationError`, `ConflictError` (mapped to HTTP status by routes)
- Use `ServiceCallback` protocol for progress/failure hooks in long operations

### Background Job Handler Pattern
Handlers in [fuzzbin/tasks/handlers.py](fuzzbin/tasks/handlers.py) follow this contract:
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

## Job Types Reference
Key job types in `JobType` enum ([fuzzbin/tasks/models.py](fuzzbin/tasks/models.py)):
- `IMPORT_NFO`: Import from NFO files with IMVDb/Discogs enrichment
- `IMPORT_SPOTIFY`: Import from Spotify playlist
- `DOWNLOAD_YOUTUBE`: Download video via yt-dlp
- `VIDEO_POST_PROCESS`: FFProbe analysis, thumbnail generation, organize
- `BACKUP`: Scheduled database backup
- `TRASH_CLEANUP`: Automatic trash cleanup

## Adding New Features

### New API Integration
1. Create `fuzzbin/api/{service}_client.py` extending `RateLimitedAPIClient`
2. Implement `from_config()` with env var priority
3. Add config section to `config.example.yaml` under `apis.{service}`
4. Create parser in `fuzzbin/parsers/` for response models
5. Add tests in `tests/unit/test_{service}_client.py`
6. Export in `fuzzbin/__init__.py`

### New Background Job
1. Add to `JobType` enum in [fuzzbin/tasks/models.py](fuzzbin/tasks/models.py)
2. Create handler function in [fuzzbin/tasks/handlers.py](fuzzbin/tasks/handlers.py)
3. Register in `register_all_handlers()` function
4. Add API endpoint in appropriate route file to submit jobs

### New Service
1. Create `fuzzbin/services/{name}_service.py` extending `BaseService`
2. Inject via FastAPI dependency in `fuzzbin/web/dependencies.py`
3. Use in routes, never call repository directly from routes

## Frontend (React/TypeScript)

### Stack
- **Vite** build system with React 19
- **TanStack Query** for server state management
- **React Router** v7 for routing
- **Vitest** + Testing Library for unit tests, **Playwright** for E2E

### Commands
```bash
cd frontend
npm run dev              # Start dev server (HMR)
npm run build            # Type-check + production build
npm run test             # Run Vitest in watch mode
npm run test:e2e         # Run Playwright E2E tests
npm run generate-types   # Generate API types from OpenAPI spec
```

### Type Generation
API types are generated from [docs/openapi.json](docs/openapi.json):
```bash
./utils/generate_openapi_docs.sh  # Regenerate OpenAPI spec from FastAPI app
npm run generate-types            # Creates src/lib/api/generated.ts
```

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

## CLI Tools

### Password Reset
```bash
fuzzbin-user set-password -u admin       # Interactive password prompt
fuzzbin-user set-password -u admin -p newpass  # Direct password set
fuzzbin-user list                        # List all users
```

## Database Migrations

Migrations are in [fuzzbin/core/db/migrations/](fuzzbin/core/db/migrations/) as numbered SQL files:
- `001_initial_schema.sql` - Core tables (videos, artists, albums, directors)
- `002_create_fts_index.sql` - FTS5 full-text search
- `004_add_users.sql` - Authentication tables
- Migrations run automatically on startup

## WebSocket Events

Real-time job progress uses WebSocket. See [docs/websocket-spec.md](docs/websocket-spec.md) for:
- Connection endpoint and authentication
- Event types (`job.progress`, `job.completed`, `job.failed`)
- Message payload schemas

## Logging Standards
- Logger: `logger = structlog.get_logger(__name__)`
- Events: `snake_case` (e.g., `"job_started"`, `"request_complete"`)
- Context binding: `logger.bind(job_id=job.id, video_id=123)`

## Common Pitfalls
- **Clear env vars in tests**: API client tests MUST clear credential env vars
- **Unique cache databases**: Each API needs separate SQLite file in `.cache/`
- **Don't retry auth errors**: Exclude 401/403/404 from `retry.status_codes`
- **Async context managers**: Both `rate_limiter` and `concurrency_limiter` require `async with`
- **Repository via fuzzbin module**: Use `await fuzzbin.get_repository()`, not direct instantiation
