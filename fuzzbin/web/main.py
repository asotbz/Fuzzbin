"""FastAPI application factory and entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

import fuzzbin
from fuzzbin.auth import is_default_password
from fuzzbin.common.logging_config import setup_logging
from fuzzbin.tasks import init_job_queue, reset_job_queue
from fuzzbin.tasks.handlers import register_all_handlers

from .dependencies import require_auth, get_api_settings
from .middleware import RequestLoggingMiddleware, register_exception_handlers
from .settings import get_settings, APISettings
from .schemas.common import HealthCheckResponse, AUTH_ERROR_RESPONSES

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
        await fuzzbin.configure()
    else:
        logger.info("api_using_existing_config")

    # Initialize and start job queue
    queue = init_job_queue(max_workers=2)
    register_all_handlers(queue)
    await queue.start()
    logger.info("job_queue_started_in_lifespan")

    # Check for default password if auth is enabled
    if settings.auth_enabled:
        logger.info("api_auth_enabled", jwt_algorithm=settings.jwt_algorithm)
        await _check_default_password_warning()
    else:
        logger.info("api_auth_disabled", note="Set FUZZBIN_API_AUTH_ENABLED=true for production")

    logger.info(
        "api_ready",
        version=fuzzbin.__version__,
        debug=settings.debug,
    )

    yield

    # Cleanup on shutdown
    logger.info("api_shutting_down")

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

Obtain a token via `POST /auth/token` with username/password credentials.

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
                "name": "Imports",
                "description": "Import workflows for YouTube and IMVDb content",
            },
            {
                "name": "Exports",
                "description": "Export NFO metadata files and generate playlists",
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
    from .routes import artists, collections, search, tags, videos, auth, files, jobs, websocket
    from .routes import bulk, imports, exports  # Phase 7 routes

    # Auth routes (public - no authentication required)
    app.include_router(auth.router)

    # WebSocket routes (handle their own authentication if needed)
    app.include_router(websocket.router)

    # Protected routes - require authentication when auth_enabled=True
    # The require_auth dependency will bypass auth check when auth_enabled=False
    protected_dependencies = [Depends(require_auth)]

    app.include_router(videos.router, dependencies=protected_dependencies)
    app.include_router(artists.router, dependencies=protected_dependencies)
    app.include_router(collections.router, dependencies=protected_dependencies)
    app.include_router(tags.router, dependencies=protected_dependencies)
    app.include_router(search.router, dependencies=protected_dependencies)
    app.include_router(files.router, dependencies=protected_dependencies)
    app.include_router(jobs.router, dependencies=protected_dependencies)
    # Phase 7 routes
    app.include_router(bulk.router, dependencies=protected_dependencies)
    app.include_router(imports.router, dependencies=protected_dependencies)
    app.include_router(exports.router, dependencies=protected_dependencies)

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
                "description": "JWT token obtained from POST /auth/token",
            }
        }
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

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
