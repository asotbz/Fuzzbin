"""Async event bus for real-time WebSocket updates.

Provides a centralized event emission system with per-job debouncing for
progress updates. Terminal events (completed, failed, cancelled) bypass
debouncing for immediate delivery.

Example:
    >>> from fuzzbin.core.event_bus import get_event_bus, EventBus
    >>>
    >>> # Initialize during app startup
    >>> bus = init_event_bus()
    >>>
    >>> # Emit job progress (debounced at 250ms)
    >>> await bus.emit_job_progress(job)
    >>>
    >>> # Emit terminal events (immediate)
    >>> await bus.emit_job_completed(job)
    >>> await bus.emit_job_failed(job, error="Something went wrong")
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Coroutine

import structlog

if TYPE_CHECKING:
    from fuzzbin.tasks.models import Job

logger = structlog.get_logger(__name__)

# Debounce interval for progress updates (in seconds)
PROGRESS_DEBOUNCE_INTERVAL = 0.25  # 250ms


@dataclass
class DebouncedProgress:
    """Holds pending progress update for debouncing."""

    job_id: str
    progress: float
    current_step: str
    processed_items: int
    total_items: int
    job_type: str
    download_speed: float | None = None
    eta_seconds: int | None = None
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    flush_task: asyncio.Task | None = field(default=None, repr=False)


class EventBus:
    """Centralized async event bus with debounced progress updates.

    Manages event emission to WebSocket clients via ConnectionManager.
    Progress events are debounced per-job (250ms interval) while terminal
    events (completed, failed, cancelled, started) are delivered immediately.

    Attributes:
        _pending_progress: Dict of job_id -> DebouncedProgress for batching
        _lock: Async lock for thread-safe access to pending state
        _broadcast_fn: Optional function to broadcast events (injected)
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._pending_progress: dict[str, DebouncedProgress] = {}
        self._lock = asyncio.Lock()
        self._broadcast_fn: Callable[[dict[str, Any]], Coroutine[Any, Any, None]] | None = None
        self._started = False

    def set_broadcast_function(
        self,
        broadcast_fn: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Set the broadcast function for sending events to clients.

        This should be called during app startup to inject the ConnectionManager's
        broadcast_dict method.

        Args:
            broadcast_fn: Async function that broadcasts a dict to all WebSocket clients
        """
        self._broadcast_fn = broadcast_fn
        self._started = True
        logger.info("event_bus_broadcast_configured")

    async def _broadcast(self, event: dict[str, Any]) -> None:
        """Internal method to broadcast an event.

        Args:
            event: Event dictionary to broadcast
        """
        if not self._broadcast_fn:
            logger.debug("event_bus_no_broadcast_fn", event_type=event.get("event_type"))
            return

        try:
            await self._broadcast_fn(event)
        except Exception as e:
            logger.error("event_bus_broadcast_error", error=str(e), exc_info=True)

    def _create_event(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a standardized event dictionary.

        Args:
            event_type: Type of event (e.g., "job_progress", "job_completed")
            payload: Event-specific payload data

        Returns:
            Event dictionary with type, timestamp, and payload
        """
        return {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }

    async def emit_job_started(self, job: "Job") -> None:
        """Emit a job started event (immediate, no debounce).

        Args:
            job: Job that started
        """
        event = self._create_event(
            "job_started",
            {
                "job_id": job.id,
                "job_type": job.type.value,
                "priority": job.priority.value,
                "metadata": job.metadata,
            },
        )
        await self._broadcast(event)
        logger.debug("event_bus_job_started", job_id=job.id, job_type=job.type.value)

    async def emit_job_progress(
        self,
        job: "Job",
        download_speed: float | None = None,
        eta_seconds: int | None = None,
    ) -> None:
        """Emit a job progress event (debounced at 250ms per job).

        Multiple rapid progress updates for the same job are batched and
        only the latest state is sent after the debounce interval.

        Args:
            job: Job with updated progress
            download_speed: Optional download speed in MB/s (for download jobs)
            eta_seconds: Optional estimated time remaining in seconds
        """
        async with self._lock:
            pending = self._pending_progress.get(job.id)

            if pending and pending.flush_task and not pending.flush_task.done():
                # Update pending state, don't create new flush task
                pending.progress = job.progress
                pending.current_step = job.current_step
                pending.processed_items = job.processed_items
                pending.total_items = job.total_items
                pending.download_speed = download_speed
                pending.eta_seconds = eta_seconds
                pending.last_update = datetime.now(timezone.utc)
                return

            # Create new pending progress
            debounced = DebouncedProgress(
                job_id=job.id,
                progress=job.progress,
                current_step=job.current_step,
                processed_items=job.processed_items,
                total_items=job.total_items,
                job_type=job.type.value,
                download_speed=download_speed,
                eta_seconds=eta_seconds,
            )
            self._pending_progress[job.id] = debounced

            # Schedule flush after debounce interval
            debounced.flush_task = asyncio.create_task(self._flush_progress_after_delay(job.id))

    async def _flush_progress_after_delay(self, job_id: str) -> None:
        """Flush pending progress after debounce delay.

        Args:
            job_id: Job ID to flush progress for
        """
        await asyncio.sleep(PROGRESS_DEBOUNCE_INTERVAL)
        await self._flush_progress(job_id)

    async def _flush_progress(self, job_id: str) -> None:
        """Immediately flush pending progress for a job.

        Args:
            job_id: Job ID to flush
        """
        async with self._lock:
            pending = self._pending_progress.pop(job_id, None)

        if not pending:
            return

        payload: dict[str, Any] = {
            "job_id": pending.job_id,
            "job_type": pending.job_type,
            "progress": pending.progress,
            "current_step": pending.current_step,
            "processed_items": pending.processed_items,
            "total_items": pending.total_items,
        }

        # Add optional download-specific fields
        if pending.download_speed is not None:
            payload["download_speed"] = pending.download_speed
        if pending.eta_seconds is not None:
            payload["eta_seconds"] = pending.eta_seconds

        event = self._create_event("job_progress", payload)
        await self._broadcast(event)

    async def emit_job_completed(
        self,
        job: "Job",
        result: dict[str, Any] | None = None,
    ) -> None:
        """Emit a job completed event (immediate, flushes pending progress).

        Args:
            job: Completed job
            result: Optional result data (defaults to job.result)
        """
        # Flush any pending progress first
        await self._cancel_and_flush_progress(job.id)

        event = self._create_event(
            "job_completed",
            {
                "job_id": job.id,
                "job_type": job.type.value,
                "result": result if result is not None else job.result,
            },
        )
        await self._broadcast(event)
        logger.debug("event_bus_job_completed", job_id=job.id)

    async def emit_job_failed(
        self,
        job: "Job",
        error: str | None = None,
        error_type: str | None = None,
    ) -> None:
        """Emit a job failed event (immediate, flushes pending progress).

        Args:
            job: Failed job
            error: Error message (defaults to job.error)
            error_type: Optional error type/class name
        """
        # Flush any pending progress first
        await self._cancel_and_flush_progress(job.id)

        event = self._create_event(
            "job_failed",
            {
                "job_id": job.id,
                "job_type": job.type.value,
                "error": error if error is not None else job.error,
                "error_type": error_type,
            },
        )
        await self._broadcast(event)
        logger.debug("event_bus_job_failed", job_id=job.id, error=error or job.error)

    async def emit_job_cancelled(self, job: "Job") -> None:
        """Emit a job cancelled event (immediate, flushes pending progress).

        Args:
            job: Cancelled job
        """
        # Flush any pending progress first
        await self._cancel_and_flush_progress(job.id)

        event = self._create_event(
            "job_cancelled",
            {
                "job_id": job.id,
                "job_type": job.type.value,
            },
        )
        await self._broadcast(event)
        logger.debug("event_bus_job_cancelled", job_id=job.id)

    async def emit_job_timeout(self, job: "Job") -> None:
        """Emit a job timeout event (immediate, flushes pending progress).

        Args:
            job: Timed out job
        """
        # Flush any pending progress first
        await self._cancel_and_flush_progress(job.id)

        event = self._create_event(
            "job_timeout",
            {
                "job_id": job.id,
                "job_type": job.type.value,
                "timeout_seconds": job.timeout_seconds,
            },
        )
        await self._broadcast(event)
        logger.debug("event_bus_job_timeout", job_id=job.id)

    async def _cancel_and_flush_progress(self, job_id: str) -> None:
        """Cancel pending debounce and flush progress immediately.

        Used by terminal events to ensure final progress is sent before
        the terminal event.

        Args:
            job_id: Job ID to flush
        """
        async with self._lock:
            pending = self._pending_progress.get(job_id)
            if pending and pending.flush_task:
                pending.flush_task.cancel()
                try:
                    await pending.flush_task
                except asyncio.CancelledError:
                    pass

        # Flush the progress (will pop from dict)
        await self._flush_progress(job_id)

    async def emit_video_updated(
        self,
        video_id: int,
        fields_changed: list[str],
        thumbnail_timestamp: int | None = None,
    ) -> None:
        """Emit a video updated event for real-time UI updates.

        Used to notify clients when video metadata or thumbnail has changed,
        enabling cache invalidation and UI refresh.

        Args:
            video_id: ID of the updated video
            fields_changed: List of field names that changed (e.g., ["thumbnail", "file_properties"])
            thumbnail_timestamp: Unix timestamp for cache-busting when thumbnail changed
        """
        payload: dict[str, Any] = {
            "video_id": video_id,
            "fields_changed": fields_changed,
        }

        # Include timestamp for cache-busting when thumbnail is updated
        if thumbnail_timestamp is not None and "thumbnail" in fields_changed:
            payload["thumbnail_timestamp"] = thumbnail_timestamp

        event = self._create_event("video_updated", payload)
        await self._broadcast(event)
        logger.debug(
            "event_bus_video_updated",
            video_id=video_id,
            fields_changed=fields_changed,
        )

    async def shutdown(self) -> None:
        """Shutdown the event bus, cancelling all pending flush tasks."""
        async with self._lock:
            for pending in self._pending_progress.values():
                if pending.flush_task and not pending.flush_task.done():
                    pending.flush_task.cancel()
                    try:
                        await pending.flush_task
                    except asyncio.CancelledError:
                        pass
            self._pending_progress.clear()

        self._started = False
        logger.info("event_bus_shutdown")


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance.

    Returns:
        EventBus singleton

    Raises:
        RuntimeError: If event bus not initialized
    """
    if _event_bus is None:
        raise RuntimeError("Event bus not initialized. Call init_event_bus() first.")
    return _event_bus


def init_event_bus() -> EventBus:
    """Initialize the global event bus.

    Returns:
        EventBus instance
    """
    global _event_bus
    _event_bus = EventBus()
    logger.info("event_bus_initialized")
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (for testing)."""
    global _event_bus
    _event_bus = None
