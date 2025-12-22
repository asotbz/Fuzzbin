"""WebSocket endpoints for real-time updates with first-message authentication."""

import asyncio
from typing import Any, Dict, Literal, Optional, Set, Union

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

import fuzzbin
from fuzzbin.auth import decode_token
from fuzzbin.tasks import get_job_queue
from fuzzbin.web.schemas.events import WebSocketEvent
from fuzzbin.web.schemas.jobs import JobProgressUpdate
from fuzzbin.web.settings import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["WebSocket"])

# WebSocket close codes (4000+ range for application-specific codes)
WS_CLOSE_AUTH_TIMEOUT = 4000
WS_CLOSE_AUTH_FAILED = 4001
WS_CLOSE_AUTH_REQUIRED = 4002


# ============================================================================
# WebSocket Client Message Schemas (for first-message auth protocol)
# ============================================================================


class WSAuthMessage(BaseModel):
    """Authentication message sent by client as first message."""

    type: Literal["auth"] = Field(description="Message type, must be 'auth'")
    token: str = Field(min_length=1, description="JWT access token")


class WSPingMessage(BaseModel):
    """Keep-alive ping message from client."""

    type: Literal["ping"] = Field(description="Message type, must be 'ping'")


class WSSubscribeMessage(BaseModel):
    """Subscribe to specific event types (optional, for future use)."""

    type: Literal["subscribe"] = Field(description="Message type, must be 'subscribe'")
    events: list[str] = Field(description="List of event types to subscribe to")


# Union type for all valid client messages
WSClientMessage = Union[WSAuthMessage, WSPingMessage, WSSubscribeMessage]


class WSAuthSuccessResponse(BaseModel):
    """Response sent on successful authentication."""

    type: Literal["auth_success"] = "auth_success"
    user_id: int = Field(description="Authenticated user ID")
    username: str = Field(description="Authenticated username")


class WSAuthErrorResponse(BaseModel):
    """Response sent on authentication failure."""

    type: Literal["auth_error"] = "auth_error"
    message: str = Field(description="Error description")
    code: int = Field(description="WebSocket close code that will follow")


class WSPongResponse(BaseModel):
    """Response to client ping."""

    type: Literal["pong"] = "pong"


class ConnectionManager:
    """Manages WebSocket connections for broadcast events.

    Thread-safe connection tracking with broadcast support for
    real-time event distribution to connected clients.

    Note: This manager does NOT accept connections automatically.
    The caller must call websocket.accept() before adding to manager,
    allowing for authentication to occur first.
    """

    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add(self, websocket: WebSocket) -> None:
        """Register an already-accepted WebSocket connection.

        The websocket must already be accepted before calling this method.
        This allows authentication to happen between accept and registration.

        Args:
            websocket: WebSocket connection to register (must be accepted)
        """
        async with self._lock:
            self.active_connections.add(websocket)
        logger.debug(
            "websocket_registered",
            total_connections=len(self.active_connections),
        )

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection.

        Deprecated: Use accept() on websocket directly, then add().
        Kept for backward compatibility.

        Args:
            websocket: WebSocket connection to register
        """
        await websocket.accept()
        await self.add(websocket)

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


async def _authenticate_websocket(
    websocket: WebSocket,
    timeout_seconds: float = 10.0,
) -> Optional[Dict[str, Any]]:
    """Perform first-message authentication for WebSocket connections.

    Waits for an auth message from the client, validates the JWT token,
    and returns user info on success.

    Args:
        websocket: Already-accepted WebSocket connection
        timeout_seconds: How long to wait for auth message

    Returns:
        Dict with user_id and username on success, None on failure
        (error response already sent to client)
    """
    settings = get_settings()

    try:
        # Wait for first message with timeout
        raw_message = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        error = WSAuthErrorResponse(
            message="Authentication timeout - no auth message received",
            code=WS_CLOSE_AUTH_TIMEOUT,
        )
        await websocket.send_json(error.model_dump())
        await websocket.close(code=WS_CLOSE_AUTH_TIMEOUT, reason="Auth timeout")
        logger.warning("websocket_auth_timeout")
        return None

    # Parse the message
    try:
        import json

        data = json.loads(raw_message)
        auth_msg = WSAuthMessage.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        error = WSAuthErrorResponse(
            message=f"Invalid auth message format: {str(e)}",
            code=WS_CLOSE_AUTH_FAILED,
        )
        await websocket.send_json(error.model_dump())
        await websocket.close(code=WS_CLOSE_AUTH_FAILED, reason="Invalid auth message")
        logger.warning("websocket_auth_invalid_format", error=str(e))
        return None

    # Decode and validate JWT token
    payload = decode_token(
        token=auth_msg.token,
        secret_key=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expected_type="access",
    )

    if not payload:
        error = WSAuthErrorResponse(
            message="Invalid or expired token",
            code=WS_CLOSE_AUTH_FAILED,
        )
        await websocket.send_json(error.model_dump())
        await websocket.close(code=WS_CLOSE_AUTH_FAILED, reason="Invalid token")
        logger.warning("websocket_auth_invalid_token")
        return None

    user_id = payload.get("user_id")
    username = payload.get("sub")

    if not user_id or not username:
        error = WSAuthErrorResponse(
            message="Invalid token payload",
            code=WS_CLOSE_AUTH_FAILED,
        )
        await websocket.send_json(error.model_dump())
        await websocket.close(code=WS_CLOSE_AUTH_FAILED, reason="Invalid payload")
        logger.warning("websocket_auth_invalid_payload")
        return None

    # Verify user exists and is active
    try:
        repo = await fuzzbin.get_repository()
        cursor = await repo._connection.execute(
            "SELECT id, is_active FROM users WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()

        if not row or not row[1]:
            error = WSAuthErrorResponse(
                message="User not found or disabled",
                code=WS_CLOSE_AUTH_FAILED,
            )
            await websocket.send_json(error.model_dump())
            await websocket.close(code=WS_CLOSE_AUTH_FAILED, reason="User invalid")
            logger.warning("websocket_auth_user_invalid", user_id=user_id)
            return None
    except Exception as e:
        error = WSAuthErrorResponse(
            message="Authentication error",
            code=WS_CLOSE_AUTH_FAILED,
        )
        await websocket.send_json(error.model_dump())
        await websocket.close(code=WS_CLOSE_AUTH_FAILED, reason="Auth error")
        logger.error("websocket_auth_db_error", error=str(e))
        return None

    # Success! Send confirmation
    success = WSAuthSuccessResponse(user_id=user_id, username=username)
    await websocket.send_json(success.model_dump())

    logger.info("websocket_authenticated", user_id=user_id, username=username)
    return {"user_id": user_id, "username": username}


@router.websocket("/ws/events")
async def events_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time application events.

    Broadcasts configuration changes, job progress, and other system events
    to connected clients. Requires first-message authentication when auth
    is enabled.

    Args:
        websocket: WebSocket connection

    Authentication Protocol (first-message auth):
        1. Client connects to /ws/events
        2. Server accepts the WebSocket connection
        3. Client MUST send auth message within 10 seconds:
           {"type": "auth", "token": "<jwt_access_token>"}
        4. Server validates token and responds:
           - Success: {"type": "auth_success", "user_id": 1, "username": "admin"}
           - Failure: {"type": "auth_error", "message": "...", "code": 4001}
        5. On failure, server closes with code 4001
        6. On success, server registers connection and broadcasts events

    Subsequent Messages:
        - Client can send {"type": "ping"} for keep-alive
        - Server responds with {"type": "pong"}
        - Server sends events as they occur

    Event Format (JSON):
        {
            "event_type": "config_changed",
            "timestamp": "2025-12-22T15:30:00Z",
            "payload": {...}
        }

    Event Types:
        - config_changed: Configuration field was modified
        - job_progress: Background job progress update
        - job_completed: Background job completed successfully
        - job_failed: Background job failed with error
        - client_reloaded: API client was reloaded with new configuration

    WebSocket Close Codes:
        - 4000: Authentication timeout
        - 4001: Authentication failed
        - 4002: Authentication required
    """
    settings = get_settings()

    # Accept the connection first
    await websocket.accept()

    # Perform first-message authentication if auth is enabled
    if settings.auth_enabled:
        user_info = await _authenticate_websocket(websocket)
        if not user_info:
            return  # Connection already closed with error
        logger.info(
            "websocket_events_authenticated",
            user_id=user_info["user_id"],
            username=user_info["username"],
        )
    else:
        # In insecure mode, skip auth but log warning
        logger.warning("websocket_events_no_auth", reason="auth_disabled")

    # Register with connection manager
    await connection_manager.add(websocket)
    logger.info("websocket_events_connected")

    try:
        # Keep connection alive - wait for client messages or disconnect
        while True:
            try:
                raw_message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # Handle client messages
                try:
                    import json

                    data = json.loads(raw_message)
                    if data.get("type") == "ping":
                        await websocket.send_json(WSPongResponse().model_dump())
                except (json.JSONDecodeError, Exception):
                    pass  # Ignore invalid messages

            except asyncio.TimeoutError:
                # Send server ping to keep connection alive
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
    Requires first-message authentication when auth is enabled.

    Args:
        websocket: WebSocket connection
        job_id: Job ID to monitor

    Authentication Protocol (first-message auth):
        1. Client connects to /ws/jobs/{job_id}
        2. Server accepts the WebSocket connection
        3. Client MUST send auth message within 10 seconds:
           {"type": "auth", "token": "<jwt_access_token>"}
        4. Server validates token and responds with auth_success or auth_error
        5. On success, server sends initial job state and streams updates
        6. On failure, server closes with code 4001

    Progress Message Format (JSON):
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

    WebSocket Close Codes:
        - 4000: Authentication timeout
        - 4001: Authentication failed
        - 1008: Job not found
        - 1011: Internal error
    """
    settings = get_settings()

    # Accept the connection first
    await websocket.accept()
    logger.info("websocket_job_connecting", job_id=job_id)

    # Perform first-message authentication if auth is enabled
    if settings.auth_enabled:
        user_info = await _authenticate_websocket(websocket)
        if not user_info:
            return  # Connection already closed with error
        logger.info(
            "websocket_job_authenticated",
            job_id=job_id,
            user_id=user_info["user_id"],
            username=user_info["username"],
        )
    else:
        logger.warning("websocket_job_no_auth", job_id=job_id, reason="auth_disabled")

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
