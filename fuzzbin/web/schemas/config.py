"""Configuration management API request/response schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SafetyLevel(str, Enum):
    """Safety level for configuration changes.

    Determines what side effects a config change may have.
    """

    SAFE = "safe"
    """Can change without side effects."""

    REQUIRES_RELOAD = "requires_reload"
    """Need to recreate components (API clients, connections)."""

    AFFECTS_STATE = "affects_state"
    """Changes persistent files, database paths, or connections."""


class RequiredAction(BaseModel):
    """Action required after a configuration change.

    Provides structured information for UI/client to handle config changes
    that require additional steps.
    """

    action_type: str = Field(
        description="Type of action required: 'reload_client', 'reconnect_database', 'restart_cache', 'restart_service'",
        examples=["reload_client:imvdb", "reconnect_database", "restart_cache:discogs"],
    )
    target: Optional[str] = Field(
        default=None,
        description="Target of the action (e.g., API client name)",
        examples=["imvdb", "discogs"],
    )
    description: str = Field(
        description="Human-readable description of the required action",
        examples=["Restart IMVDb client to apply rate limit changes"],
    )


class ConfigResponse(BaseModel):
    """Full configuration response.

    Returns the complete current configuration state.
    """

    config: Dict[str, Any] = Field(
        description="Complete configuration as nested dictionary",
    )
    config_path: Optional[str] = Field(
        default=None,
        description="Path to the YAML configuration file",
        examples=["/Users/jbruns/Fuzzbin/config/config.yaml"],
    )


class ConfigFieldResponse(BaseModel):
    """Response for a single configuration field."""

    path: str = Field(
        description="Dot-notation path to the field",
        examples=["http.timeout", "apis.discogs.rate_limit.requests_per_minute"],
    )
    value: Any = Field(
        description="Current value of the field",
    )
    safety_level: SafetyLevel = Field(
        description="Safety level for modifying this field",
    )


class ConfigUpdateRequest(BaseModel):
    """Request to update one or more configuration fields."""

    updates: Dict[str, Any] = Field(
        description="Dictionary mapping dot-notation paths to new values",
        examples=[{"http.timeout": 60, "logging.level": "DEBUG"}],
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional description of the change for history",
        examples=["Increased timeout for slow network"],
    )
    force: bool = Field(
        default=False,
        description="Force update even for REQUIRES_RELOAD or AFFECTS_STATE fields (acknowledges side effects)",
    )


class ConfigUpdateResponse(BaseModel):
    """Response after successful configuration update."""

    updated_fields: List[str] = Field(
        description="List of field paths that were updated",
        examples=[["http.timeout", "logging.level"]],
    )
    safety_level: SafetyLevel = Field(
        description="Highest safety level among updated fields",
    )
    required_actions: List[RequiredAction] = Field(
        default_factory=list,
        description="Actions required to fully apply the changes",
    )
    message: str = Field(
        description="Human-readable summary of the update",
        examples=["Updated 2 fields successfully"],
    )


class ConfigConflictDetail(BaseModel):
    """Details about a field that would cause side effects."""

    path: str = Field(
        description="Dot-notation path to the field",
    )
    safety_level: SafetyLevel = Field(
        description="Safety level of the field",
    )
    current_value: Any = Field(
        description="Current value of the field",
    )
    requested_value: Any = Field(
        description="Requested new value",
    )


class ConfigConflictResponse(BaseModel):
    """Response when config update would cause side effects.

    Returned with HTTP 409 Conflict when REQUIRES_RELOAD or AFFECTS_STATE
    fields are modified without force=true.
    """

    detail: str = Field(
        default="Configuration change requires additional actions",
        description="Error message",
    )
    error_type: str = Field(
        default="config_conflict",
        description="Error type identifier",
    )
    affected_fields: List[ConfigConflictDetail] = Field(
        description="Fields that would cause side effects",
    )
    required_actions: List[RequiredAction] = Field(
        description="Actions that would be required after update",
    )
    message: str = Field(
        description="Human-readable explanation",
        examples=[
            "Changes to rate limit settings require reloading the API client. "
            "Set force=true to proceed, or use the clients endpoint to reload affected clients."
        ],
    )


class ConfigHistoryEntry(BaseModel):
    """Entry in configuration change history."""

    timestamp: datetime = Field(
        description="When the change was made",
    )
    description: str = Field(
        description="Human-readable description of the change",
        examples=["Changed http.timeout: 30 → 60"],
    )
    is_current: bool = Field(
        default=False,
        description="Whether this is the current configuration state",
    )


class ConfigHistoryResponse(BaseModel):
    """Response containing configuration change history."""

    entries: List[ConfigHistoryEntry] = Field(
        description="List of history entries (newest first)",
    )
    current_index: int = Field(
        description="Index of the current configuration in history",
    )
    can_undo: bool = Field(
        description="Whether undo is available",
    )
    can_redo: bool = Field(
        description="Whether redo is available",
    )


class ConfigUndoRedoResponse(BaseModel):
    """Response after undo or redo operation."""

    success: bool = Field(
        description="Whether the operation succeeded",
    )
    description: str = Field(
        description="Description of the restored state",
        examples=["Restored: Changed http.timeout: 30 → 60"],
    )
    timestamp: datetime = Field(
        description="Timestamp of the restored snapshot",
    )


class SafetyLevelInfo(BaseModel):
    """Information about a field's safety level."""

    path: str = Field(
        description="Dot-notation path to the field",
        examples=["apis.discogs.rate_limit.requests_per_minute"],
    )
    safety_level: SafetyLevel = Field(
        description="Safety level for the field",
    )
    description: str = Field(
        description="What this safety level means for this field",
        examples=["Changing rate limit settings requires reloading the Discogs API client"],
    )


class ClientInfo(BaseModel):
    """Information about a registered API client."""

    name: str = Field(
        description="Client identifier",
        examples=["discogs", "imvdb"],
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Base URL for the API",
        examples=["https://api.discogs.com"],
    )


class ClientStatsResponse(BaseModel):
    """Real-time statistics for an API client."""

    name: str = Field(
        description="Client identifier",
        examples=["discogs"],
    )
    active_requests: int = Field(
        description="Number of currently active requests",
        examples=[3],
    )
    max_concurrent: int = Field(
        description="Maximum allowed concurrent requests",
        examples=[5],
    )
    available_tokens: float = Field(
        description="Available rate limit tokens",
        examples=[45.5],
    )
    rate_limit_capacity: float = Field(
        description="Total rate limit token capacity (burst size)",
        examples=[60.0],
    )
    utilization_pct: float = Field(
        description="Concurrency utilization percentage (0-100)",
        examples=[60.0],
    )
    rate_limit_pct: float = Field(
        description="Rate limit capacity percentage (0-100)",
        examples=[75.8],
    )


class ClientListResponse(BaseModel):
    """Response containing list of registered API clients."""

    clients: List[ClientInfo] = Field(
        description="List of registered API clients",
    )
    total: int = Field(
        description="Total number of registered clients",
    )
