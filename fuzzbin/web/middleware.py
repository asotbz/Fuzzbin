"""Middleware and exception handlers for the FastAPI application."""

import time
from typing import Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from fuzzbin.core.db.exceptions import (
    ArtistNotFoundError,
    CollectionNotFoundError,
    DatabaseError,
    DuplicateRecordError,
    QueryError,
    TagNotFoundError,
    TransactionError,
    VideoNotFoundError,
)

logger = structlog.get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register exception handlers for the FastAPI application.

    Maps database exceptions to appropriate HTTP status codes:
    - VideoNotFoundError, ArtistNotFoundError, CollectionNotFoundError, TagNotFoundError -> 404
    - DuplicateRecordError -> 409
    - QueryError, TransactionError, DatabaseError -> 500

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(VideoNotFoundError)
    async def video_not_found_handler(request: Request, exc: VideoNotFoundError) -> JSONResponse:
        logger.warning(
            "video_not_found",
            video_id=exc.video_id,
            imvdb_id=exc.imvdb_id,
            youtube_id=exc.youtube_id,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=404,
            content={
                "detail": str(exc),
                "error_type": "video_not_found",
                "video_id": exc.video_id,
            },
        )

    @app.exception_handler(ArtistNotFoundError)
    async def artist_not_found_handler(request: Request, exc: ArtistNotFoundError) -> JSONResponse:
        logger.warning(
            "artist_not_found",
            artist_id=exc.artist_id,
            name=exc.name,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=404,
            content={
                "detail": str(exc),
                "error_type": "artist_not_found",
                "artist_id": exc.artist_id,
            },
        )

    @app.exception_handler(CollectionNotFoundError)
    async def collection_not_found_handler(
        request: Request, exc: CollectionNotFoundError
    ) -> JSONResponse:
        logger.warning(
            "collection_not_found",
            collection_id=exc.collection_id,
            name=exc.name,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=404,
            content={
                "detail": str(exc),
                "error_type": "collection_not_found",
                "collection_id": exc.collection_id,
            },
        )

    @app.exception_handler(TagNotFoundError)
    async def tag_not_found_handler(request: Request, exc: TagNotFoundError) -> JSONResponse:
        logger.warning(
            "tag_not_found",
            tag_id=exc.tag_id,
            name=exc.name,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=404,
            content={
                "detail": str(exc),
                "error_type": "tag_not_found",
                "tag_id": exc.tag_id,
            },
        )

    @app.exception_handler(DuplicateRecordError)
    async def duplicate_record_handler(request: Request, exc: DuplicateRecordError) -> JSONResponse:
        logger.warning(
            "duplicate_record",
            table=exc.table,
            key=exc.key,
            value=exc.value,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=409,
            content={
                "detail": str(exc),
                "error_type": "duplicate_record",
                "table": exc.table,
                "key": exc.key,
            },
        )

    @app.exception_handler(QueryError)
    async def query_error_handler(request: Request, exc: QueryError) -> JSONResponse:
        logger.error(
            "query_error",
            error=str(exc),
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Database query failed",
                "error_type": "query_error",
            },
        )

    @app.exception_handler(TransactionError)
    async def transaction_error_handler(request: Request, exc: TransactionError) -> JSONResponse:
        logger.error(
            "transaction_error",
            operation=exc.operation,
            error=str(exc),
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Database transaction failed",
                "error_type": "transaction_error",
            },
        )

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request: Request, exc: DatabaseError) -> JSONResponse:
        logger.error(
            "database_error",
            error=str(exc),
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Database error occurred",
                "error_type": "database_error",
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "validation_error",
            errors=exc.errors(),
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation error",
                "error_type": "validation_error",
                "errors": [
                    {
                        "loc": list(err["loc"]),
                        "msg": err["msg"],
                        "type": err["type"],
                    }
                    for err in exc.errors()
                ],
            },
        )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests and responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Log request details and response status."""
        start_time = time.perf_counter()

        # Log request
        logger.info(
            "request_started",
            method=request.method,
            path=str(request.url.path),
            query=str(request.url.query) if request.url.query else None,
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration = time.perf_counter() - start_time
            logger.error(
                "request_failed",
                method=request.method,
                path=str(request.url.path),
                error=str(exc),
                duration_ms=round(duration * 1000, 2),
            )
            raise

        duration = time.perf_counter() - start_time
        logger.info(
            "request_completed",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )

        return response
