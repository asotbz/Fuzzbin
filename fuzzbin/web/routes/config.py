"""Configuration management endpoints."""

from typing import Annotated, Any, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

import fuzzbin
from fuzzbin.auth.schemas import UserInfo
from fuzzbin.common.config import ConfigSafetyLevel, get_safety_level
from fuzzbin.common.config_manager import (
    ConfigManager,
    ConfigManagerError,
    ConfigValidationError,
)
from fuzzbin.web.dependencies import require_auth
from fuzzbin.web.schemas.common import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES
from fuzzbin.web.schemas.config import (
    ClientInfo,
    ClientListResponse,
    ClientStatsResponse,
    ConfigConflictDetail,
    ConfigConflictResponse,
    ConfigFieldResponse,
    ConfigHistoryEntry,
    ConfigHistoryResponse,
    ConfigResponse,
    ConfigUndoRedoResponse,
    ConfigUpdateRequest,
    ConfigUpdateResponse,
    RequiredAction,
    SafetyLevel,
    SafetyLevelInfo,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/config", tags=["Configuration"])


def get_config_manager() -> ConfigManager:
    """Get the global ConfigManager instance.

    Returns:
        ConfigManager instance

    Raises:
        HTTPException(500): If ConfigManager is not initialized
    """
    try:
        return fuzzbin.get_config_manager()
    except RuntimeError as e:
        logger.error("config_manager_not_initialized", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration manager not initialized",
        )


def _safety_level_to_schema(level: ConfigSafetyLevel) -> SafetyLevel:
    """Convert internal ConfigSafetyLevel to schema SafetyLevel."""
    return SafetyLevel(level.value)


def _get_required_actions(path: str, safety_level: ConfigSafetyLevel) -> List[RequiredAction]:
    """Generate required actions based on field path and safety level.

    Args:
        path: Dot-notation config path
        safety_level: Safety level of the field

    Returns:
        List of required actions for this field change
    """
    actions = []

    if safety_level == ConfigSafetyLevel.REQUIRES_RELOAD:
        # Check if this is an API client config
        if path.startswith("apis."):
            parts = path.split(".")
            if len(parts) >= 2:
                api_name = parts[1]
                actions.append(
                    RequiredAction(
                        action_type=f"reload_client:{api_name}",
                        target=api_name,
                        description=f"Reload {api_name} API client to apply changes",
                    )
                )
        elif path.startswith("http.max_connections") or path.startswith(
            "http.max_keepalive_connections"
        ):
            actions.append(
                RequiredAction(
                    action_type="restart_http_pool",
                    target="http",
                    description="Restart HTTP connection pool to apply changes",
                )
            )
        elif path.startswith("cache."):
            actions.append(
                RequiredAction(
                    action_type="restart_cache",
                    target="cache",
                    description="Restart cache system to apply changes",
                )
            )

    elif safety_level == ConfigSafetyLevel.AFFECTS_STATE:
        if path in ("config_dir", "library_dir"):
            actions.append(
                RequiredAction(
                    action_type="restart_service",
                    target="application",
                    description="Restart application to use new directory paths",
                )
            )
        elif path.startswith("file_manager.") or path.startswith("thumbnail.") or path.startswith("backup.output_dir"):
            actions.append(
                RequiredAction(
                    action_type="restart_file_manager",
                    target="file_manager",
                    description="Restart file manager to apply directory changes",
                )
            )
        elif "storage_path" in path:
            api_name = path.split(".")[1] if path.startswith("apis.") else "default"
            actions.append(
                RequiredAction(
                    action_type=f"migrate_cache:{api_name}",
                    target=api_name,
                    description=f"Migrate cache data to new storage path for {api_name}",
                )
            )

    return actions


@router.get(
    "",
    response_model=ConfigResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Get current configuration",
    description="""
Retrieve the complete current configuration as a nested dictionary.

The configuration includes all settings for HTTP, logging, database, APIs,
and other subsystems. API credentials are returned in full (single-user mode).
    """,
)
async def get_config(
    current_user: Annotated[UserInfo, Depends(require_auth)],
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigResponse:
    """Get the complete current configuration."""
    config = manager.get_config()
    config_path = manager._config_path

    return ConfigResponse(
        config=config.model_dump(mode="json"),
        config_path=str(config_path) if config_path else None,
    )


@router.get(
    "/field/{path:path}",
    response_model=ConfigFieldResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        404: COMMON_ERROR_RESPONSES[404],
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Get configuration field",
    description="""
Retrieve a specific configuration field by dot-notation path.

Examples:
- `http.timeout` - HTTP timeout setting
- `apis.discogs.rate_limit.requests_per_minute` - Discogs rate limit
- `logging.level` - Current log level
    """,
)
async def get_config_field(
    path: str,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigFieldResponse:
    """Get a specific configuration field by path."""
    try:
        value = manager._get_nested(manager.get_config(), path)
        safety_level = get_safety_level(path)

        # Convert Pydantic models to dict for JSON response
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")

        return ConfigFieldResponse(
            path=path,
            value=value,
            safety_level=_safety_level_to_schema(safety_level),
        )
    except (AttributeError, KeyError) as e:
        logger.warning("config_field_not_found", path=path, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration field not found: {path}",
        )


@router.patch(
    "",
    response_model=ConfigUpdateResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        400: COMMON_ERROR_RESPONSES[400],
        409: {
            "model": ConfigConflictResponse,
            "description": "Configuration change requires additional actions",
        },
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Update configuration",
    description="""
Update one or more configuration fields.

**Safety Levels:**
- `safe`: Changes apply immediately with no side effects
- `requires_reload`: Components need reloading (API clients, connections)
- `affects_state`: Changes affect persistent state (database paths, directories)

For `requires_reload` or `affects_state` fields, returns **409 Conflict** unless
`force=true` is set. The response includes `required_actions` describing what
needs to happen to fully apply the changes.

**Examples:**
```json
{
    "updates": {
        "http.timeout": 60,
        "logging.level": "DEBUG"
    },
    "description": "Increased timeout for slow network"
}
```
    """,
)
async def update_config(
    request: ConfigUpdateRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigUpdateResponse:
    """Update configuration fields."""
    # Check safety levels for all updates
    affected_fields: List[ConfigConflictDetail] = []
    all_required_actions: List[RequiredAction] = []
    highest_safety = ConfigSafetyLevel.SAFE

    for path, new_value in request.updates.items():
        safety_level = get_safety_level(path)

        # Track highest safety level
        if safety_level == ConfigSafetyLevel.AFFECTS_STATE:
            highest_safety = ConfigSafetyLevel.AFFECTS_STATE
        elif (
            safety_level == ConfigSafetyLevel.REQUIRES_RELOAD
            and highest_safety != ConfigSafetyLevel.AFFECTS_STATE
        ):
            highest_safety = ConfigSafetyLevel.REQUIRES_RELOAD

        # Collect affected fields that require action
        if safety_level in (ConfigSafetyLevel.REQUIRES_RELOAD, ConfigSafetyLevel.AFFECTS_STATE):
            try:
                current_value = manager._get_nested(manager.get_config(), path)
                if hasattr(current_value, "model_dump"):
                    current_value = current_value.model_dump(mode="json")
            except (AttributeError, KeyError):
                current_value = None

            affected_fields.append(
                ConfigConflictDetail(
                    path=path,
                    safety_level=_safety_level_to_schema(safety_level),
                    current_value=current_value,
                    requested_value=new_value,
                )
            )

            actions = _get_required_actions(path, safety_level)
            all_required_actions.extend(actions)

    # Return 409 if non-safe fields and force=false
    if affected_fields and not request.force:
        logger.info(
            "config_update_blocked",
            affected_fields=[f.path for f in affected_fields],
            safety_level=highest_safety.value,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ConfigConflictResponse(
                affected_fields=affected_fields,
                required_actions=all_required_actions,
                message=(
                    f"Changes to {len(affected_fields)} field(s) require additional actions. "
                    "Set force=true to proceed, acknowledging the required actions."
                ),
            ).model_dump(),
        )

    # Apply updates
    try:
        if len(request.updates) == 1:
            # Single field update
            path, value = next(iter(request.updates.items()))
            await manager.update(path, value, description=request.description)
        else:
            # Batch update
            await manager.update_many(request.updates)

        logger.info(
            "config_updated",
            fields=list(request.updates.keys()),
            safety_level=highest_safety.value,
            forced=request.force,
        )

        return ConfigUpdateResponse(
            updated_fields=list(request.updates.keys()),
            safety_level=_safety_level_to_schema(highest_safety),
            required_actions=all_required_actions,
            message=f"Updated {len(request.updates)} field(s) successfully",
        )

    except ConfigValidationError as e:
        logger.warning("config_validation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ConfigManagerError as e:
        logger.error("config_update_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {e}",
        )


@router.get(
    "/history",
    response_model=ConfigHistoryResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Get configuration history",
    description="""
Retrieve recent configuration change history.

History entries include timestamps, descriptions, and undo/redo availability.
Use this to review changes before performing undo/redo operations.
    """,
)
async def get_config_history(
    current_user: Annotated[UserInfo, Depends(require_auth)],
    limit: int = Query(default=10, ge=1, le=100, description="Maximum entries to return"),
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigHistoryResponse:
    """Get configuration change history."""
    snapshots = manager.get_history(limit)
    current_index = manager.history.current_index

    entries = [
        ConfigHistoryEntry(
            timestamp=snap.timestamp,
            description=snap.description,
            is_current=(i == current_index),
        )
        for i, snap in enumerate(reversed(snapshots))
    ]

    # Reverse to show newest first
    entries.reverse()

    return ConfigHistoryResponse(
        entries=entries,
        current_index=current_index,
        can_undo=current_index > 0,
        can_redo=current_index < len(manager.history.snapshots) - 1,
    )


@router.post(
    "/undo",
    response_model=ConfigUndoRedoResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        400: COMMON_ERROR_RESPONSES[400],
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Undo configuration change",
    description="""
Undo the most recent configuration change.

Restores the previous configuration state from history.
The change is automatically saved to the configuration file.
    """,
)
async def undo_config(
    current_user: Annotated[UserInfo, Depends(require_auth)],
    steps: int = Query(default=1, ge=1, le=50, description="Number of steps to undo"),
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigUndoRedoResponse:
    """Undo configuration changes."""
    success = await manager.undo(steps)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No earlier configuration snapshots available",
        )

    current = manager.history.get_current()
    return ConfigUndoRedoResponse(
        success=True,
        description=f"Restored: {current.description}" if current else "Restored previous state",
        timestamp=current.timestamp if current else None,
    )


@router.post(
    "/redo",
    response_model=ConfigUndoRedoResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        400: COMMON_ERROR_RESPONSES[400],
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Redo configuration change",
    description="""
Redo a previously undone configuration change.

Restores the next configuration state from history.
The change is automatically saved to the configuration file.
    """,
)
async def redo_config(
    current_user: Annotated[UserInfo, Depends(require_auth)],
    steps: int = Query(default=1, ge=1, le=50, description="Number of steps to redo"),
    manager: ConfigManager = Depends(get_config_manager),
) -> ConfigUndoRedoResponse:
    """Redo configuration changes."""
    success = await manager.redo(steps)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No later configuration snapshots available",
        )

    current = manager.history.get_current()
    return ConfigUndoRedoResponse(
        success=True,
        description=f"Restored: {current.description}" if current else "Restored next state",
        timestamp=current.timestamp if current else None,
    )


@router.get(
    "/safety/{path:path}",
    response_model=SafetyLevelInfo,
    responses={
        **AUTH_ERROR_RESPONSES,
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Get field safety level",
    description="""
Get the safety level for a configuration field path.

Use this to check what side effects a configuration change may have
before submitting an update request.

**Safety Levels:**
- `safe`: No side effects, changes apply immediately
- `requires_reload`: Components need reloading after change
- `affects_state`: Changes affect persistent state
    """,
)
async def get_field_safety(
    path: str,
    current_user: Annotated[UserInfo, Depends(require_auth)],
) -> SafetyLevelInfo:
    """Get safety level for a configuration field."""
    safety_level = get_safety_level(path)

    # Generate description based on safety level and path
    if safety_level == ConfigSafetyLevel.SAFE:
        description = "This field can be changed without side effects"
    elif safety_level == ConfigSafetyLevel.REQUIRES_RELOAD:
        if path.startswith("apis."):
            parts = path.split(".")
            api_name = parts[1] if len(parts) >= 2 else "the API"
            description = f"Changing this field requires reloading the {api_name} client"
        else:
            description = "Changing this field requires reloading affected components"
    else:  # AFFECTS_STATE
        if "database" in path:
            description = "Changing this field affects database connections (restart required)"
        elif path in ("config_dir", "library_dir"):
            description = "Changing this field affects directory paths (restart required)"
        else:
            description = "Changing this field affects persistent state"

    return SafetyLevelInfo(
        path=path,
        safety_level=_safety_level_to_schema(safety_level),
        description=description,
    )


@router.get(
    "/clients",
    response_model=ClientListResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="List registered API clients",
    description="""
List all API clients registered with the configuration manager.

Registered clients can be hot-reloaded when their configuration changes.
    """,
)
async def list_clients(
    current_user: Annotated[UserInfo, Depends(require_auth)],
    manager: ConfigManager = Depends(get_config_manager),
) -> ClientListResponse:
    """List registered API clients."""
    client_names = manager.list_clients()
    config = manager.get_config()

    clients = []
    for name in client_names:
        base_url = None
        if config.apis and name in config.apis:
            base_url = config.apis[name].base_url

        clients.append(ClientInfo(name=name, base_url=base_url))

    return ClientListResponse(
        clients=clients,
        total=len(clients),
    )


@router.get(
    "/clients/{name}/stats",
    response_model=ClientStatsResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        404: COMMON_ERROR_RESPONSES[404],
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Get API client statistics",
    description="""
Get real-time statistics for a registered API client.

Statistics include:
- Active request count
- Concurrency utilization
- Rate limit token availability
- Rate limit capacity percentage
    """,
)
async def get_client_stats(
    name: str,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    manager: ConfigManager = Depends(get_config_manager),
) -> ClientStatsResponse:
    """Get statistics for a registered API client."""
    stats = manager.get_client_stats(name)

    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client not found: {name}",
        )

    return ClientStatsResponse(
        name=name,
        active_requests=stats.active_requests,
        max_concurrent=stats.max_concurrent,
        available_tokens=stats.available_tokens,
        rate_limit_capacity=stats.rate_limit_capacity,
        utilization_pct=stats.utilization_pct,
        rate_limit_pct=stats.rate_limit_pct,
    )
