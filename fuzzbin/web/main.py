"""FastAPI application factory and entry point."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import fuzzbin
from fuzzbin.auth import is_default_password
from fuzzbin.common.logging_config import setup_logging
from fuzzbin.core import init_event_bus, reset_event_bus
from fuzzbin.tasks import init_job_queue, reset_job_queue, Job, JobType
from fuzzbin.tasks.handlers import register_all_handlers

from .dependencies import require_auth, get_api_settings
from .middleware import RequestLoggingMiddleware, register_exception_handlers
from .settings import get_settings, APISettings
from .schemas.common import HealthCheckResponse

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles startup and shutdown events:
    - Startup: Configure fuzzbin (logging, database), start job queue
    - Shutdown: Stop job queue, close database connections

    Note: In test mode, fuzzbin._config and fuzzbin._repository are
    pre-configured by test fixtures, so we skip initialization.
    """
    settings = get_settings()

    # Configure fuzzbin on startup (skip if already configured by tests)
    logger.info("api_starting", host=settings.host, port=settings.port)

    # Check if already configured (e.g., by test fixtures)
    already_configured = fuzzbin._config is not None and fuzzbin._repository is not None

    if not already_configured:
        # Initialize fuzzbin configuration and database
        if settings.config_path:
            await fuzzbin.configure(config_path=Path(settings.config_path))
        else:
            await fuzzbin.configure()
    else:
        logger.info("api_using_existing_config")

    # Initialize and start job queue
    queue = init_job_queue(max_workers=2)
    register_all_handlers(queue)

    # Initialize event bus and wire up to job queue
    event_bus = init_event_bus()
    from fuzzbin.web.routes.websocket import get_connection_manager

    ws_manager = get_connection_manager()
    event_bus.set_broadcast_function(ws_manager.broadcast_dict)
    queue.set_event_bus(event_bus)
    logger.info("event_bus_wired_to_job_queue")

    await queue.start()
    logger.info("job_queue_started_in_lifespan")

    # Schedule automatic backup if enabled
    config = fuzzbin.get_config()
    if config.backup.enabled:
        backup_job = Job(
            type=JobType.BACKUP,
            schedule=config.backup.schedule,
            metadata={"retention_count": config.backup.retention_count},
        )
        await queue.submit(backup_job)
        logger.info(
            "scheduled_backup_enabled",
            schedule=config.backup.schedule,
            retention_count=config.backup.retention_count,
        )

    # Schedule automatic trash cleanup if enabled
    if config.trash.enabled:
        trash_cleanup_job = Job(
            type=JobType.TRASH_CLEANUP,
            schedule=config.trash.schedule,
            metadata={"retention_days": config.trash.retention_days},
        )
        await queue.submit(trash_cleanup_job)
        logger.info(
            "scheduled_trash_cleanup_enabled",
            schedule=config.trash.schedule,
            retention_days=config.trash.retention_days,
        )

    # Schedule automatic NFO export if enabled
    if config.nfo_export.enabled:
        nfo_export_job = Job(
            type=JobType.EXPORT_NFO,
            schedule=config.nfo_export.schedule,
            metadata={
                "incremental": config.nfo_export.incremental,
                "include_deleted": config.nfo_export.include_deleted,
            },
        )
        await queue.submit(nfo_export_job)
        logger.info(
            "scheduled_nfo_export_enabled",
            schedule=config.nfo_export.schedule,
            incremental=config.nfo_export.incremental,
            include_deleted=config.nfo_export.include_deleted,
        )

    # Check for default password if auth is enabled
    if settings.auth_enabled:
        logger.info("api_auth_enabled", jwt_algorithm=settings.jwt_algorithm)
        await _check_default_password_warning()

        # Cleanup expired revoked tokens on startup
        try:
            from fuzzbin.auth import cleanup_expired_tokens

            cleaned = await cleanup_expired_tokens()
            if cleaned > 0:
                logger.info("startup_token_cleanup", expired_tokens_removed=cleaned)
        except Exception as e:
            logger.debug("startup_token_cleanup_failed", error=str(e))
    else:
        # Log prominent warning for insecure mode
        logger.warning(
            "SECURITY_WARNING_INSECURE_MODE",
            message="Running in INSECURE MODE - authentication is disabled!",
            bound_host=settings.host,
            note="This mode is for local development only. All endpoints are unprotected.",
        )

    # Register config change callback for WebSocket broadcast
    try:
        from fuzzbin.web.routes.websocket import get_connection_manager
        from fuzzbin.web.schemas.events import WebSocketEvent
        from fuzzbin.common.config_manager import ConfigChangeEvent

        config_manager = fuzzbin.get_config_manager()
        ws_manager = get_connection_manager()

        async def broadcast_config_change(event: ConfigChangeEvent) -> None:
            """Broadcast config changes to connected WebSocket clients."""
            # Determine required actions based on safety level
            required_actions = []
            if event.safety_level.value == "requires_reload":
                if event.path.startswith("apis."):
                    parts = event.path.split(".")
                    if len(parts) >= 2:
                        required_actions.append(f"reload_client:{parts[1]}")
            elif event.safety_level.value == "affects_state":
                if "database" in event.path:
                    required_actions.append("reconnect_database")
                elif event.path in ("config_dir", "library_dir"):
                    required_actions.append("restart_service")

            ws_event = WebSocketEvent.config_changed(
                path=event.path,
                old_value=event.old_value,
                new_value=event.new_value,
                safety_level=event.safety_level.value,
                required_actions=required_actions,
            )
            await ws_manager.broadcast(ws_event)

        config_manager.on_change(broadcast_config_change)
        logger.info("config_change_broadcast_registered")
    except Exception as e:
        logger.warning("config_change_broadcast_registration_failed", error=str(e))

    logger.info(
        "api_ready",
        version=fuzzbin.__version__,
        debug=settings.debug,
    )

    yield

    # Cleanup on shutdown
    logger.info("api_shutting_down")

    # Cleanup shared API clients
    from .dependencies import cleanup_api_clients

    await cleanup_api_clients()

    # Shutdown event bus
    await event_bus.shutdown()
    reset_event_bus()
    logger.info("event_bus_shutdown_in_lifespan")

    # Stop job queue
    await queue.stop()
    reset_job_queue()
    logger.info("job_queue_stopped_in_lifespan")

    # Close database (only if we initialized)
    if not already_configured and fuzzbin._repository is not None:
        await fuzzbin._repository.close()


async def _check_default_password_warning() -> None:
    """Check if admin user is using the default password and log a warning."""
    try:
        repo = await fuzzbin.get_repository()
        cursor = await repo._connection.execute(
            "SELECT password_hash FROM users WHERE username = 'admin'"
        )
        row = await cursor.fetchone()

        if row and is_default_password(row[0]):
            logger.warning(
                "SECURITY_WARNING_DEFAULT_PASSWORD",
                message="Admin user is using the default password 'changeme'!",
                action="Change immediately via POST /auth/password or CLI: fuzzbin user set-password",
            )
    except Exception as e:
        # Don't fail startup if we can't check - just log
        logger.debug("default_password_check_failed", error=str(e))


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    This factory function creates the app with:
    - OpenAPI metadata (title, version, description)
    - CORS middleware
    - Request logging middleware (if enabled)
    - Exception handlers for database errors
    - Health check endpoint

    Returns:
        Configured FastAPI application instance

    Example:
        # For testing
        from fuzzbin.web import create_app
        app = create_app()

        # With TestClient
        from fastapi.testclient import TestClient
        client = TestClient(app)
    """
    settings = get_settings()

    # Setup logging before creating app
    config = fuzzbin.get_config()
    setup_logging(config.logging)

    app = FastAPI(
        title="Fuzzbin API",
        version=fuzzbin.__version__,
        description="""Music video library management API.
Provides CRUD operations for videos, artists, collections, and tags,
with full-text search and filtering capabilities.

## Authentication

When authentication is enabled (`FUZZBIN_API_AUTH_ENABLED=true`), protected endpoints require
a Bearer token in the `Authorization` header:

```
Authorization: Bearer <your-jwt-token>
```

Obtain a token via `POST /auth/login` with username/password credentials.

## WebSocket API

### Real-time Job Progress: `/ws/jobs/{job_id}`

Connect to receive live progress updates for background jobs.

**Connection:**
```
ws://localhost:8000/ws/jobs/{job_id}
```

**Message Format (JSON):**
```json
{
  "job_id": "uuid-string",
  "status": "running",
  "progress": 0.45,
  "message": "Processing file 45 of 100",
  "result": null
}
```

**Fields:**
- `job_id`: Job identifier
- `status`: One of `pending`, `running`, `completed`, `failed`, `cancelled`
- `progress`: Float 0.0-1.0 indicating completion percentage
- `message`: Human-readable status message
- `result`: Job result data (populated on completion)

**Close Codes:**
- `1008` (Policy Violation): Invalid or unknown job ID
- `1011` (Internal Error): Server error during progress streaming
""",
        openapi_url=settings.openapi_url,
        openapi_tags=[
            {
                "name": "Health",
                "description": "Health check and status endpoints",
            },
            {
                "name": "Authentication",
                "description": "User authentication, token management, and password operations",
            },
            {
                "name": "Videos",
                "description": "Video CRUD operations and metadata management",
            },
            {
                "name": "Artists",
                "description": "Artist management and video associations",
            },
            {
                "name": "Collections",
                "description": "Collection management for organizing videos",
            },
            {
                "name": "Tags",
                "description": "Tag management and video categorization",
            },
            {
                "name": "Search",
                "description": "Full-text search across the video library",
            },
            {
                "name": "Files",
                "description": "File operations: organize, delete, restore, verify, and duplicate detection",
            },
            {
                "name": "Jobs",
                "description": "Background job submission, status tracking, and cancellation",
            },
            {
                "name": "WebSocket",
                "description": "Real-time progress updates via WebSocket",
            },
            {
                "name": "Bulk Operations",
                "description": "Batch operations for updating, deleting, tagging, and organizing multiple videos",
            },
            {
                "name": "IMVDb",
                "description": "IMVDb music video database: search videos/entities, get metadata and credits",
            },
            {
                "name": "Discogs",
                "description": "Discogs music database: search releases, get master/release details and artist discographies",
            },
            {
                "name": "Spotify",
                "description": "Spotify Web API: get playlists, tracks, and collect all metadata from a playlist",
            },
            {
                "name": "Exports",
                "description": "Export NFO metadata files and generate playlists",
            },
            {
                "name": "Backup",
                "description": "System backup creation, listing, download, and verification",
            },
            {
                "name": "Configuration",
                "description": "Runtime configuration management with history/undo support and safety level enforcement",
            },
            {
                "name": "yt-dlp",
                "description": "YouTube video search, metadata retrieval, and download with progress tracking",
            },
            {
                "name": "Library Scan",
                "description": "Scan directories for music videos and import into library with full or discovery mode",
            },
            {
                "name": "Add",
                "description": "Import hub endpoints: batch preview and import job submission",
            },
        ],
        lifespan=lifespan,
        debug=settings.debug,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Password-Change-Required", "Retry-After"],
    )

    # Add request logging middleware if enabled
    if settings.log_requests:
        app.add_middleware(RequestLoggingMiddleware)

    # Register exception handlers
    register_exception_handlers(app)

    # Health check endpoint
    @app.get(
        "/health",
        tags=["Health"],
        summary="Health check",
        response_model=HealthCheckResponse,
        response_description="Health status of the API",
    )
    async def health_check(
        settings: APISettings = Depends(get_api_settings),
    ) -> HealthCheckResponse:
        """
        Check API health status.

        Returns basic health information including API version.
        """
        return HealthCheckResponse(
            status="ok",
            version=fuzzbin.__version__,
            auth_enabled=settings.auth_enabled,
        )

    # Import and include routers
    from .routes import (
        artists,
        collections,
        search,
        tags,
        videos,
        auth,
        files,
        jobs,
        websocket,
    )
    from .routes import (
        add,
        bulk,
        discogs,
        exports,
        backup,
        config,
        genres,
        imvdb,
        scan,
        spotify,
        ytdlp,
    )  # Phase 7 routes + config + ytdlp + external APIs + genres

    # Auth routes (no authentication required)
    app.include_router(auth.router)

    # WebSocket routes (handle their own authentication if needed)
    app.include_router(websocket.router)

    # Video stream endpoint (handles auth internally via query param for <video> element)
    app.include_router(videos.stream_router)

    # Protected routes - require authentication when auth_enabled=True
    # The require_auth dependency will bypass auth check when auth_enabled=False
    protected_dependencies = [Depends(require_auth)]

    # NOTE: bulk.router must be included BEFORE videos.router
    # Otherwise /videos/bulk/* routes match /videos/{video_id} where video_id="bulk"
    app.include_router(bulk.router, dependencies=protected_dependencies)
    app.include_router(videos.router, dependencies=protected_dependencies)
    app.include_router(artists.router, dependencies=protected_dependencies)
    app.include_router(collections.router, dependencies=protected_dependencies)
    app.include_router(tags.router, dependencies=protected_dependencies)
    app.include_router(search.router, dependencies=protected_dependencies)
    app.include_router(files.router, dependencies=protected_dependencies)
    app.include_router(jobs.router, dependencies=protected_dependencies)
    app.include_router(add.router, dependencies=protected_dependencies)
    # Phase 7 routes
    app.include_router(imvdb.router, dependencies=protected_dependencies)
    app.include_router(discogs.router, dependencies=protected_dependencies)
    app.include_router(spotify.router, dependencies=protected_dependencies)
    app.include_router(exports.router, dependencies=protected_dependencies)
    app.include_router(backup.router, dependencies=protected_dependencies)
    app.include_router(config.router, dependencies=protected_dependencies)
    app.include_router(genres.router, dependencies=protected_dependencies)
    app.include_router(ytdlp.router, dependencies=protected_dependencies)
    app.include_router(scan.router, dependencies=protected_dependencies)

    # Custom OpenAPI schema with security scheme
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )
        # Add security scheme for Bearer authentication
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token obtained from POST /auth/login",
            }
        }
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # SPA static file serving (for Docker production deployment)
    # Only enabled when frontend/dist exists (i.e., in Docker image)
    # Check multiple possible locations:
    # 1. /app/frontend/dist (Docker deployment)
    # 2. Relative to source (local development with built frontend)
    frontend_dist = None
    possible_paths = [
        Path("/app/frontend/dist"),  # Docker container path
        Path(__file__).parent.parent.parent / "frontend" / "dist",  # Relative to source
    ]
    for path in possible_paths:
        if path.exists() and path.is_dir():
            frontend_dist = path
            break

    if frontend_dist is not None:
        # Mount static assets (JS, CSS, images)
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="static_assets")
            logger.info("spa_assets_mounted", path="/assets", directory=str(assets_dir))

        # API route prefixes to exclude from SPA catch-all
        # These must be passed through to the API, not served as frontend routes
        API_PREFIXES = (
            "/add",
            "/artists",
            "/auth",
            "/backup",
            "/collections",
            "/config",
            "/discogs",
            "/exports",
            "/files",
            "/genres",
            "/health",
            "/imvdb",
            "/jobs",
            "/scan",
            "/search",
            "/spotify",
            "/tags",
            "/videos",
            "/ytdlp",
            "/ws",
            "/docs",
            "/redoc",
            "/openapi.json",
        )

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            """
            Serve the SPA index.html for all non-API routes.

            This enables client-side routing in the React frontend.
            API routes are excluded and handled by their respective routers.
            Static files (images, etc.) are served directly if they exist.
            """
            # Check if path starts with an API prefix
            path_to_check = f"/{full_path}"
            if any(path_to_check.startswith(prefix) for prefix in API_PREFIXES):
                # This shouldn't normally be reached since API routes are registered first,
                # but provides a safety net
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Not found")

            # Check if requesting a static file that exists (e.g., images from public/)
            if full_path:
                static_file = frontend_dist / full_path
                if static_file.exists() and static_file.is_file():
                    # Determine media type based on extension
                    import mimetypes

                    media_type, _ = mimetypes.guess_type(str(static_file))
                    return FileResponse(static_file, media_type=media_type)

            # Serve index.html for SPA routing
            index_file = frontend_dist / "index.html"
            if index_file.exists():
                return FileResponse(index_file, media_type="text/html")

            # Fallback if index.html doesn't exist
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Frontend not found")

        logger.info("spa_serving_enabled", frontend_dist=str(frontend_dist))

    logger.info("api_app_created", routes=len(app.routes))

    return app


def run() -> None:
    """
    Run the API server with uvicorn.

    This is the entry point for the fuzzbin-api script.
    """
    settings = get_settings()

    uvicorn.run(
        "fuzzbin.web.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
