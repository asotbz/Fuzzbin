"""Configuration management with hot-reload, history, and event callbacks."""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union
from weakref import WeakMethod

import structlog
from pydantic import ValidationError

from .config import Config, ConfigSafetyLevel, get_safety_level

logger = structlog.get_logger(__name__)


# ============================================================================
# Exceptions
# ============================================================================


class ConfigManagerError(Exception):
    """Base exception for configuration manager errors."""

    pass


class ConfigValidationError(ConfigManagerError):
    """Configuration validation failed."""

    pass


class ConfigSaveError(ConfigManagerError):
    """Failed to save configuration to YAML."""

    pass


class ClientReloadError(ConfigManagerError):
    """Failed to reload API client with new configuration."""

    pass


# ============================================================================
# Event System
# ============================================================================


@dataclass
class ConfigChangeEvent:
    """Event data for configuration changes."""

    path: str  # Dot-notation path (e.g., "http.timeout")
    old_value: Any  # Previous value
    new_value: Any  # New value
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    safety_level: ConfigSafetyLevel = ConfigSafetyLevel.SAFE


# Type alias for callbacks (can be sync or async)
ConfigCallback = Callable[[ConfigChangeEvent], Union[None, Awaitable[None]]]


# ============================================================================
# Configuration History
# ============================================================================


@dataclass
class ConfigSnapshot:
    """Immutable configuration snapshot for history/rollback."""

    config: Config
    timestamp: datetime
    description: str  # Human-readable change description

    def __post_init__(self) -> None:
        """Deep copy config to prevent mutation."""
        # Create immutable copy by round-tripping through Pydantic
        self.config = Config.model_validate(self.config.model_dump())


class ConfigHistory:
    """Manages configuration history with rollback support."""

    def __init__(self, max_snapshots: int = 50):
        """
        Initialize configuration history.

        Args:
            max_snapshots: Maximum number of snapshots to retain (default: 50)
        """
        self.snapshots: deque[ConfigSnapshot] = deque(maxlen=max_snapshots)
        self.current_index: int = -1  # Points to current snapshot

    def save_snapshot(self, config: Config, description: str) -> None:
        """
        Save a configuration snapshot.

        Args:
            config: Configuration to snapshot
            description: Human-readable description of changes
        """
        snapshot = ConfigSnapshot(
            config=config,
            timestamp=datetime.now(timezone.utc),
            description=description,
        )

        # If we're not at the latest, discard forward history
        if self.current_index < len(self.snapshots) - 1:
            # Truncate forward history
            while len(self.snapshots) > self.current_index + 1:
                self.snapshots.pop()

        self.snapshots.append(snapshot)
        self.current_index = len(self.snapshots) - 1

        logger.debug(
            "config_snapshot_saved",
            description=description,
            index=self.current_index,
            total_snapshots=len(self.snapshots),
        )

    def rollback(self, steps: int = 1) -> Optional[Config]:
        """
        Rollback to previous configuration.

        Args:
            steps: Number of snapshots to go back

        Returns:
            Previous config, or None if can't rollback
        """
        target_index = self.current_index - steps
        if target_index < 0:
            logger.warning("rollback_failed", reason="no_earlier_snapshots")
            return None

        self.current_index = target_index
        snapshot = self.snapshots[target_index]

        logger.info(
            "config_rolled_back",
            steps=steps,
            description=snapshot.description,
            timestamp=snapshot.timestamp.isoformat(),
        )

        return snapshot.config

    def forward(self, steps: int = 1) -> Optional[Config]:
        """
        Redo forward through history.

        Args:
            steps: Number of snapshots to go forward

        Returns:
            Next config, or None if can't go forward
        """
        target_index = self.current_index + steps
        if target_index >= len(self.snapshots):
            logger.warning("forward_failed", reason="no_later_snapshots")
            return None

        self.current_index = target_index
        snapshot = self.snapshots[target_index]

        logger.info(
            "config_moved_forward",
            steps=steps,
            description=snapshot.description,
            timestamp=snapshot.timestamp.isoformat(),
        )

        return snapshot.config

    def get_current(self) -> Optional[ConfigSnapshot]:
        """Get current snapshot."""
        if 0 <= self.current_index < len(self.snapshots):
            return self.snapshots[self.current_index]
        return None

    def list_history(self, limit: int = 10) -> List[ConfigSnapshot]:
        """
        Get recent history for UI display.

        Args:
            limit: Maximum number of snapshots to return

        Returns:
            List of recent snapshots (newest first)
        """
        start = max(0, len(self.snapshots) - limit)
        return list(reversed(list(self.snapshots)[start:]))


# ============================================================================
# Client Statistics
# ============================================================================


@dataclass
class ClientStats:
    """Real-time client statistics for UI display."""

    active_requests: int = 0
    max_concurrent: int = 0
    available_tokens: float = 0.0
    rate_limit_capacity: float = 0.0

    @property
    def utilization_pct(self) -> float:
        """Get concurrency utilization percentage."""
        if self.max_concurrent == 0:
            return 0.0
        return (self.active_requests / self.max_concurrent) * 100

    @property
    def rate_limit_pct(self) -> float:
        """Get rate limit capacity percentage."""
        if self.rate_limit_capacity == 0:
            return 0.0
        return (self.available_tokens / self.rate_limit_capacity) * 100


def get_client_stats(client: Any) -> ClientStats:
    """
    Get current statistics for a RateLimitedAPIClient.

    Args:
        client: RateLimitedAPIClient instance

    Returns:
        ClientStats with current metrics
    """
    stats = ClientStats()

    # Get concurrency stats
    if hasattr(client, "concurrency_limiter") and client.concurrency_limiter:
        stats.active_requests = client.concurrency_limiter.get_active_count()
        stats.max_concurrent = client.concurrency_limiter.max_concurrent

    # Get rate limiter stats
    if hasattr(client, "rate_limiter") and client.rate_limiter:
        stats.available_tokens = client.rate_limiter.get_available_tokens()
        stats.rate_limit_capacity = client.rate_limiter.burst_size

    return stats


# ============================================================================
# Configuration Manager
# ============================================================================


class ConfigManager:
    """
    Manages configuration with hot-reload, history, and event callbacks.

    Features:
    - Update config fields with validation
    - Automatic YAML persistence (debounced)
    - Configuration history with undo/redo
    - Event callbacks for UI notifications
    - Safe client hot-reload for API clients
    """

    def __init__(
        self,
        config: Config,
        config_path: Optional[Path] = None,
        save_debounce_seconds: float = 2.0,
    ):
        """
        Initialize configuration manager.

        Args:
            config: Initial configuration
            config_path: Path to YAML file for auto-save (optional)
            save_debounce_seconds: Debounce delay for auto-save (default: 2s)
        """
        self._config = config
        self._config_path = config_path
        self._save_debounce_seconds = save_debounce_seconds
        self._save_task: Optional[asyncio.Task] = None

        # Configuration history
        self.history = ConfigHistory()

        # Event callbacks
        self._callbacks: List[Union[ConfigCallback, WeakMethod]] = []

        # Registered API clients for hot-reload
        self._clients: Dict[str, Any] = {}  # api_name -> RateLimitedAPIClient

        logger.info(
            "config_manager_initialized",
            config_path=str(config_path) if config_path else None,
            save_debounce=save_debounce_seconds,
        )

    # ========================================================================
    # Client Registration
    # ========================================================================

    def register_client(self, name: str, client: Any) -> None:
        """
        Register an API client for hot-reload management.

        Args:
            name: Unique client identifier (e.g., "discogs", "imvdb")
            client: RateLimitedAPIClient instance
        """
        self._clients[name] = client
        logger.debug("client_registered", name=name)

    def unregister_client(self, name: str) -> None:
        """
        Unregister an API client.

        Args:
            name: Client identifier
        """
        if name in self._clients:
            del self._clients[name]
            logger.debug("client_unregistered", name=name)

    def get_client(self, name: str) -> Optional[Any]:
        """
        Get registered client by name.

        Args:
            name: Client identifier

        Returns:
            Client instance or None if not found
        """
        return self._clients.get(name)

    def get_client_stats(self, name: str) -> Optional[ClientStats]:
        """
        Get statistics for a registered client.

        Args:
            name: Client identifier

        Returns:
            ClientStats or None if client not found
        """
        client = self._clients.get(name)
        if client:
            return get_client_stats(client)
        return None

    def list_clients(self) -> List[str]:
        """Get list of registered client names."""
        return list(self._clients.keys())

    # ========================================================================
    # Event Callbacks
    # ========================================================================

    def on_change(self, callback: ConfigCallback) -> None:
        """
        Register a callback for configuration changes.

        Supports both sync and async callbacks. Bound methods are stored
        as weak references to prevent memory leaks.

        Args:
            callback: Function to call when config changes

        Example:
            >>> async def on_timeout_change(event: ConfigChangeEvent):
            ...     print(f"Timeout changed: {event.old_value} → {event.new_value}")
            >>> manager.on_change(on_timeout_change)
        """
        # Use weak reference for bound methods
        if hasattr(callback, "__self__"):
            callback_ref = WeakMethod(callback)
            self._callbacks.append(callback_ref)
            logger.debug("callback_registered", callback="<bound_method>", weak_ref=True)
        else:
            self._callbacks.append(callback)
            logger.debug("callback_registered", callback=callback.__name__, weak_ref=False)

    def remove_callback(self, callback: ConfigCallback) -> None:
        """
        Unregister a callback.

        Args:
            callback: Callback function to remove
        """
        # Handle both direct callbacks and weak references
        to_remove = []
        for i, cb_ref in enumerate(self._callbacks):
            if isinstance(cb_ref, WeakMethod):
                cb = cb_ref()
                if cb is None or cb == callback:
                    to_remove.append(i)
            elif cb_ref == callback:
                to_remove.append(i)

        for i in reversed(to_remove):
            del self._callbacks[i]

        if to_remove:
            logger.debug("callback_removed", count=len(to_remove))

    async def _notify(self, event: ConfigChangeEvent) -> None:
        """
        Notify all registered callbacks of a config change.

        Args:
            event: Configuration change event
        """
        dead_refs = []

        for i, cb_ref in enumerate(self._callbacks):
            # Dereference weak methods
            if isinstance(cb_ref, WeakMethod):
                cb = cb_ref()
                if cb is None:
                    dead_refs.append(i)
                    continue
            else:
                cb = cb_ref

            # Call callback (handle both sync and async)
            try:
                result = cb(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(
                    "config_callback_failed",
                    path=event.path,
                    error=str(e),
                    exc_info=True,
                )

        # Remove dead weak references
        for i in reversed(dead_refs):
            del self._callbacks[i]

        if dead_refs:
            logger.debug("dead_callbacks_cleaned", count=len(dead_refs))

    # ========================================================================
    # Nested Path Helpers
    # ========================================================================

    def _get_nested(self, obj: Any, path: str) -> Any:
        """
        Get nested attribute by dot path.

        Args:
            obj: Object to traverse
            path: Dot-notation path (e.g., "http.timeout")

        Returns:
            Value at path

        Raises:
            AttributeError: If path doesn't exist
        """
        parts = path.split(".")
        for part in parts:
            # Handle dict access for apis.* patterns
            if isinstance(obj, dict):
                obj = obj[part]
            else:
                obj = getattr(obj, part)
        return obj

    def _set_nested(self, obj: Any, path: str, value: Any) -> None:
        """
        Set nested attribute by dot path.

        Args:
            obj: Object to modify
            path: Dot-notation path (e.g., "http.timeout")
            value: New value to set

        Raises:
            AttributeError: If path doesn't exist
        """
        parts = path.split(".")
        for part in parts[:-1]:
            # Handle dict access for apis.* patterns
            if isinstance(obj, dict):
                obj = obj[part]
            else:
                obj = getattr(obj, part)

        # Set final attribute
        final_part = parts[-1]
        if isinstance(obj, dict):
            obj[final_part] = value
        else:
            setattr(obj, final_part, value)

    # ========================================================================
    # Update Methods
    # ========================================================================

    async def update(self, path: str, value: Any, description: Optional[str] = None) -> None:
        """
        Update a configuration field.

        Args:
            path: Dot-notation path (e.g., "http.timeout")
            value: New value
            description: Optional human-readable description of change

        Raises:
            ConfigValidationError: If validation fails
            ClientReloadError: If client reload fails (for REQUIRES_RELOAD fields)

        Example:
            >>> await manager.update("http.timeout", 60)
            >>> await manager.update("apis.discogs.rate_limit.requests_per_minute", 30)
        """
        # Get old value
        try:
            old_value = self._get_nested(self._config, path)
        except (AttributeError, KeyError) as e:
            raise ConfigValidationError(f"Invalid config path: {path}") from e

        # Check if value actually changed
        if old_value == value:
            logger.debug("config_unchanged", path=path, value=value)
            return

        # Apply change
        self._set_nested(self._config, path, value)

        # Validate entire config
        try:
            self._config.model_validate(self._config.model_dump())
        except ValidationError as e:
            # Rollback on validation failure
            self._set_nested(self._config, path, old_value)

            # Extract user-friendly error message
            errors = e.errors()
            if errors:
                first_error = errors[0]
                field = ".".join(str(x) for x in first_error["loc"])
                msg = first_error["msg"]
                logger.warning(
                    "config_validation_failed",
                    field=field,
                    message=msg,
                    value=value,
                )
                raise ConfigValidationError(f"Invalid value for {field}: {msg}") from e
            else:
                raise ConfigValidationError(f"Validation failed: {e}") from e

        # Get safety level
        safety_level = get_safety_level(path)

        # Handle client reload for API config changes
        # Check if this is an API client config change (auth, rate_limit, etc.)
        if path.startswith("apis."):
            parts = path.split(".")
            if len(parts) >= 2:
                api_name = parts[1]
                if api_name in self._clients:
                    try:
                        await self._reload_client(api_name)
                    except ClientReloadError:
                        # Rollback config on client reload failure
                        self._set_nested(self._config, path, old_value)
                        raise

        # Save snapshot to history
        desc = description or f"Changed {path}: {old_value} → {value}"
        self.history.save_snapshot(self._config, desc)

        # Schedule auto-save
        await self._schedule_save()

        # Notify callbacks
        event = ConfigChangeEvent(
            path=path,
            old_value=old_value,
            new_value=value,
            safety_level=safety_level,
        )
        await self._notify(event)

        logger.info(
            "config_updated",
            path=path,
            old_value=old_value,
            new_value=value,
            safety_level=safety_level.value,
        )

    async def update_many(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple configuration fields atomically.

        Either all updates succeed or all are rolled back.

        Args:
            updates: Dict mapping paths to new values

        Raises:
            ConfigValidationError: If validation fails (all changes rolled back)

        Example:
            >>> await manager.update_many({
            ...     "http.timeout": 60,
            ...     "http.max_redirects": 10,
            ... })
        """
        # Save snapshot before any changes
        snapshot = self._config.model_dump()
        old_values: Dict[str, Any] = {}

        try:
            # Apply all changes
            for path, value in updates.items():
                old_values[path] = self._get_nested(self._config, path)
                self._set_nested(self._config, path, value)

            # Validate entire config
            self._config.model_validate(self._config.model_dump())

            # Save snapshot on success
            desc = f"Batch update: {', '.join(updates.keys())}"
            self.history.save_snapshot(self._config, desc)

            # Schedule auto-save
            await self._schedule_save()

            # Notify callbacks for each change
            for path, value in updates.items():
                event = ConfigChangeEvent(
                    path=path,
                    old_value=old_values[path],
                    new_value=value,
                    safety_level=get_safety_level(path),
                )
                await self._notify(event)

            logger.info("batch_update_succeeded", paths=list(updates.keys()))

        except ValidationError as e:
            # Rollback all changes
            logger.warning("batch_update_failed_rolling_back", error=str(e))
            self._config = Config.model_validate(snapshot)
            raise ConfigValidationError(f"Batch update validation failed: {e}") from e

    def get_config(self) -> Config:
        """Get current configuration."""
        return self._config

    # ========================================================================
    # Auto-Save
    # ========================================================================

    async def _schedule_save(self) -> None:
        """Schedule save with debounce."""
        # Cancel pending save
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass

        # Schedule new save
        async def save_after_delay() -> None:
            await asyncio.sleep(self._save_debounce_seconds)
            await self.save()

        self._save_task = asyncio.create_task(save_after_delay())
        logger.debug("save_scheduled", delay_seconds=self._save_debounce_seconds)

    async def save(self, force: bool = False) -> None:
        """
        Save configuration to YAML immediately.

        Args:
            force: If False, only saves if config_path was provided

        Raises:
            ConfigSaveError: If save fails
        """
        if not self._config_path:
            if force:
                raise ConfigSaveError("No config path configured")
            logger.debug("save_skipped", reason="no_config_path")
            return

        try:
            self._config.to_yaml(self._config_path)
            logger.info("config_saved", path=str(self._config_path))
        except Exception as e:
            logger.error("config_save_failed", path=str(self._config_path), error=str(e))
            raise ConfigSaveError(f"Failed to save config: {e}") from e

    # ========================================================================
    # Client Hot-Reload
    # ========================================================================

    async def _reload_client(self, api_name: str) -> None:
        """
        Reload API client with new configuration.

        Args:
            api_name: Name of the API client to reload

        Raises:
            ClientReloadError: If reload fails
        """
        old_client = self._clients.get(api_name)
        if not old_client:
            logger.warning("client_reload_skipped", api=api_name, reason="not_registered")
            return

        try:
            # Get new config
            if not self._config.apis or api_name not in self._config.apis:
                raise ClientReloadError(f"No config found for API: {api_name}")

            new_config = self._config.apis[api_name]

            # Wait for old client to drain
            logger.info("draining_client", api=api_name)
            if hasattr(old_client, "concurrency_limiter") and old_client.concurrency_limiter:
                while old_client.concurrency_limiter.get_active_count() > 0:
                    await asyncio.sleep(0.1)

            # Close old client
            if hasattr(old_client, "__aexit__"):
                await old_client.__aexit__(None, None, None)

            # Create new client from config
            client_class = type(old_client)
            new_client = client_class.from_config(new_config)

            # Initialize new client if needed
            if hasattr(new_client, "__aenter__"):
                await new_client.__aenter__()

            # Swap clients
            self._clients[api_name] = new_client

            logger.info("client_reloaded", api=api_name)

        except Exception as e:
            logger.error("client_reload_failed", api=api_name, error=str(e), exc_info=True)

            # Keep old client on failure
            if old_client:
                self._clients[api_name] = old_client
                logger.warning("keeping_old_client", api=api_name)

            raise ClientReloadError(f"Failed to reload {api_name}: {e}") from e

    # ========================================================================
    # History Management
    # ========================================================================

    async def undo(self, steps: int = 1) -> bool:
        """
        Undo configuration changes.

        Args:
            steps: Number of steps to undo

        Returns:
            True if successful, False if no history to undo
        """
        prev_config = self.history.rollback(steps)
        if prev_config is None:
            return False

        self._config = prev_config
        await self._schedule_save()
        logger.info("config_undo", steps=steps)
        return True

    async def redo(self, steps: int = 1) -> bool:
        """
        Redo configuration changes.

        Args:
            steps: Number of steps to redo

        Returns:
            True if successful, False if no history to redo
        """
        next_config = self.history.forward(steps)
        if next_config is None:
            return False

        self._config = next_config
        await self._schedule_save()
        logger.info("config_redo", steps=steps)
        return True

    def get_history(self, limit: int = 10) -> List[ConfigSnapshot]:
        """
        Get recent configuration history.

        Args:
            limit: Maximum number of snapshots to return

        Returns:
            List of recent snapshots (newest first)
        """
        return self.history.list_history(limit)
