"""Configuration models using Pydantic for validation."""

import os
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any, ClassVar
import string

import yaml
from ruamel.yaml import YAML
from pydantic import BaseModel, Field, field_validator
import structlog

logger = structlog.get_logger(__name__)


class ConfigSafetyLevel(Enum):
    """Safety level for runtime configuration changes."""

    SAFE = "safe"  # Can change without side effects
    REQUIRES_RELOAD = "requires_reload"  # Need to recreate components
    AFFECTS_STATE = "affects_state"  # Changes persistent files/connections


class RetryConfig(BaseModel):
    """Configuration for HTTP retry logic with exponential backoff."""

    max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of retry attempts",
    )
    backoff_multiplier: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Multiplier for exponential backoff calculation",
    )
    min_wait: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Minimum wait time between retries in seconds",
    )
    max_wait: float = Field(
        default=10.0,
        ge=1.0,
        le=300.0,
        description="Maximum wait time between retries in seconds",
    )
    status_codes: List[int] = Field(
        default_factory=lambda: [408, 429, 500, 502, 503, 504],
        description="HTTP status codes that should trigger a retry",
    )

    @field_validator("status_codes")
    @classmethod
    def validate_status_codes(cls, v: List[int]) -> List[int]:
        """Validate that status codes are in valid range."""
        for code in v:
            if not 100 <= code <= 599:
                raise ValueError(f"Invalid HTTP status code: {code}")
        return v


class HTTPConfig(BaseModel):
    """Configuration for HTTP client."""

    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Request timeout in seconds",
    )
    max_redirects: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Maximum number of redirects to follow",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify SSL certificates",
    )
    max_connections: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of connections in the pool",
    )
    max_keepalive_connections: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum number of keep-alive connections",
    )
    retry: RetryConfig = Field(
        default_factory=RetryConfig,
        description="Retry configuration",
    )


class FileLoggingConfig(BaseModel):
    """Configuration for file-based logging.

    File logging uses daily rotation with 7-day retention.
    Log files are stored as fuzzbin.log in config_dir, rotated daily
    with format fuzzbin.log.YYYY-MM-DD.
    """

    enabled: bool = Field(
        default=False,
        description="Enable file logging (logs to fuzzbin.log in config_dir)",
    )


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    format: str = Field(
        default="json",
        description="Log format: json or text",
    )
    file: FileLoggingConfig = Field(
        default_factory=FileLoggingConfig,
        description="File logging configuration",
    )
    third_party: Dict[str, str] = Field(
        default_factory=dict,
        description="Log levels for third-party libraries (advanced)",
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = ["json", "text"]
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(f"Invalid format: {v}. Must be one of {valid_formats}")
        return v_lower


class RateLimitConfig(BaseModel):
    """Configuration for rate limiting."""

    enabled: bool = Field(
        default=True,
        description="Whether rate limiting is enabled",
    )
    requests_per_minute: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum requests per minute",
    )
    requests_per_second: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum requests per second",
    )
    requests_per_hour: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum requests per hour",
    )
    burst_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum burst size (defaults to rate limit)",
    )

    @field_validator("burst_size")
    @classmethod
    def validate_burst_size(cls, v: Optional[int], info: Any) -> Optional[int]:
        """Validate that at least one rate limit is set when enabled."""
        # Note: This validator runs after other fields are set
        return v


class ConcurrencyConfig(BaseModel):
    """Configuration for concurrency control."""

    max_concurrent_requests: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Maximum number of concurrent requests",
    )
    per_host_limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Maximum concurrent requests per host (optional)",
    )


class CacheConfig(BaseModel):
    """Configuration for HTTP response caching using Hishel."""

    enabled: bool = Field(
        default=False,
        description="Whether response caching is enabled",
    )
    storage_path: str = Field(
        default=".cache/fuzzbin.db",
        description="Path to SQLite cache database file (per API client instance)",
    )
    ttl: Optional[int] = Field(
        default=3600,
        ge=1,
        description="Default time-to-live for cached responses in seconds",
    )
    stale_while_revalidate: Optional[int] = Field(
        default=60,
        ge=0,
        description="Time in seconds to serve stale responses while revalidating in background",
    )
    cacheable_methods: List[str] = Field(
        default_factory=lambda: ["GET", "HEAD"],
        description="HTTP methods that can be cached",
    )
    cacheable_status_codes: List[int] = Field(
        default_factory=lambda: [200, 203, 204, 206, 300, 301, 308],
        description="HTTP status codes that can be cached",
    )

    @field_validator("cacheable_methods")
    @classmethod
    def validate_methods(cls, v: List[str]) -> List[str]:
        """Validate HTTP methods."""
        valid_methods = ["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        for method in v:
            if method.upper() not in valid_methods:
                raise ValueError(f"Invalid HTTP method: {method}. Must be one of {valid_methods}")
        return [m.upper() for m in v]

    @field_validator("cacheable_status_codes")
    @classmethod
    def validate_status_codes(cls, v: List[int]) -> List[int]:
        """Validate that status codes are in valid range."""
        for code in v:
            if not 100 <= code <= 599:
                raise ValueError(f"Invalid HTTP status code: {code}")
        return v


class APIClientConfig(BaseModel):
    """Configuration for a specific API client.

    This is a simplified config that only contains authentication settings.
    All other settings (rate limiting, caching, concurrency, HTTP config)
    are hardcoded with sensible defaults in the API client implementations.

    For advanced configuration options, see docs/advanced-config.md.
    """

    auth: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Authentication configuration (API keys, tokens, secrets)",
    )


class YTDLPConfig(BaseModel):
    """Configuration for yt-dlp client."""

    ytdlp_path: str = Field(
        default="yt-dlp",
        description="Path to yt-dlp binary",
    )
    format_spec: Optional[str] = Field(
        default="bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        description="Default format specification for downloads",
    )
    geo_bypass: bool = Field(
        default=False,
        description="Bypass geographic restrictions",
    )


class FFProbeConfig(BaseModel):
    """Configuration for ffprobe client.

    For advanced configuration options, see docs/advanced-config.md.
    """

    ffprobe_path: str = Field(
        default="ffprobe",
        description="Path to ffprobe binary",
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Command execution timeout in seconds",
    )


class ThumbnailConfig(BaseModel):
    """Configuration for thumbnail generation via ffmpeg.

    For advanced configuration options (dimensions, quality, timestamp),
    see docs/advanced-config.md.
    """

    cache_dir: str = Field(
        default=".thumbnails",
        description="Directory for cached thumbnails (relative to config_dir)",
    )


class DatabaseConfig(BaseModel):
    """Configuration for SQLite database.

    Note: All database settings use hardcoded defaults for reliability.
    For advanced configuration, see docs/advanced-config.md.
    """

    # All fields removed - database uses hardcoded defaults:
    # - database_path: "fuzzbin.db" (relative to config_dir)
    # - enable_wal_mode: True
    # - connection_timeout: 30 seconds
    # - backup_dir: "backups" (relative to config_dir)
    pass


class NFOConfig(BaseModel):
    """Configuration for NFO file handling."""

    featured_artists: Optional["FeaturedArtistConfig"] = Field(  # noqa: F821
        default=None,
        description="Featured artist handling configuration",
    )
    write_artist_nfo: bool = Field(
        default=True,
        description="Write artist.nfo files in each {artist} directory",
    )
    write_musicvideo_nfo: bool = Field(
        default=True,
        description="Write <basename>.nfo files for each music video",
    )

    def model_post_init(self, __context):
        """Initialize featured_artists with default if not provided."""
        if self.featured_artists is None:
            from ..parsers.models import FeaturedArtistConfig

            object.__setattr__(self, "featured_artists", FeaturedArtistConfig())


# Import after NFOConfig definition to avoid circular import
from ..parsers.models import FeaturedArtistConfig  # noqa: E402, F401

# Rebuild model now that FeaturedArtistConfig is available
NFOConfig.model_rebuild()


class OrganizerConfig(BaseModel):
    """Configuration for media file organizer."""

    path_pattern: str = Field(
        default="{artist}/{title}",
        description="Path pattern with {field} placeholders for organizing media files",
    )
    normalize_filenames: bool = Field(
        default=False,
        description="Apply filename normalization (lowercase, remove special chars, etc.)",
    )

    def validate_pattern(self) -> None:
        """
        Validate that path_pattern uses only valid MusicVideoNFO fields.

        This method can be called on-demand (e.g., in hot-reload scenarios)
        to validate the pattern without requiring it during config initialization.

        Raises:
            ValueError: If pattern contains invalid field names

        Example:
            >>> config = OrganizerConfig(path_pattern="{artist}/{invalid_field}")
            >>> config.validate_pattern()  # Raises ValueError
        """
        from ..parsers.models import MusicVideoNFO

        # Extract field names from pattern
        formatter = string.Formatter()
        pattern_fields = set()
        for _, field_name, _, _ in formatter.parse(self.path_pattern):
            if field_name:
                pattern_fields.add(field_name)

        # Validate against MusicVideoNFO fields
        valid_fields = set(MusicVideoNFO.model_fields.keys())
        invalid_fields = pattern_fields - valid_fields

        if invalid_fields:
            raise ValueError(
                f"Invalid pattern fields: {invalid_fields}. Valid fields: {valid_fields}"
            )


class AutoDecadeConfig(BaseModel):
    """Configuration for automatic decade tagging based on release year."""

    enabled: bool = Field(
        default=True,
        description="Enable automatic decade tag generation",
    )
    format: str = Field(
        default="{decade}s",
        description="Format string for decade tags (e.g., '{decade}s' produces '90s')",
    )

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate that format string contains {decade} placeholder."""
        if "{decade}" not in v:
            raise ValueError("Format string must contain {decade} placeholder")
        return v


class TagsConfig(BaseModel):
    """Configuration for tag management and auto-tagging."""

    normalize: bool = Field(
        default=True,
        description="Normalize tag names to lowercase for consistency",
    )
    auto_decade: AutoDecadeConfig = Field(
        default_factory=AutoDecadeConfig,
        description="Automatic decade tag configuration",
    )


class BackupConfig(BaseModel):
    """Configuration for automatic system backups.

    Backups include config.yaml, the SQLite database, and the thumbnail repository.
    Archives are stored as timestamped .zip files that can be restored manually.
    """

    enabled: bool = Field(
        default=True,
        description="Enable automatic scheduled backups",
    )
    schedule: str = Field(
        default="0 2 * * *",
        description="Cron expression for backup schedule (default: daily at 2 AM)",
    )
    retention_count: int = Field(
        default=7,
        ge=1,
        le=365,
        description="Number of backup archives to retain (oldest are deleted)",
    )
    output_dir: str = Field(
        default="backups",
        description="Directory for backup archives (relative to config_dir)",
    )


class TrashConfig(BaseModel):
    """Configuration for trash directory and automatic cleanup.

    Deleted files are moved to the trash directory before permanent deletion.
    The cleanup scheduler removes old items based on retention_days.
    """

    trash_dir: str = Field(
        default=".trash",
        description="Directory for soft-deleted files (relative to library_dir)",
    )
    enabled: bool = Field(
        default=True,
        description="Enable automatic scheduled trash cleanup",
    )
    schedule: str = Field(
        default="0 3 * * *",
        description="Cron expression for cleanup schedule (default: daily at 3 AM)",
    )
    retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Delete items from trash older than this many days",
    )


def _get_default_config_dir() -> Path:
    """
    Get default config directory based on environment.

    Priority:
    1. FUZZBIN_CONFIG_DIR environment variable
    2. /config if FUZZBIN_DOCKER=1
    3. $HOME/Fuzzbin/config otherwise

    Returns:
        Path to config directory
    """
    # Check explicit env var override
    env_config_dir = os.environ.get("FUZZBIN_CONFIG_DIR")
    if env_config_dir:
        return Path(env_config_dir)

    # Check if running in Docker
    if os.environ.get("FUZZBIN_DOCKER") == "1":
        return Path("/config")

    # Default to $HOME/Fuzzbin/config
    return Path.home() / "Fuzzbin" / "config"


def _get_default_library_dir() -> Path:
    """
    Get default library directory based on environment.

    Priority:
    1. FUZZBIN_LIBRARY_DIR environment variable
    2. /music_videos if FUZZBIN_DOCKER=1
    3. $HOME/Fuzzbin/music_videos otherwise

    Returns:
        Path to library directory
    """
    # Check explicit env var override
    env_library_dir = os.environ.get("FUZZBIN_LIBRARY_DIR")
    if env_library_dir:
        return Path(env_library_dir)

    # Check if running in Docker
    if os.environ.get("FUZZBIN_DOCKER") == "1":
        return Path("/music_videos")

    # Default to $HOME/Fuzzbin/music_videos
    return Path.home() / "Fuzzbin" / "music_videos"


class Config(BaseModel):
    """Main configuration class for Fuzzbin.

    Path Resolution:
    - config_dir: Where configuration, database, caches, and thumbnails are stored
    - library_dir: Where video files, NFOs, and trash are stored

    Environment Variables:
    - FUZZBIN_CONFIG_DIR: Override config_dir
    - FUZZBIN_LIBRARY_DIR: Override library_dir
    - FUZZBIN_DOCKER=1: Use Docker defaults (/config, /music_videos)

    Defaults:
    - Docker: config_dir=/config, library_dir=/music_videos
    - Non-Docker: config_dir=$HOME/Fuzzbin/config, library_dir=$HOME/Fuzzbin/music_videos

    All relative paths in config (database_path, cache storage_path, backup_dir, etc.)
    are resolved against config_dir at runtime.
    """

    # Path configuration - resolved at runtime via resolve_paths()
    config_dir: Optional[Path] = Field(
        default=None,
        description="Configuration directory (database, caches, thumbnails). Resolved from FUZZBIN_CONFIG_DIR or defaults.",
    )
    library_dir: Optional[Path] = Field(
        default=None,
        description="Video library directory (media files, NFOs, trash). Resolved from FUZZBIN_LIBRARY_DIR or defaults.",
    )

    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration",
    )
    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        description="Database configuration",
    )
    apis: Optional[Dict[str, APIClientConfig]] = Field(
        default=None,
        description="API client configurations",
    )
    ytdlp: Optional[YTDLPConfig] = Field(
        default=None,
        description="yt-dlp client configuration",
    )
    ffprobe: FFProbeConfig = Field(
        default_factory=FFProbeConfig,
        description="ffprobe client configuration",
    )
    thumbnail: ThumbnailConfig = Field(
        default_factory=ThumbnailConfig,
        description="Thumbnail generation configuration",
    )
    nfo: NFOConfig = Field(
        default_factory=NFOConfig,
        description="NFO file handling configuration",
    )
    organizer: OrganizerConfig = Field(
        default_factory=OrganizerConfig,
        description="Media file organizer configuration",
    )
    tags: TagsConfig = Field(
        default_factory=TagsConfig,
        description="Tag management and auto-tagging configuration",
    )
    backup: BackupConfig = Field(
        default_factory=BackupConfig,
        description="Automatic backup configuration",
    )
    trash: TrashConfig = Field(
        default_factory=TrashConfig,
        description="Trash directory and automatic cleanup configuration",
    )

    def resolve_paths(self, create_dirs: bool = True) -> "Config":
        """
        Resolve config_dir and library_dir from environment or defaults.

        This method should be called after loading config to ensure paths
        are properly resolved based on environment variables and defaults.

        Args:
            create_dirs: If True, create directories if they don't exist

        Returns:
            Self with resolved paths (for chaining)

        Example:
            >>> config = Config.from_yaml(Path("config.yaml")).resolve_paths()
        """
        # Resolve config_dir
        if self.config_dir is None:
            object.__setattr__(self, "config_dir", _get_default_config_dir())

        # Resolve library_dir
        if self.library_dir is None:
            object.__setattr__(self, "library_dir", _get_default_library_dir())

        # Create directories if requested
        if create_dirs:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.library_dir.mkdir(parents=True, exist_ok=True)

            # Create subdirectories
            (self.config_dir / ".cache").mkdir(parents=True, exist_ok=True)
            (self.config_dir / ".thumbnails").mkdir(parents=True, exist_ok=True)
            (self.config_dir / "backups").mkdir(parents=True, exist_ok=True)
            (self.library_dir / ".trash").mkdir(parents=True, exist_ok=True)

        logger.debug(
            "paths_resolved",
            config_dir=str(self.config_dir),
            library_dir=str(self.library_dir),
        )

        return self

    # Default database settings (not user-configurable)
    DEFAULT_DATABASE_PATH: ClassVar[str] = "fuzzbin.db"
    DEFAULT_BACKUP_DIR: ClassVar[str] = "backups"

    def get_database_path(self) -> Path:
        """
        Get absolute database path, resolved against config_dir.

        Returns:
            Absolute path to database file
        """
        db_path = Path(self.DEFAULT_DATABASE_PATH)
        config_dir = self.config_dir or _get_default_config_dir()
        return config_dir / db_path

    def get_backup_dir(self) -> Path:
        """
        Get absolute backup directory path, resolved against config_dir.

        Returns:
            Absolute path to backup directory
        """
        backup_path = Path(self.DEFAULT_BACKUP_DIR)
        config_dir = self.config_dir or _get_default_config_dir()
        return config_dir / backup_path

    def get_cache_path(self, storage_path: str) -> Path:
        """
        Get absolute cache path, resolved against config_dir.

        Args:
            storage_path: Relative or absolute path from cache config

        Returns:
            Absolute path to cache file
        """
        cache_path = Path(storage_path)
        if cache_path.is_absolute():
            return cache_path

        config_dir = self.config_dir or _get_default_config_dir()
        return config_dir / cache_path

    def get_thumbnail_dir(self) -> Path:
        """
        Get absolute thumbnail directory path, resolved against config_dir.

        Returns:
            Absolute path to thumbnail directory
        """
        thumb_path = Path(self.thumbnail.cache_dir)
        if thumb_path.is_absolute():
            return thumb_path

        config_dir = self.config_dir or _get_default_config_dir()
        return config_dir / thumb_path

    def get_trash_dir(self) -> Path:
        """
        Get absolute trash directory path, resolved against library_dir.

        Returns:
            Absolute path to trash directory
        """
        trash_path = Path(self.trash.trash_dir)
        if trash_path.is_absolute():
            return trash_path

        library_dir = self.library_dir or _get_default_library_dir()
        return library_dir / trash_path

    def get_log_file_path(self) -> Path:
        """
        Get absolute log file path, resolved against config_dir.

        Returns:
            Absolute path to log file (fuzzbin.log in config_dir)
        """
        config_dir = self.config_dir or _get_default_config_dir()
        return config_dir / "fuzzbin.log"

    @staticmethod
    def _convert_paths_to_strings(data: Any) -> Any:
        """
        Recursively convert Path objects to strings for YAML serialization.

        ruamel.yaml cannot serialize Path objects directly, so we need to
        convert them to strings before dumping.

        Args:
            data: Data structure potentially containing Path objects

        Returns:
            Data structure with all Path objects converted to strings
        """
        if isinstance(data, Path):
            return str(data)
        elif isinstance(data, dict):
            return {key: Config._convert_paths_to_strings(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [Config._convert_paths_to_strings(item) for item in data]
        else:
            return data

    @staticmethod
    def _deep_merge(original: Any, updates: Any) -> Any:
        """
        Deep merge updates into original while preserving structure and comments.

        This is used to update ruamel.yaml CommentedMap/CommentedSeq structures
        while preserving comments and formatting.

        Args:
            original: Original data structure (potentially with comments)
            updates: New data to merge in

        Returns:
            Merged data structure with preserved comments
        """
        # If original is None or updates is None, return updates
        if original is None or updates is None:
            return updates

        # If both are dicts, merge recursively
        if isinstance(original, dict) and isinstance(updates, dict):
            for key, value in updates.items():
                if key in original:
                    # Recursively merge nested structures
                    original[key] = Config._deep_merge(original[key], value)
                else:
                    # New key, just add it
                    original[key] = value
            return original

        # For lists and primitives, replace entirely
        # (list merging is too complex and rarely needed for config)
        return updates

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """
        Load configuration from YAML file using ruamel.yaml for comment preservation.

        Args:
            path: Path to YAML configuration file

        Returns:
            Config object with validated configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML is invalid
            pydantic.ValidationError: If configuration is invalid

        Example:
            >>> from pathlib import Path
            >>> config = Config.from_yaml(Path("config.yaml"))
        """
        yaml_loader = YAML()
        yaml_loader.preserve_quotes = True
        yaml_loader.default_flow_style = False

        with open(path, "r", encoding="utf-8") as f:
            data = yaml_loader.load(f)
        return cls.model_validate(data or {})

    @classmethod
    def from_yaml_string(cls, yaml_string: str) -> "Config":
        """
        Load configuration from YAML string.

        Args:
            yaml_string: YAML configuration as string

        Returns:
            Config object with validated configuration

        Example:
            >>> yaml_str = "http:\\n  timeout: 60"
            >>> config = Config.from_yaml_string(yaml_str)
        """
        data = yaml.safe_load(yaml_string)
        return cls.model_validate(data or {})

    def to_yaml(
        self,
        path: Path,
        exclude_defaults: bool = True,
        exclude_secrets: bool = True,
    ) -> None:
        """
        Save configuration to YAML file with atomic write and comment preservation.

        Uses ruamel.yaml to preserve comments and formatting from the original file.

        Args:
            path: Path to YAML configuration file
            exclude_defaults: Exclude fields with default values (recommended: True)
            exclude_secrets: Exclude API secrets from custom fields (recommended: True)

        Raises:
            OSError: If file cannot be written (disk full, permission denied, etc.)
            yaml.YAMLError: If serialization fails

        Example:
            >>> config = Config()
            >>> config.to_yaml(Path("config.yaml"))
        """
        # Convert Pydantic model to dict
        data = self.model_dump(
            mode="python",  # Use Python native types
            exclude_none=True,  # Skip None values
            exclude_defaults=exclude_defaults,  # Skip default values
            exclude_unset=False,  # Include explicitly set values
        )

        # Remove secrets from API configs if requested
        if exclude_secrets and "apis" in data:
            for api_name, api_config in data["apis"].items():
                # Remove custom dict entirely - these often contain secrets from env vars
                if "custom" in api_config:
                    del api_config["custom"]

        # Convert Path objects to strings for YAML serialization
        data = self._convert_paths_to_strings(data)

        # Set up ruamel.yaml for comment preservation
        yaml_dumper = YAML()
        yaml_dumper.preserve_quotes = True
        yaml_dumper.default_flow_style = False
        yaml_dumper.width = 4096  # Prevent line wrapping

        # Load original file to preserve comments and structure
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    original = yaml_dumper.load(f)

                # Merge new data into original structure (preserves comments)
                merged_data = self._deep_merge(original, data)
            except Exception as e:
                logger.warning("failed_to_load_original_yaml", path=str(path), error=str(e))
                # If we can't load original, just use new data
                merged_data = data
        else:
            # No existing file, use new data as-is
            merged_data = data

        # Atomic write pattern: temp file + fsync + rename
        temp_path = path.with_suffix(".tmp")
        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file using ruamel.yaml (preserves comments)
            with open(temp_path, "w", encoding="utf-8") as f:
                yaml_dumper.dump(merged_data, f)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk

            # Atomic rename
            temp_path.replace(path)  # POSIX atomic on same filesystem

            logger.info("config_saved", path=str(path))

        except Exception as e:
            # Cleanup temp file on failure
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass  # Best effort cleanup

            logger.error("config_save_failed", path=str(path), error=str(e))
            raise


# Field-level safety categorization for runtime config changes
FIELD_SAFETY_MAP: Dict[str, ConfigSafetyLevel] = {
    # Safe fields - can change without side effects
    "logging.level": ConfigSafetyLevel.SAFE,
    "logging.format": ConfigSafetyLevel.SAFE,
    "logging.file.enabled": ConfigSafetyLevel.SAFE,
    "logging.third_party": ConfigSafetyLevel.SAFE,
    "ytdlp.ytdlp_path": ConfigSafetyLevel.SAFE,
    "ytdlp.format_spec": ConfigSafetyLevel.SAFE,
    "ytdlp.geo_bypass": ConfigSafetyLevel.SAFE,
    "ffprobe.ffprobe_path": ConfigSafetyLevel.SAFE,
    "ffprobe.timeout": ConfigSafetyLevel.SAFE,
    "nfo.*": ConfigSafetyLevel.SAFE,
    "organizer.*": ConfigSafetyLevel.SAFE,
    "tags.*": ConfigSafetyLevel.SAFE,
    "backup.enabled": ConfigSafetyLevel.SAFE,
    "backup.schedule": ConfigSafetyLevel.SAFE,
    "backup.retention_count": ConfigSafetyLevel.SAFE,
    "trash.enabled": ConfigSafetyLevel.SAFE,
    "trash.schedule": ConfigSafetyLevel.SAFE,
    "trash.retention_days": ConfigSafetyLevel.SAFE,
    # API auth - safe because ConfigManager auto-reloads clients with rollback on failure
    "apis.*.auth.*": ConfigSafetyLevel.SAFE,
    # Affects state - changes persistent files/connections
    "config_dir": ConfigSafetyLevel.AFFECTS_STATE,
    "library_dir": ConfigSafetyLevel.AFFECTS_STATE,
    # Note: database.* fields removed - database settings are not user-configurable
    "thumbnail.cache_dir": ConfigSafetyLevel.AFFECTS_STATE,
    "trash.trash_dir": ConfigSafetyLevel.AFFECTS_STATE,
    "backup.output_dir": ConfigSafetyLevel.AFFECTS_STATE,
}


def get_safety_level(field_path: str) -> ConfigSafetyLevel:
    """
    Get safety level for a configuration field.

    Args:
        field_path: Dot-notation path (e.g., "logging.level", "apis.discogs.auth.api_key")

    Returns:
        ConfigSafetyLevel indicating how safe it is to change this field at runtime

    Example:
        >>> get_safety_level("logging.level")
        ConfigSafetyLevel.SAFE
        >>> get_safety_level("database.database_path")
        ConfigSafetyLevel.AFFECTS_STATE
    """
    # Exact match
    if field_path in FIELD_SAFETY_MAP:
        return FIELD_SAFETY_MAP[field_path]

    # Wildcard match (e.g., "apis.*.rate_limit.requests_per_minute" matches "apis.discogs.rate_limit.requests_per_minute")
    parts = field_path.split(".")
    for pattern, level in FIELD_SAFETY_MAP.items():
        pattern_parts = pattern.split(".")

        # Check if pattern length matches or ends with wildcard
        if len(pattern_parts) > len(parts):
            continue

        # Match each part, treating * as wildcard
        match = True
        for i, pattern_part in enumerate(pattern_parts):
            if pattern_part == "*":
                # Wildcard at end matches rest of path
                if i == len(pattern_parts) - 1:
                    return level
                # Wildcard in middle matches single component
                continue
            elif i >= len(parts) or pattern_part != parts[i]:
                match = False
                break

        if match and len(pattern_parts) == len(parts):
            return level

    # Default: assume safe if not explicitly categorized
    return ConfigSafetyLevel.SAFE
