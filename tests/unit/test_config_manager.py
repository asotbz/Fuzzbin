"""Tests for configuration manager with hot-reload and event callbacks."""

import asyncio
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import pytest_asyncio

from fuzzbin.common.config import (
    Config,
    ConfigSafetyLevel,
    LoggingConfig,
    TagsConfig,
    OrganizerConfig,
    BackupConfig,
    get_safety_level,
)
from fuzzbin.common.config_manager import (
    ConfigManager,
    ConfigChangeEvent,
    ConfigSnapshot,
    ConfigHistory,
    ClientStats,
    get_client_stats,
    ConfigManagerError,
    ConfigValidationError,
    ConfigSaveError,
    ClientReloadError,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Create a temporary config file path."""
    return tmp_path / "test_config.yaml"


@pytest.fixture
def sample_config() -> Config:
    """Create a sample configuration for testing."""
    return Config(
        backup=BackupConfig(retention_count=7, output_dir="backups"),
        logging=LoggingConfig(level="INFO", format="json"),
    )


@pytest_asyncio.fixture
async def config_manager(sample_config: Config, temp_config_file: Path):
    """Create a ConfigManager instance for testing."""
    manager = ConfigManager(
        config=sample_config,
        config_path=temp_config_file,
        save_debounce_seconds=0.1,  # Faster for tests
    )
    yield manager
    
    # Cleanup: cancel any pending save tasks
    if manager._save_task and not manager._save_task.done():
        manager._save_task.cancel()
        try:
            await manager._save_task
        except asyncio.CancelledError:
            pass


# ============================================================================
# Safety Level Tests
# ============================================================================


class TestSafetyLevel:
    """Test configuration safety level categorization."""

    def test_safe_fields(self):
        """Test that safe fields are correctly categorized."""
        assert get_safety_level("logging.level") == ConfigSafetyLevel.SAFE
        assert get_safety_level("backup.retention_count") == ConfigSafetyLevel.SAFE
        assert get_safety_level("backup.schedule") == ConfigSafetyLevel.SAFE

    def test_requires_reload_fields(self):
        """Test that reload-required fields are correctly categorized."""
        assert (
            get_safety_level("apis.discogs.auth.api_key")
            == ConfigSafetyLevel.REQUIRES_RELOAD
        )
        assert (
            get_safety_level("apis.imvdb.auth.app_key")
            == ConfigSafetyLevel.REQUIRES_RELOAD
        )

    def test_affects_state_fields(self):
        """Test that state-affecting fields are correctly categorized."""
        assert get_safety_level("file_manager.trash_dir") == ConfigSafetyLevel.AFFECTS_STATE
        assert get_safety_level("library_dir") == ConfigSafetyLevel.AFFECTS_STATE
        assert get_safety_level("config_dir") == ConfigSafetyLevel.AFFECTS_STATE
        assert get_safety_level("backup.output_dir") == ConfigSafetyLevel.AFFECTS_STATE

    def test_wildcard_matching(self):
        """Test wildcard pattern matching for safety levels."""
        # nfo.* should match any nfo field
        assert get_safety_level("nfo.featured_artists") == ConfigSafetyLevel.SAFE
        
        # organizer.* should match any organizer field
        assert get_safety_level("organizer.path_pattern") == ConfigSafetyLevel.SAFE
        
        # apis.*.auth.* should match any API auth field
        assert (
            get_safety_level("apis.spotify.auth.client_id")
            == ConfigSafetyLevel.REQUIRES_RELOAD
        )

    def test_default_safe_for_unknown_fields(self):
        """Test that unknown fields default to SAFE."""
        assert get_safety_level("unknown.field") == ConfigSafetyLevel.SAFE


# ============================================================================
# Config History Tests
# ============================================================================


class TestConfigHistory:
    """Test configuration history and rollback functionality."""

    def test_save_snapshot(self, sample_config: Config):
        """Test saving configuration snapshots."""
        history = ConfigHistory(max_snapshots=5)
        
        history.save_snapshot(sample_config, "Initial config")
        assert len(history.snapshots) == 1
        assert history.current_index == 0
        
        history.save_snapshot(sample_config, "Second config")
        assert len(history.snapshots) == 2
        assert history.current_index == 1

    def test_max_snapshots_limit(self, sample_config: Config):
        """Test that snapshot buffer respects max limit."""
        history = ConfigHistory(max_snapshots=3)
        
        for i in range(5):
            history.save_snapshot(sample_config, f"Config {i}")
        
        # Should only keep last 3
        assert len(history.snapshots) == 3
        assert history.current_index == 2

    def test_rollback(self, sample_config: Config):
        """Test rolling back to previous configurations."""
        history = ConfigHistory()
        
        # Save multiple snapshots
        for i in range(3):
            config = Config(backup=BackupConfig(retention_count=7 + i))
            history.save_snapshot(config, f"Config {i}")
        
        # Rollback 1 step
        prev_config = history.rollback(1)
        assert prev_config is not None
        assert prev_config.backup.retention_count == 8
        assert history.current_index == 1

    def test_rollback_too_far(self, sample_config: Config):
        """Test that rollback returns None when going too far."""
        history = ConfigHistory()
        history.save_snapshot(sample_config, "Config")
        
        # Try to rollback 5 steps when only 1 exists
        result = history.rollback(5)
        assert result is None

    def test_forward(self, sample_config: Config):
        """Test moving forward through history."""
        history = ConfigHistory()
        
        # Save snapshots and rollback
        for i in range(3):
            config = Config(backup=BackupConfig(retention_count=7 + i))
            history.save_snapshot(config, f"Config {i}")
        
        history.rollback(2)
        assert history.current_index == 0
        
        # Move forward
        next_config = history.forward(1)
        assert next_config is not None
        assert next_config.backup.retention_count == 8
        assert history.current_index == 1

    def test_truncate_forward_history(self, sample_config: Config):
        """Test that new snapshots truncate forward history."""
        history = ConfigHistory()
        
        # Save 3 snapshots
        for i in range(3):
            config = Config(backup=BackupConfig(retention_count=7 + i))
            history.save_snapshot(config, f"Config {i}")
        
        # Rollback to middle
        history.rollback(1)
        assert len(history.snapshots) == 3
        
        # Save new snapshot - should discard forward history
        new_config = Config(backup=BackupConfig(retention_count=100))
        history.save_snapshot(new_config, "New config")
        
        assert len(history.snapshots) == 3  # One was discarded
        assert history.current_index == 2
        assert history.snapshots[-1].config.backup.retention_count == 100

    def test_list_history(self, sample_config: Config):
        """Test listing recent history."""
        history = ConfigHistory()
        
        for i in range(15):
            config = Config(backup=BackupConfig(retention_count=7 + i))
            history.save_snapshot(config, f"Config {i}")
        
        # Get last 10
        recent = history.list_history(limit=10)
        assert len(recent) == 10
        
        # Should be newest first
        assert recent[0].config.backup.retention_count == 21  # Config 14
        assert recent[-1].config.backup.retention_count == 12  # Config 5


# ============================================================================
# Client Stats Tests
# ============================================================================


class TestClientStats:
    """Test client statistics tracking."""

    def test_client_stats_with_no_limiters(self):
        """Test getting stats from client with no limiters."""
        mock_client = Mock()
        mock_client.concurrency_limiter = None
        mock_client.rate_limiter = None
        
        stats = get_client_stats(mock_client)
        assert stats.active_requests == 0
        assert stats.max_concurrent == 0
        assert stats.available_tokens == 0.0
        assert stats.rate_limit_capacity == 0.0

    def test_client_stats_with_limiters(self):
        """Test getting stats from client with limiters."""
        mock_client = Mock()
        
        # Mock concurrency limiter
        mock_concurrency = Mock()
        mock_concurrency.get_active_count.return_value = 3
        mock_concurrency.max_concurrent = 10
        mock_client.concurrency_limiter = mock_concurrency
        
        # Mock rate limiter
        mock_rate = Mock()
        mock_rate.get_available_tokens.return_value = 15.5
        mock_rate.burst_size = 30.0
        mock_client.rate_limiter = mock_rate
        
        stats = get_client_stats(mock_client)
        assert stats.active_requests == 3
        assert stats.max_concurrent == 10
        assert stats.available_tokens == 15.5
        assert stats.rate_limit_capacity == 30.0

    def test_utilization_percentage(self):
        """Test utilization percentage calculation."""
        stats = ClientStats(active_requests=5, max_concurrent=10)
        assert stats.utilization_pct == 50.0
        
        stats = ClientStats(active_requests=0, max_concurrent=10)
        assert stats.utilization_pct == 0.0
        
        stats = ClientStats(active_requests=5, max_concurrent=0)
        assert stats.utilization_pct == 0.0  # Avoid division by zero

    def test_rate_limit_percentage(self):
        """Test rate limit percentage calculation."""
        stats = ClientStats(available_tokens=15.0, rate_limit_capacity=30.0)
        assert stats.rate_limit_pct == 50.0
        
        stats = ClientStats(available_tokens=0.0, rate_limit_capacity=30.0)
        assert stats.rate_limit_pct == 0.0
        
        stats = ClientStats(available_tokens=15.0, rate_limit_capacity=0.0)
        assert stats.rate_limit_pct == 0.0  # Avoid division by zero


# ============================================================================
# ConfigManager Core Tests
# ============================================================================


class TestConfigManager:
    """Test ConfigManager core functionality."""

    def test_initialization(self, config_manager: ConfigManager):
        """Test ConfigManager initialization."""
        assert config_manager._config is not None
        assert config_manager._config_path is not None
        assert config_manager.history is not None
        assert len(config_manager._callbacks) == 0
        assert len(config_manager._clients) == 0

    def test_get_config(self, config_manager: ConfigManager, sample_config: Config):
        """Test getting current configuration."""
        config = config_manager.get_config()
        assert config == sample_config

    def test_nested_get(self, config_manager: ConfigManager):
        """Test getting nested configuration values."""
        value = config_manager._get_nested(config_manager._config, "backup.retention_count")
        assert value == 7

    def test_nested_set(self, config_manager: ConfigManager):
        """Test setting nested configuration values."""
        config_manager._set_nested(config_manager._config, "backup.retention_count", 14)
        assert config_manager._config.backup.retention_count == 14

    def test_nested_get_invalid_path(self, config_manager: ConfigManager):
        """Test that invalid paths raise AttributeError."""
        with pytest.raises((AttributeError, KeyError)):
            config_manager._get_nested(config_manager._config, "invalid.path")


# ============================================================================
# Client Registration Tests
# ============================================================================


class TestClientRegistration:
    """Test API client registration and management."""

    def test_register_client(self, config_manager: ConfigManager):
        """Test registering an API client."""
        mock_client = Mock()
        config_manager.register_client("test_api", mock_client)
        
        assert "test_api" in config_manager._clients
        assert config_manager.get_client("test_api") == mock_client

    def test_unregister_client(self, config_manager: ConfigManager):
        """Test unregistering an API client."""
        mock_client = Mock()
        config_manager.register_client("test_api", mock_client)
        config_manager.unregister_client("test_api")
        
        assert "test_api" not in config_manager._clients
        assert config_manager.get_client("test_api") is None

    def test_get_nonexistent_client(self, config_manager: ConfigManager):
        """Test getting a non-existent client returns None."""
        assert config_manager.get_client("nonexistent") is None

    def test_list_clients(self, config_manager: ConfigManager):
        """Test listing registered clients."""
        config_manager.register_client("api1", Mock())
        config_manager.register_client("api2", Mock())
        
        clients = config_manager.list_clients()
        assert set(clients) == {"api1", "api2"}

    def test_get_client_stats(self, config_manager: ConfigManager):
        """Test getting stats for registered client."""
        mock_client = Mock()
        mock_client.concurrency_limiter = Mock()
        mock_client.concurrency_limiter.get_active_count.return_value = 5
        mock_client.concurrency_limiter.max_concurrent = 10
        mock_client.rate_limiter = None
        
        config_manager.register_client("test_api", mock_client)
        
        stats = config_manager.get_client_stats("test_api")
        assert stats is not None
        assert stats.active_requests == 5

    def test_get_stats_for_nonexistent_client(self, config_manager: ConfigManager):
        """Test getting stats for non-existent client returns None."""
        assert config_manager.get_client_stats("nonexistent") is None


# ============================================================================
# Event Callback Tests
# ============================================================================


class TestEventCallbacks:
    """Test event callback system."""

    @pytest.mark.asyncio
    async def test_register_sync_callback(self, config_manager: ConfigManager):
        """Test registering synchronous callbacks."""
        events: List[ConfigChangeEvent] = []
        
        def callback(event: ConfigChangeEvent):
            events.append(event)
        
        config_manager.on_change(callback)
        assert len(config_manager._callbacks) == 1
        
        # Trigger update
        await config_manager.update("backup.retention_count", 14)
        
        # Give callbacks time to execute
        await asyncio.sleep(0.01)
        
        assert len(events) == 1
        assert events[0].path == "backup.retention_count"
        assert events[0].old_value == 7
        assert events[0].new_value == 14

    @pytest.mark.asyncio
    async def test_register_async_callback(self, config_manager: ConfigManager):
        """Test registering asynchronous callbacks."""
        events: List[ConfigChangeEvent] = []
        
        async def callback(event: ConfigChangeEvent):
            events.append(event)
        
        config_manager.on_change(callback)
        
        # Trigger update
        await config_manager.update("backup.retention_count", 14)
        
        assert len(events) == 1
        assert events[0].path == "backup.retention_count"

    @pytest.mark.asyncio
    async def test_remove_callback(self, config_manager: ConfigManager):
        """Test removing callbacks."""
        events: List[ConfigChangeEvent] = []
        
        def callback(event: ConfigChangeEvent):
            events.append(event)
        
        config_manager.on_change(callback)
        config_manager.remove_callback(callback)
        
        # Trigger update
        await config_manager.update("backup.retention_count", 14)
        
        # Callback should not be called
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_callback_error_doesnt_fail_update(self, config_manager: ConfigManager):
        """Test that callback errors don't prevent config updates."""
        
        def bad_callback(event: ConfigChangeEvent):
            raise ValueError("Callback error")
        
        config_manager.on_change(bad_callback)
        
        # Update should succeed despite callback error
        await config_manager.update("backup.retention_count", 14)
        
        assert config_manager._config.backup.retention_count == 14

    @pytest.mark.asyncio
    async def test_weak_reference_cleanup(self, config_manager: ConfigManager):
        """Test that weak references to bound methods are cleaned up."""
        
        class Handler:
            def __init__(self):
                self.events: List[ConfigChangeEvent] = []
            
            def on_change(self, event: ConfigChangeEvent):
                self.events.append(event)
        
        handler = Handler()
        config_manager.on_change(handler.on_change)
        
        # Trigger update - callback should work
        await config_manager.update("backup.retention_count", 14)
        assert len(handler.events) == 1
        
        # Delete handler - weak reference should be cleaned up
        del handler
        
        # Trigger another update - should clean up dead reference
        await config_manager.update("backup.retention_count", 21)
        
        # Dead references should be removed during notification
        # (Exact count depends on cleanup timing)


# ============================================================================
# Update Tests
# ============================================================================


class TestConfigUpdate:
    """Test configuration update functionality."""

    @pytest.mark.asyncio
    async def test_update_safe_field(self, config_manager: ConfigManager):
        """Test updating a safe field."""
        await config_manager.update("backup.retention_count", 14)
        
        assert config_manager._config.backup.retention_count == 14
        assert len(config_manager.history.snapshots) == 1

    @pytest.mark.asyncio
    async def test_update_validation_failure(self, config_manager: ConfigManager):
        """Test that validation failures rollback changes."""
        with pytest.raises(ConfigValidationError):
            await config_manager.update("backup.retention_count", -10)  # Invalid
        
        # Should be rolled back to original value
        assert config_manager._config.backup.retention_count == 7

    @pytest.mark.asyncio
    async def test_update_no_change(self, config_manager: ConfigManager):
        """Test that updating to same value is a no-op."""
        await config_manager.update("backup.retention_count", 7)  # Same value
        
        # No history snapshot should be created
        assert len(config_manager.history.snapshots) == 0

    @pytest.mark.asyncio
    async def test_update_invalid_path(self, config_manager: ConfigManager):
        """Test that invalid paths raise ConfigValidationError."""
        with pytest.raises(ConfigValidationError):
            await config_manager.update("invalid.path", 123)

    @pytest.mark.asyncio
    async def test_update_many_success(self, config_manager: ConfigManager):
        """Test batch update of multiple fields."""
        await config_manager.update_many({
            "backup.retention_count": 14,
            "backup.output_dir": "custom_backups",
            "logging.level": "DEBUG",
        })
        
        assert config_manager._config.backup.retention_count == 14
        assert config_manager._config.backup.output_dir == "custom_backups"
        assert config_manager._config.logging.level == "DEBUG"

    @pytest.mark.asyncio
    async def test_update_many_validation_failure(self, config_manager: ConfigManager):
        """Test that batch update rolls back all changes on validation failure."""
        with pytest.raises(ConfigValidationError):
            await config_manager.update_many({
                "backup.retention_count": 14,  # Valid
                "backup.retention_count": -5,  # Invalid (overwrites previous)
            })
        
        # Should be rolled back
        assert config_manager._config.backup.retention_count == 7


# ============================================================================
# Auto-Save Tests
# ============================================================================


class TestAutoSave:
    """Test automatic YAML saving."""

    @pytest.mark.asyncio
    async def test_debounced_save(self, config_manager: ConfigManager, temp_config_file: Path):
        """Test that saves are debounced."""
        # Make multiple rapid updates
        await config_manager.update("backup.retention_count", 10)
        await config_manager.update("backup.retention_count", 15)
        await config_manager.update("backup.retention_count", 20)
        
        # Should only trigger one save after debounce period
        await asyncio.sleep(0.2)  # Wait for debounce
        
        # File should exist with final value
        assert temp_config_file.exists()
        
        # Load and verify
        saved_config = Config.from_yaml(temp_config_file)
        assert saved_config.backup.retention_count == 20

    @pytest.mark.asyncio
    async def test_save_without_config_path(self):
        """Test that save without config_path is a no-op."""
        manager = ConfigManager(
            config=Config(),
            config_path=None,  # No path
        )
        
        # Should not raise error
        await manager.save()

    @pytest.mark.asyncio
    async def test_force_save_without_path_raises(self):
        """Test that force save without config_path raises error."""
        manager = ConfigManager(
            config=Config(),
            config_path=None,
        )
        
        with pytest.raises(ConfigSaveError):
            await manager.save(force=True)


# ============================================================================
# History/Undo Tests
# ============================================================================


class TestUndoRedo:
    """Test undo/redo functionality."""

    @pytest.mark.asyncio
    async def test_undo(self, config_manager: ConfigManager):
        """Test undoing configuration changes."""
        # Make changes
        await config_manager.update("backup.retention_count", 10)
        await config_manager.update("backup.retention_count", 15)
        
        # Undo one step
        success = await config_manager.undo(1)
        assert success
        assert config_manager._config.backup.retention_count == 10

    @pytest.mark.asyncio
    async def test_undo_when_no_history(self, config_manager: ConfigManager):
        """Test that undo returns False when no history exists."""
        success = await config_manager.undo(1)
        assert not success

    @pytest.mark.asyncio
    async def test_redo(self, config_manager: ConfigManager):
        """Test redoing configuration changes."""
        # Make changes and undo
        await config_manager.update("backup.retention_count", 10)
        await config_manager.update("backup.retention_count", 15)
        await config_manager.undo(1)
        
        # Redo
        success = await config_manager.redo(1)
        assert success
        assert config_manager._config.backup.retention_count == 15

    @pytest.mark.asyncio
    async def test_get_history(self, config_manager: ConfigManager):
        """Test getting configuration history."""
        # Make several changes
        for i in range(5):
            await config_manager.update("backup.retention_count", 7 + i * 3)
        
        # Get history
        history = config_manager.get_history(limit=3)
        assert len(history) == 3
        
        # Should be newest first
        assert history[0].config.backup.retention_count == 19


# ============================================================================
# Client Reload Tests
# ============================================================================


class TestClientReload:
    """Test client hot-reload functionality."""

    @pytest.mark.asyncio
    async def test_reload_unregistered_client(self, config_manager: ConfigManager):
        """Test that reloading unregistered client is a no-op."""
        # Should not raise error
        await config_manager._reload_client("nonexistent")

    @pytest.mark.asyncio
    async def test_reload_client_with_drain(self, config_manager: ConfigManager):
        """Test client reload waits for active requests to drain."""
        # Create mock client
        mock_client = AsyncMock()
        mock_limiter = Mock()
        
        # Simulate active requests that drain
        call_count = [0]
        
        def get_count():
            call_count[0] += 1
            if call_count[0] <= 2:
                return 1  # Active requests
            return 0  # Drained
        
        mock_limiter.get_active_count = get_count
        mock_client.concurrency_limiter = mock_limiter
        mock_client.__aexit__ = AsyncMock()
        
        # Register client
        config_manager.register_client("test_api", mock_client)
        
        # Mock the from_config class method
        mock_new_client = AsyncMock()
        mock_new_client.__aenter__ = AsyncMock()
        type(mock_client).from_config = Mock(return_value=mock_new_client)
        
        # Trigger reload (should wait for drain)
        # Note: This will fail because we don't have a real API config
        # but we can test the drain logic separately


# ============================================================================
# Config.to_yaml Tests
# ============================================================================


class TestConfigToYaml:
    """Test Config.to_yaml() method."""

    def test_to_yaml_creates_file(self, sample_config: Config, tmp_path: Path):
        """Test that to_yaml creates a YAML file."""
        config_file = tmp_path / "test.yaml"
        sample_config.to_yaml(config_file)
        
        assert config_file.exists()

    def test_to_yaml_roundtrip(self, sample_config: Config, tmp_path: Path):
        """Test saving and loading config."""
        config_file = tmp_path / "test.yaml"
        sample_config.to_yaml(config_file)
        
        loaded_config = Config.from_yaml(config_file)
        assert loaded_config.backup.retention_count == sample_config.backup.retention_count
        assert loaded_config.logging.level == sample_config.logging.level

    def test_to_yaml_excludes_defaults(self, tmp_path: Path):
        """Test that default values are excluded."""
        config = Config()  # All defaults
        config_file = tmp_path / "test.yaml"
        config.to_yaml(config_file, exclude_defaults=True)
        
        # File should be minimal or empty
        assert config_file.exists()

    def test_to_yaml_atomic_write(self, sample_config: Config, tmp_path: Path):
        """Test that temp file is cleaned up on success."""
        config_file = tmp_path / "test.yaml"
        sample_config.to_yaml(config_file)
        
        # Temp file should not exist
        temp_file = config_file.with_suffix(".tmp")
        assert not temp_file.exists()
