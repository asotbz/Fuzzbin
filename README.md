# Fuzzbin

Fuzzbin is a full-stack music video library organizer. It ingests music videos from the web and local disks, enriches metadata from multiple sources, downloads and organizes files, and serves a real-time UI for browsing, tagging, and monitoring background jobs. The Python/FastAPI backend exposes a rich API and WebSocket event stream; the React/TypeScript frontend rides on those APIs for day-to-day use.

## Highlights
- Library management: CRUD for videos, artists, tags, and collections with status history, thumbnails, Range-enabled streaming, soft-delete/trash, and permanent delete.
- Imports everywhere: multi-source search (IMVDb, Discogs, YouTube/yt-dlp), Spotify playlist import, directory/NFO scan (full or discovery mode), single-video import, bulk download, and metadata enrichment (MusicBrainz via ISRC).
- File handling: ffprobe analysis, configurable organizer path patterns, NFO generation, duplicate detection by hash/metadata, trash/restore, and library verification/repair.
- Search & discovery: SQLite FTS5 full-text search with AND/OR/NOT, facets, suggestions, and saved searches for repeatable filters.
- Background jobs with live updates: queued and scheduled jobs (downloads, imports, backups, trash cleanup, scans) broadcast over `/ws/events` with debounced progress; Activity Monitor UI listens live.
- Configuration with safety rails: runtime config PATCH with safety levels (`safe`, `requires_reload`, `affects_state`), history/undo/redo, and API client stats; YAML + env overrides for anything not in the UI.
- Backups and exports: scheduled/on-demand backups (config, DB, thumbnails), NFO regeneration, and playlist export (M3U/CSV/JSON).
- Auth & security: JWT auth with refresh cookies, login/refresh/logout, password change/rotation, and per-route protection. A seeded `admin` user ships with password `changeme`; you must change it immediately.

## Architecture
- **Backend**: Python 3.9+ FastAPI service (`fuzzbin-api`) with SQLite, background job queue, structured logging, hishel caching for outbound APIs, yt-dlp + ffprobe clients, and WebSocket event bus (`/ws/events`). OpenAPI served at `/openapi.json` (docs/openapi.json, docs/openapi-spec.md).
- **Frontend**: React + TypeScript + Vite app (`frontend/`) using TanStack Query, WebSocket hooks for job activity, and generated API types (`npm run generate-types` from docs/openapi.json). Key screens: Library (grid/table, facets, playback, bulk actions), Import Hub (search wizard, Spotify playlist, NFO scan), Activity Monitor, and Settings.
- **Paths**: `config_dir` holds config, `fuzzbin.db`, caches, thumbnails, backups; `library_dir` holds media/NFO files and `.trash`. Defaults resolve to `~/Fuzzbin/config` and `~/Fuzzbin/music_videos` (or `/config` and `/music_videos` when `FUZZBIN_DOCKER=1`).

## Prerequisites
- Python 3.9+ (3.10+ recommended) and Node.js 18+.
- ffprobe/ffmpeg and yt-dlp on PATH for analysis, thumbnails, and downloads.
- API credentials as needed: IMVDb, Discogs, Spotify (optional but required for those features).
- Generate a JWT secret for the API: `python - <<'PY'\nimport secrets; print(secrets.token_urlsafe(32))\nPY`.

## Quick start (local)
1. **Backend deps**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
2. **Config**  
   Copy the template and fill in API keys as needed:
   ```bash
   cp config.example.yaml config.yaml
   ```
   Environment overrides:
   - `FUZZBIN_CONFIG_DIR`, `FUZZBIN_LIBRARY_DIR` to change storage paths.
   - `FUZZBIN_API_JWT_SECRET` (required), `FUZZBIN_API_HOST`, `FUZZBIN_API_PORT`, `FUZZBIN_API_DEBUG` for the server.
3. **Run the API**
   ```bash
   export FUZZBIN_API_JWT_SECRET=<paste-secret>
   fuzzbin-api
   ```
   First run will create `config.yaml` (if missing), initialize `fuzzbin.db`, and seed `admin/changeme` with `password_must_change=1`.
4. **Change the admin password** (recommended before UI login):
   ```bash
   fuzzbin-user set-password --username admin
   ```
5. **Frontend**
   ```bash
   cd frontend
   npm install
   VITE_API_BASE_URL=http://localhost:8000 npm run dev
   ```
   Open the printed Vite URL, log in as `admin` with your new password, and start importing.

## Core capabilities
- **Library**: Browse as grid or table, stream via Range-enabled endpoint, view metadata and status history, switch facets (tags/genres/years/directors), and run saved or ad hoc searches.
- **Bulk actions**: Update status, tag sets, add to collections, delete (with optional file delete to trash), and organize file paths in batch.
- **Import hub**:  
  - Artist/Title Search wizard: aggregate IMVDb, Discogs, and YouTube results; preview and import single videos.  
  - Spotify playlist import: preview, duplicate check, selective import, and optional auto-download.  
  - NFO directory scan: full import (NFO metadata) or discovery mode for later enrichment.  
  - One-off YouTube downloads and metadata lookups via yt-dlp.
- **Automation & jobs**: Any import/download/scan/export runs as a background job; track via `/jobs` API or WebSocket `/ws/events`. Scheduled jobs handle backups and trash cleanup.
- **Files & integrity**: Organizer moves files to pattern-based paths, regenerate thumbnails, detect duplicates, soft-delete to `.trash`, restore, permanently delete, verify/repair library state, and queue downloads directly from a video record.
- **Search**: FTS5 query language with boolean operators and phrase search, autocomplete suggestions, facets for UI filters, and saved searches persisted in the DB.
- **Exports**: Regenerate NFOs (artist and musicvideo) and export playlists as M3U/CSV/JSON.
- **Configuration**: PATCH `/config` with safety levels to guard disruptive changes, fetch field-level metadata (`/config/field/{path}`), inspect history/undo/redo, and reload API clients. Advanced options (per-API caching/rate limits, logging overrides, backup/trash schedules, organizer patterns) live in `docs/advanced-config.md`.

## API, docs, and real-time
- REST: OpenAPI at `/openapi.json` (`docs/openapi.json`, human-readable `docs/openapi-spec.md`).
- WebSocket: `/ws/events` with first-message auth and job subscriptions; see `docs/websocket-spec.md` for message shapes and close codes.
- Auth flow: login (`/auth/login`) returns access token and sets refresh cookie; refresh via `/auth/refresh`; logout revokes token and clears cookie; `/auth/password` and `/auth/set-initial-password` handle rotation.
- Type generation for the UI: `cd frontend && npm run generate-types` after changing the backend schema.

## Development and testing
- Backend:
  ```bash
  pytest          # with coverage flags from pyproject
  ruff check .    # lint
  mypy fuzzbin    # type checks
  ```
- Frontend:
  ```bash
  npm run lint
  npm test          # unit/VItest
  npm run test:e2e  # Playwright (requires API running and seeded data)
  npm run build
  ```

## Repository layout
- `fuzzbin/` – FastAPI app, background jobs, clients, workflows, and config/database code.
- `frontend/` – React/Vite UI.
- `docs/` – OpenAPI and WebSocket specs plus advanced config notes.
- `config.example.yaml` – starter config; copies to `config.yaml` on first run.
- `examples/`, `tests/` – sample usage and backend tests.

## License

MIT
