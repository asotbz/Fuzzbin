"""WebSocket endpoints for real-time updates with first-message authentication."""

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Set, Union

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

import fuzzbin
from fuzzbin.auth import decode_token
from fuzzbin.tasks import get_job_queue
from fuzzbin.web.schemas.events import WebSocketEvent
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


class WSSubscribeJobsMessage(BaseModel):
    """Subscribe to job events with optional filtering.

    Clients can filter job events by job type and/or specific job IDs.
    When include_active_state is True, the server sends current state of
    all active jobs matching the filters immediately after subscribing.

    Example:
        # Subscribe to all job events
        {"type": "subscribe_jobs"}

        # Subscribe to specific job types
        {"type": "subscribe_jobs", "job_types": ["download_youtube", "import_nfo"]}

        # Subscribe to specific jobs
        {"type": "subscribe_jobs", "job_ids": ["uuid-1", "uuid-2"]}

        # Subscribe with initial state dump
        {"type": "subscribe_jobs", "include_active_state": true}
    """

    type: Literal["subscribe_jobs"] = Field(description="Message type, must be 'subscribe_jobs'")
    job_types: list[str] | None = Field(
        default=None,
        description="Filter by job types (e.g., ['download_youtube', 'import_nfo']). None = all types.",
    )
    job_ids: list[str] | None = Field(
        default=None,
        description="Filter by specific job IDs. None = all jobs.",
    )
    include_active_state: bool = Field(
        default=True,
        description="If true, immediately send current state of all active jobs matching filters.",
    )


class WSUnsubscribeJobsMessage(BaseModel):
    """Unsubscribe from job events.

    Removes all job event subscriptions for this connection.

    Example:
        {"type": "unsubscribe_jobs"}
    """

    type: Literal["unsubscribe_jobs"] = Field(
        description="Message type, must be 'unsubscribe_jobs'"
    )


# Union type for all valid client messages
WSClientMessage = Union[
    WSAuthMessage,
    WSPingMessage,
    WSSubscribeMessage,
    WSSubscribeJobsMessage,
    WSUnsubscribeJobsMessage,
]


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


class WSSubscribeJobsSuccessResponse(BaseModel):
    """Response sent on successful job subscription."""

    type: Literal["subscribe_jobs_success"] = "subscribe_jobs_success"
    job_types: list[str] | None = Field(description="Subscribed job types (None = all)")
    job_ids: list[str] | None = Field(description="Subscribed job IDs (None = all)")


class WSUnsubscribeJobsSuccessResponse(BaseModel):
    """Response sent on successful job unsubscription."""

    type: Literal["unsubscribe_jobs_success"] = "unsubscribe_jobs_success"


class WSJobStateMessage(BaseModel):
    """Initial job state sent when subscribing with include_active_state=true.

    Contains snapshot of active jobs matching the subscription filters.
    """

    type: Literal["job_state"] = "job_state"
    jobs: list[Dict[str, Any]] = Field(description="List of active job states")


@dataclass
class JobSubscription:
    """Tracks a client's job event subscription filters."""

    job_types: set[str] | None = None  # None = all types
    job_ids: set[str] | None = None  # None = all jobs

    def matches(self, event: Dict[str, Any]) -> bool:
        """Check if an event matches this subscription's filters.

        Args:
            event: Event dict with event_type and payload

        Returns:
            True if event matches filters, False otherwise
        """
        event_type = event.get("event_type", "")

        # Only filter job events
        if not event_type.startswith("job_"):
            return True  # Non-job events pass through

        payload = event.get("payload", {})
        job_type = payload.get("job_type")
        job_id = payload.get("job_id")

        # Check job type filter
        if self.job_types is not None and job_type not in self.job_types:
            return False

        # Check job ID filter
        if self.job_ids is not None and job_id not in self.job_ids:
            return False

        return True


class ConnectionManager:
    """Manages WebSocket connections for broadcast events.

    Thread-safe connection tracking with broadcast support for
    real-time event distribution to connected clients. Supports
    per-connection job event subscriptions with filtering.

    Note: This manager does NOT accept connections automatically.
    The caller must call websocket.accept() before adding to manager,
    allowing for authentication to occur first.
    """

    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Set[WebSocket] = set()
        self._job_subscriptions: Dict[WebSocket, JobSubscription] = {}
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
            self._job_subscriptions.pop(websocket, None)
        logger.debug(
            "websocket_disconnected",
            total_connections=len(self.active_connections),
        )

    async def subscribe_jobs(
        self,
        websocket: WebSocket,
        job_types: list[str] | None = None,
        job_ids: list[str] | None = None,
    ) -> None:
        """Subscribe a connection to job events with optional filters.

        Args:
            websocket: WebSocket connection to subscribe
            job_types: Filter by job types (None = all types)
            job_ids: Filter by job IDs (None = all jobs)
        """
        async with self._lock:
            self._job_subscriptions[websocket] = JobSubscription(
                job_types=set(job_types) if job_types else None,
                job_ids=set(job_ids) if job_ids else None,
            )
        logger.debug(
            "websocket_subscribed_jobs",
            job_types=job_types,
            job_ids=job_ids,
        )

    async def unsubscribe_jobs(self, websocket: WebSocket) -> None:
        """Unsubscribe a connection from job events.

        Args:
            websocket: WebSocket connection to unsubscribe
        """
        async with self._lock:
            self._job_subscriptions.pop(websocket, None)
        logger.debug("websocket_unsubscribed_jobs")

    def has_job_subscription(self, websocket: WebSocket) -> bool:
        """Check if a connection has an active job subscription.

        Args:
            websocket: WebSocket connection to check

        Returns:
            True if subscribed to job events
        """
        return websocket in self._job_subscriptions

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

        For job events, only sends to clients with matching subscriptions.
        Non-job events are sent to all clients.

        Args:
            message: Dictionary to broadcast as JSON
        """
        if not self.active_connections:
            return

        event_type = message.get("event_type", "")
        is_job_event = event_type.startswith("job_")
        dead_connections: Set[WebSocket] = set()

        async with self._lock:
            connections = list(self.active_connections)
            subscriptions = dict(self._job_subscriptions)

        for connection in connections:
            try:
                # For job events, check subscription and filters
                if is_job_event:
                    subscription = subscriptions.get(connection)
                    if subscription is None:
                        # No job subscription, skip this client
                        continue
                    if not subscription.matches(message):
                        # Doesn't match filters, skip
                        continue

                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)

        if dead_connections:
            async with self._lock:
                self.active_connections -= dead_connections
                for conn in dead_connections:
                    self._job_subscriptions.pop(conn, None)

    @property
    def connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self.active_connections)

    @property
    def job_subscription_count(self) -> int:
        """Get the number of connections with job subscriptions."""
        return len(self._job_subscriptions)


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
    except WebSocketDisconnect:
        # Client disconnected before sending auth message - this is normal
        logger.debug("websocket_auth_client_disconnected")
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
        if repo._connection is None:
            raise RuntimeError("Database connection not initialized")
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

    Job Subscriptions:
        After authentication, clients can subscribe to job events:
        - {"type": "subscribe_jobs"} - Subscribe to all job events
        - {"type": "subscribe_jobs", "job_types": ["download_youtube"]} - Filter by type
        - {"type": "subscribe_jobs", "job_ids": ["uuid"]} - Filter by job ID
        - {"type": "subscribe_jobs", "include_active_state": true} - Get current state
        - {"type": "unsubscribe_jobs"} - Stop receiving job events

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
                    msg_type = data.get("type")

                    if msg_type == "ping":
                        await websocket.send_json(WSPongResponse().model_dump())

                    elif msg_type == "subscribe_jobs":
                        # Parse and validate subscription message
                        try:
                            sub_msg = WSSubscribeJobsMessage.model_validate(data)
                        except ValidationError as e:
                            logger.warning("invalid_subscribe_jobs_message", error=str(e))
                            continue

                        # Register subscription
                        await connection_manager.subscribe_jobs(
                            websocket,
                            job_types=sub_msg.job_types,
                            job_ids=sub_msg.job_ids,
                        )

                        # Send confirmation
                        await websocket.send_json(
                            WSSubscribeJobsSuccessResponse(
                                job_types=sub_msg.job_types,
                                job_ids=sub_msg.job_ids,
                            ).model_dump()
                        )

                        # Send current active job state if requested
                        if sub_msg.include_active_state:
                            try:
                                queue = get_job_queue()
                                active_jobs = await queue.list_jobs()

                                # Filter to non-terminal jobs matching subscription
                                job_states = []
                                for job in active_jobs:
                                    if job.is_terminal:
                                        continue

                                    # Apply filters
                                    if (
                                        sub_msg.job_types
                                        and job.type.value not in sub_msg.job_types
                                    ):
                                        continue
                                    if sub_msg.job_ids and job.id not in sub_msg.job_ids:
                                        continue

                                    job_states.append(
                                        {
                                            "job_id": job.id,
                                            "job_type": job.type.value,
                                            "status": job.status.value,
                                            "progress": job.progress,
                                            "current_step": job.current_step,
                                            "processed_items": job.processed_items,
                                            "total_items": job.total_items,
                                            "created_at": (
                                                job.created_at.isoformat()
                                                if job.created_at
                                                else None
                                            ),
                                            "started_at": (
                                                job.started_at.isoformat()
                                                if job.started_at
                                                else None
                                            ),
                                            "metadata": job.metadata,
                                        }
                                    )

                                await websocket.send_json(
                                    WSJobStateMessage(jobs=job_states).model_dump()
                                )
                            except RuntimeError:
                                # Job queue not initialized
                                await websocket.send_json(WSJobStateMessage(jobs=[]).model_dump())

                        logger.info(
                            "websocket_subscribed_jobs",
                            job_types=sub_msg.job_types,
                            job_ids=sub_msg.job_ids,
                        )

                    elif msg_type == "unsubscribe_jobs":
                        await connection_manager.unsubscribe_jobs(websocket)
                        await websocket.send_json(WSUnsubscribeJobsSuccessResponse().model_dump())
                        logger.info("websocket_unsubscribed_jobs")

                except (json.JSONDecodeError, Exception) as e:
                    logger.debug("websocket_message_parse_error", error=str(e))

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
