"""WebSocket endpoints for real-time updates."""

import asyncio
from typing import Dict, Optional, Set

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

import fuzzbin
from fuzzbin.auth import decode_token
from fuzzbin.tasks import get_job_queue
from fuzzbin.web.schemas.events import WebSocketEvent
from fuzzbin.web.schemas.jobs import JobProgressUpdate
from fuzzbin.web.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages WebSocket connections for broadcast events.

    Thread-safe connection tracking with broadcast support for
    real-time event distribution to connected clients.
    """

    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection.

        Args:
            websocket: WebSocket connection to register
        """
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.debug(
            "websocket_connected",
            total_connections=len(self.active_connections),
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket connection.

        Args:
            websocket: WebSocket connection to remove
        """
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.debug(
            "websocket_disconnected",
            total_connections=len(self.active_connections),
        )

    async def broadcast(self, event: WebSocketEvent) -> None:
        """Broadcast an event to all connected clients.

        Failed sends are silently ignored and the connection is removed.

        Args:
            event: WebSocketEvent to broadcast
        """
        if not self.active_connections:
            return

        message = event.model_dump(mode="json")
        dead_connections: Set[WebSocket] = set()

        async with self._lock:
            connections = list(self.active_connections)

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.debug(
                    "websocket_send_failed",
                    error=str(e),
                )
                dead_connections.add(connection)

        # Remove dead connections
        if dead_connections:
            async with self._lock:
                self.active_connections -= dead_connections
            logger.debug(
                "dead_connections_removed",
                count=len(dead_connections),
            )

    async def broadcast_dict(self, message: Dict) -> None:
        """Broadcast a raw dictionary message to all connected clients.

        Args:
            message: Dictionary to broadcast as JSON
        """
        if not self.active_connections:
            return

        dead_connections: Set[WebSocket] = set()

        async with self._lock:
            connections = list(self.active_connections)

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)

        if dead_connections:
            async with self._lock:
                self.active_connections -= dead_connections

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)


# Global connection manager instance for event broadcasting
connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance.

    Returns:
        ConnectionManager singleton for event broadcasting
    """
    return connection_manager


@router.websocket("/ws/events")
async def events_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None, description="Optional JWT token for authentication"),
) -> None:
    """WebSocket endpoint for real-time application events.

    Broadcasts configuration changes, job progress, and other system events
    to connected clients. Authentication is optional but recommended.

    Args:
        websocket: WebSocket connection
        token: Optional JWT token for authentication (query parameter)

    Protocol:
        1. Client connects to /ws/events (optionally with ?token=<jwt>)
        2. Server accepts connection (validates token if auth enabled and provided)
        3. Server broadcasts events as they occur
        4. Client can disconnect at any time

    Message Format (JSON):
        {
            "event_type": "config_changed",
            "timestamp": "2025-12-22T15:30:00Z",
            "payload": {
                "path": "http.timeout",
                "old_value": 30,
                "new_value": 60,
                "safety_level": "safe",
                "required_actions": []
            }
        }

    Event Types:
        - config_changed: Configuration field was modified
        - job_progress: Background job progress update
        - job_completed: Background job completed successfully
        - job_failed: Background job failed with error
        - client_reloaded: API client was reloaded with new configuration
    """
    settings = get_settings()

    # Optional authentication check
    if token and settings.auth_enabled:
        try:
            repo = await fuzzbin.get_repository()
            user_info = await decode_token(token, settings.jwt_secret, repo)
            logger.info(
                "websocket_events_authenticated",
                user_id=user_info.user_id,
                username=user_info.username,
            )
        except Exception as e:
            logger.warning(
                "websocket_events_auth_failed",
                error=str(e),
            )
            # Still accept connection but log the auth failure
            # This allows unauthenticated connections in single-user mode

    await connection_manager.connect(websocket)
    logger.info("websocket_events_connected")

    try:
        # Keep connection alive - wait for client messages or disconnect
        while True:
            # Wait for any message (ping/pong or disconnect)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        logger.info("websocket_events_client_disconnected")
    except Exception as e:
        logger.error("websocket_events_error", error=str(e), exc_info=True)
    finally:
        await connection_manager.disconnect(websocket)
        logger.info("websocket_events_closed")


@router.websocket("/ws/jobs/{job_id}")
async def job_progress_websocket(websocket: WebSocket, job_id: str) -> None:
    """WebSocket endpoint for real-time job progress updates.

    Connects to a specific job and streams progress updates until the job
    reaches a terminal state (completed, failed, or cancelled).

    Args:
        websocket: WebSocket connection
        job_id: Job ID to monitor

    Protocol:
        1. Client connects to /ws/jobs/{job_id}
        2. Server accepts and sends initial job state
        3. Server polls job status every 500ms and sends updates
        4. Server closes connection when job reaches terminal state
        5. Client can disconnect at any time

    Message Format (JSON):
        {
            "job_id": "uuid",
            "status": "running",
            "progress": 0.45,
            "current_step": "Processing file.nfo...",
            "processed_items": 45,
            "total_items": 100,
            "error": null,
            "result": null
        }
    """
    await websocket.accept()
    logger.info("websocket_connected", job_id=job_id)

    try:
        queue = get_job_queue()
    except RuntimeError:
        await websocket.send_json({"error": "Job queue not initialized"})
        await websocket.close(code=1011, reason="Job queue not initialized")
        return

    try:
        # Send initial job state
        job = await queue.get_job(job_id)
        if not job:
            await websocket.send_json({"error": "Job not found"})
            await websocket.close(code=1008, reason="Job not found")
            return

        # Send initial state
        update = JobProgressUpdate(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            current_step=job.current_step,
            processed_items=job.processed_items,
            total_items=job.total_items,
            error=job.error,
            result=job.result,
        )
        await websocket.send_json(update.model_dump(mode="json"))

        # Poll for updates every 500ms
        last_progress = job.progress
        last_step = job.current_step

        while True:
            await asyncio.sleep(0.5)

            job = await queue.get_job(job_id)
            if not job:
                logger.warning("job_disappeared", job_id=job_id)
                break

            # Only send update if something changed
            if job.progress != last_progress or job.current_step != last_step or job.is_terminal:
                update = JobProgressUpdate(
                    job_id=job.id,
                    status=job.status,
                    progress=job.progress,
                    current_step=job.current_step,
                    processed_items=job.processed_items,
                    total_items=job.total_items,
                    error=job.error,
                    result=job.result,
                )
                await websocket.send_json(update.model_dump(mode="json"))
                last_progress = job.progress
                last_step = job.current_step

            # Exit if job is terminal
            if job.is_terminal:
                logger.info(
                    "job_terminal_state",
                    job_id=job_id,
                    status=job.status.value,
                )
                break

    except WebSocketDisconnect:
        logger.info("websocket_disconnected", job_id=job_id)
    except Exception as e:
        logger.error("websocket_error", job_id=job_id, error=str(e), exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass  # Connection may already be closed
    finally:
        logger.info("websocket_closed", job_id=job_id)
