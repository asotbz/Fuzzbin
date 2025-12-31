"""WebSocket event schemas for real-time updates."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of WebSocket events that can be broadcast."""

    CONFIG_CHANGED = "config_changed"
    """Configuration field was modified."""

    JOB_PROGRESS = "job_progress"
    """Background job progress update."""

    JOB_COMPLETED = "job_completed"
    """Background job completed successfully."""

    JOB_FAILED = "job_failed"
    """Background job failed with error."""

    CLIENT_RELOADED = "client_reloaded"
    """API client was reloaded with new configuration."""


class ConfigChangedPayload(BaseModel):
    """Payload for CONFIG_CHANGED events."""

    path: str = Field(
        description="Dot-notation path of the changed field",
        examples=["http.timeout", "apis.discogs.rate_limit.requests_per_minute"],
    )
    old_value: Any = Field(
        description="Previous value of the field",
    )
    new_value: Any = Field(
        description="New value of the field",
    )
    safety_level: str = Field(
        description="Safety level of the change: safe, requires_reload, affects_state",
        examples=["safe", "requires_reload"],
    )
    required_actions: List[str] = Field(
        default_factory=list,
        description="List of required actions after this change",
        examples=[["reload_client:discogs"]],
    )


class JobProgressPayload(BaseModel):
    """Payload for JOB_PROGRESS events."""

    job_id: str = Field(
        description="Unique job identifier",
    )
    progress: float = Field(
        ge=0.0,
        le=1.0,
        description="Progress percentage (0.0-1.0)",
    )
    current_step: str = Field(
        description="Current step description",
    )
    processed_items: int = Field(
        description="Number of items processed",
    )
    total_items: int = Field(
        description="Total number of items to process",
    )
    # Optional download-specific fields
    download_speed: Optional[float] = Field(
        default=None,
        description="Download speed in MB/s (for download jobs)",
    )
    eta_seconds: Optional[int] = Field(
        default=None,
        description="Estimated time remaining in seconds (for download jobs)",
    )


class JobCompletedPayload(BaseModel):
    """Payload for JOB_COMPLETED events."""

    job_id: str = Field(
        description="Unique job identifier",
    )
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Job result data",
    )


class JobFailedPayload(BaseModel):
    """Payload for JOB_FAILED events."""

    job_id: str = Field(
        description="Unique job identifier",
    )
    error: str = Field(
        description="Error message",
    )
    error_type: Optional[str] = Field(
        default=None,
        description="Error type/class name",
    )


class ClientReloadedPayload(BaseModel):
    """Payload for CLIENT_RELOADED events."""

    client_name: str = Field(
        description="Name of the reloaded client",
        examples=["discogs", "imvdb"],
    )
    success: bool = Field(
        description="Whether the reload was successful",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if reload failed",
    )


class WebSocketEvent(BaseModel):
    """Standard WebSocket event message format.

    All WebSocket events follow this structure for consistent handling
    by clients.

    Example:
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
    """

    event_type: EventType = Field(
        description="Type of event",
    )
    timestamp: datetime = Field(
        description="When the event occurred (ISO 8601 UTC)",
    )
    payload: Dict[str, Any] = Field(
        description="Event-specific payload data",
    )

    @classmethod
    def config_changed(
        cls,
        path: str,
        old_value: Any,
        new_value: Any,
        safety_level: str,
        required_actions: Optional[List[str]] = None,
    ) -> "WebSocketEvent":
        """Create a CONFIG_CHANGED event."""
        return cls(
            event_type=EventType.CONFIG_CHANGED,
            timestamp=datetime.now(timezone.utc),
            payload=ConfigChangedPayload(
                path=path,
                old_value=old_value,
                new_value=new_value,
                safety_level=safety_level,
                required_actions=required_actions or [],
            ).model_dump(),
        )

    @classmethod
    def job_progress(
        cls,
        job_id: str,
        progress: float,
        current_step: str,
        processed_items: int,
        total_items: int,
    ) -> "WebSocketEvent":
        """Create a JOB_PROGRESS event."""
        return cls(
            event_type=EventType.JOB_PROGRESS,
            timestamp=datetime.now(timezone.utc),
            payload=JobProgressPayload(
                job_id=job_id,
                progress=progress,
                current_step=current_step,
                processed_items=processed_items,
                total_items=total_items,
            ).model_dump(),
        )

    @classmethod
    def job_completed(
        cls,
        job_id: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> "WebSocketEvent":
        """Create a JOB_COMPLETED event."""
        return cls(
            event_type=EventType.JOB_COMPLETED,
            timestamp=datetime.now(timezone.utc),
            payload=JobCompletedPayload(
                job_id=job_id,
                result=result,
            ).model_dump(),
        )

    @classmethod
    def job_failed(
        cls,
        job_id: str,
        error: str,
        error_type: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create a JOB_FAILED event."""
        return cls(
            event_type=EventType.JOB_FAILED,
            timestamp=datetime.now(timezone.utc),
            payload=JobFailedPayload(
                job_id=job_id,
                error=error,
                error_type=error_type,
            ).model_dump(),
        )

    @classmethod
    def client_reloaded(
        cls,
        client_name: str,
        success: bool,
        error: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create a CLIENT_RELOADED event."""
        return cls(
            event_type=EventType.CLIENT_RELOADED,
            timestamp=datetime.now(timezone.utc),
            payload=ClientReloadedPayload(
                client_name=client_name,
                success=success,
                error=error,
            ).model_dump(),
        )
