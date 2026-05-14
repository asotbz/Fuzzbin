# Copilot Instructions for Fuzzbin

Fuzzbin is a full-stack music video library organizer: a Python 3.9+ / FastAPI backend (`fuzzbin/`) plus a React 19 + TypeScript + Vite frontend (`frontend/`). The two communicate over REST (OpenAPI at `/openapi.json`) and a WebSocket event bus at `/ws/events`.

## Build, test, lint

Backend (run from repo root, inside the `.venv`):

```bash
pip install -e ".[dev]"

# Lint + format check (what CI runs — see .github/workflows/backend.yml)
ruff check fuzzbin tests
ruff format --check fuzzbin tests

# Full test suite (coverage flags come from pyproject.toml addopts)
pytest

# Single test / module / marker
pytest tests/unit/test_database.py
pytest tests/unit/test_database.py::TestSomething::test_case
pytest -m "not slow and not live"   # markers: slow, integration, unit, live, database
```

CI deselects two `live`/network tests (`tests/integration/test_live_workflow.py::test_minimal_state_machine_workflow`, `tests/integration/test_ytdlp_integration.py::TestYTDLPIntegration::test_download_real` and `test_search_then_download`); skip them locally too unless you have credentials and network.

`pytest-asyncio` is in `auto` mode — do not decorate async tests with `@pytest.mark.asyncio`.

Setting `FUZZBIN_API_JWT_SECRET=test-secret-key-for-ci` is required for tests that boot the API.

Frontend (run from `frontend/`):

```bash
npm ci
npm run lint              # ESLint
npm run type-check        # tsc -b
npm test                  # Vitest watch
npm run test:run          # Vitest single run
npm run test:run -- src/lib/__tests__/foo.test.ts   # single file
npm run test:e2e          # Playwright — needs backend on :8000 and frontend on :5173
npm run build             # tsc -b && vite build
npm run generate-types    # regenerate src/lib/api/generated.ts from ../docs/openapi.json
```

After changing backend request/response schemas, re-run `npm run generate-types`; the frontend imports from `src/lib/api/generated.ts`.

## High-level architecture

- **Backend entry point** is `fuzzbin.web.main:run` (installed as the `fuzzbin-api` console script). It builds the FastAPI app, initializes the event bus (`fuzzbin/core/event_bus.py`), the job queue (`fuzzbin/tasks/queue.py`), registers job handlers (`fuzzbin/tasks/handlers.py`), and mounts routes from `fuzzbin/web/routes/`.
- **Async-first**: SQLite via `aiosqlite` (`fuzzbin/core/db/`), HTTP via `httpx` + `hishel` caching (`fuzzbin/common/http_client.py`), and `asyncio` throughout. There is no sync code path — repositories, services, and handlers are all `async def`.
- **Layering** (top → bottom):
  - `fuzzbin/web/routes/` — thin FastAPI routers; depend on `fuzzbin/web/dependencies.py` for auth/config/repo injection. Pydantic schemas live in `fuzzbin/web/schemas/`.
  - `fuzzbin/services/` — business logic (videos, search, imports, enrichment, backups, tags). Routes should call services, not repositories directly.
  - `fuzzbin/workflows/` — multi-step orchestrations (e.g., NFO and Spotify importers) typically invoked as background jobs.
  - `fuzzbin/tasks/` — job queue, `Job` / `JobType` models, handlers, and metrics. Long-running work (downloads, scans, imports, backups, exports) **must** go through the job queue so it surfaces on `/ws/events`.
  - `fuzzbin/clients/` — process-spawning clients (`ytdlp_client`, `ffprobe_client`, `ffmpeg_client`).
  - `fuzzbin/api/` — outbound API clients (IMVDb, Discogs, MusicBrainz, Spotify, plus `base_client` and `spotify_auth`).
  - `fuzzbin/parsers/` — parsers for client responses and NFO files.
  - `fuzzbin/core/` — DB, event bus, file manager, organizer, exceptions.
  - `fuzzbin/auth/` — JWT, OIDC, password hashing, throttle.
  - `fuzzbin/common/` — config, config manager, HTTP client, rate/concurrency limiters, string utils, logging setup.
- **Real-time updates**: emit job state changes through the singleton event bus (`get_event_bus()` / `init_event_bus()`). Progress events are debounced (~250 ms); terminal events (completed/failed/cancelled) bypass debouncing. WebSocket clients connect to `/ws/events` (first-message auth — see `docs/websocket-spec.md`).
- **Configuration** is two-tier: a `Config` Pydantic model loaded from `config.yaml` plus a runtime `ConfigManager` (in `fuzzbin/common/config_manager.py`) that handles PATCH `/config`, history, undo/redo, and reloading API clients. Every config field has a `ConfigSafetyLevel` (`safe`, `requires_reload`, `affects_state`) — when adding fields, register the appropriate safety level via `get_safety_level`.
- **Paths** resolve from `config_dir` (config, `fuzzbin.db`, caches, thumbnails, backups) and `library_dir` (media, NFO, `.trash`). Defaults: `~/Fuzzbin/{config,music_videos}`, or `/config` and `/music_videos` when `FUZZBIN_DOCKER=1`. Override with `FUZZBIN_CONFIG_DIR` / `FUZZBIN_LIBRARY_DIR`.
- **Frontend** uses TanStack Query for server state, a WebSocket hook for live job activity, generated OpenAPI types, and feature folders under `src/features/{library,activity,settings}` plus shared `components/`, `hooks/`, `lib/`, `auth/`, `routes/`.

## Conventions specific to this codebase

- **Public package surface**: anything intended to be importable from outside its module is re-exported from `fuzzbin/__init__.py`. Prefer `from fuzzbin import X` in app/test code over deep imports when the symbol is re-exported.
- **DB access**: use `await fuzzbin.get_repository()` (or the injected repo dependency in routes) — do not open raw connections. Migrations are SQL files in `fuzzbin/core/db/migrations/` and run by `fuzzbin/core/db/migrator.py`.
- **Background work** belongs in `fuzzbin/tasks/handlers.py` keyed by `JobType`. Enqueue via the job queue so progress is broadcast and persisted; do not `asyncio.create_task` long-running work from a request handler.
- **Outbound HTTP**: go through `fuzzbin/common/http_client.py` (cached via `hishel`) and respect `RateLimiter` / `ConcurrencyLimiter` configured per API client. New API clients should subclass / mirror `fuzzbin/api/base_client.py`.
- **Logging**: `structlog.get_logger(__name__)`. Pass structured kwargs (`logger.info("event", video_id=..., status=...)`); do not f-string into the message.
- **Errors**: raise the typed exceptions in `fuzzbin/core/exceptions.py` / `fuzzbin/common/config_manager.py` rather than bare `Exception`. The web layer maps them to HTTP responses in `fuzzbin/web/middleware.py`.
- **Auth**: protect new routes with the `require_auth` dependency from `fuzzbin/web/dependencies.py`. The seeded `admin/changeme` user has `password_must_change=1` until rotated.
- **Search**: full-text search uses SQLite FTS5 with a custom query grammar (AND/OR/NOT, phrases) — go through `services/search_service.py`, not raw SQL, so facets and saved searches stay consistent.
- **Style**: Ruff (line length 100, target `py39`) is the source of truth — `ruff format` is enforced in CI. Mypy is configured with `disallow_untyped_defs = true`; add type hints on all defs.
- **Test layout**: `tests/unit/` (fast, isolated, default), `tests/integration/` (cross-module, may hit subprocess clients), `tests/api/` (FastAPI TestClient against routes). Use existing fixtures in the nearest `conftest.py`; `respx` mocks outbound `httpx` traffic. Mark slow tests with `@pytest.mark.slow` and network tests with `@pytest.mark.live`.
- **Versioning**: `setuptools-scm` derives the version from the latest `vX.Y.Z` git tag. For Docker / no-git builds set `SETUPTOOLS_SCM_PRETEND_VERSION_FOR_FUZZBIN`.

## Useful references in-repo

- `docs/openapi-spec.md`, `docs/openapi.json` — REST surface.
- `docs/websocket-spec.md` — WS message shapes and close codes.
- `docs/advanced-config.md` — per-API caching/rate limits, organizer patterns, schedules.
- `config.example.yaml` — every supported config key with comments.
