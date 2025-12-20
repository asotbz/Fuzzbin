"""Configuration models using Pydantic for validation."""

import os
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any, Set
import string

import yaml
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
    """Configuration for file-based logging."""

    path: str = Field(
        default="logs/fuzzbin.log",
        description="Path to log file",
    )
    max_bytes: int = Field(
        default=10485760,  # 10MB
        ge=1024,
        description="Maximum size of log file before rotation",
    )
    backup_count: int = Field(
        default=5,
        ge=0,
        le=50,
        description="Number of backup log files to keep",
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
    handlers: List[str] = Field(
        default_factory=lambda: ["console"],
        description="Enabled log handlers: console, file",
    )
    file: Optional[FileLoggingConfig] = Field(
        default=None,
        description="File logging configuration (optional)",
    )
    third_party: Dict[str, str] = Field(
        default_factory=dict,
        description="Log levels for third-party libraries",
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"Invalid log level: {v}. Must be one of {valid_levels}"
            )
        return v_upper

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = ["json", "text"]
        v_lower = v.lower()
        if v_lower not in valid_formats:
            raise ValueError(
                f"Invalid format: {v}. Must be one of {valid_formats}"
            )
        return v_lower

    @field_validator("handlers")
    @classmethod
    def validate_handlers(cls, v: List[str]) -> List[str]:
        """Validate handlers."""
        valid_handlers = ["console", "file"]
        for handler in v:
            if handler not in valid_handlers:
                raise ValueError(
                    f"Invalid handler: {handler}. Must be one of {valid_handlers}"
                )
        return v


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
                raise ValueError(
                    f"Invalid HTTP method: {method}. Must be one of {valid_methods}"
                )
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
    """Configuration for a specific API client."""

    name: str = Field(
        description="Name of the API client",
    )
    base_url: str = Field(
        description="Base URL for the API",
    )
    http: HTTPConfig = Field(
        default_factory=HTTPConfig,
        description="HTTP client configuration",
    )
    rate_limit: Optional[RateLimitConfig] = Field(
        default=None,
        description="Rate limiting configuration",
    )
    concurrency: Optional[ConcurrencyConfig] = Field(
        default=None,
        description="Concurrency control configuration",
    )
    cache: Optional[CacheConfig] = Field(
        default=None,
        description="Response caching configuration",
    )
    auth: Optional[Dict[str, str]] = Field(
        default=None,
        description="Authentication configuration (headers, tokens, etc.)",
    )
    custom: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Custom API-specific configuration",
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
    quiet: bool = Field(
        default=False,
        description="Suppress progress output during downloads",
    )
    search_max_results: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Default maximum search results",
    )
    timeout: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Command execution timeout in seconds",
    )


class FFProbeConfig(BaseModel):
    """Configuration for ffprobe client."""

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
    show_format: bool = Field(
        default=True,
        description="Include format/container information in output",
    )
    show_streams: bool = Field(
        default=True,
        description="Include stream information in output",
    )


class ThumbnailConfig(BaseModel):
    """Configuration for thumbnail generation via ffmpeg."""

    cache_dir: str = Field(
        default=".thumbnails",
        description="Directory for cached thumbnails (relative to workspace_root)",
    )
    default_timestamp: float = Field(
        default=5.0,
        ge=0.0,
        description="Default timestamp in seconds to extract frame from",
    )
    width: int = Field(
        default=320,
        ge=32,
        le=1920,
        description="Thumbnail width in pixels",
    )
    height: int = Field(
        default=180,
        ge=32,
        le=1080,
        description="Thumbnail height in pixels",
    )
    quality: int = Field(
        default=5,
        ge=1,
        le=31,
        description="JPEG quality (1=best, 31=worst)",
    )
    max_file_size: int = Field(
        default=5 * 1024 * 1024,  # 5MB
        ge=1024,
        description="Maximum thumbnail file size in bytes (safety limit)",
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="FFmpeg execution timeout in seconds",
    )
    ffmpeg_path: str = Field(
        default="ffmpeg",
        description="Path to ffmpeg binary",
    )


class DatabaseConfig(BaseModel):
    """Configuration for SQLite database."""

    database_path: str = Field(
        default=".db/fuzzbin_metadata.db",
        description="Path to SQLite metadata database file",
    )
    workspace_root: Optional[str] = Field(
        default=None,
        description="Workspace root directory for relative path calculation",
    )
    enable_wal_mode: bool = Field(
        default=True,
        description="Enable Write-Ahead Logging mode for better concurrency",
    )
    connection_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Database connection timeout in seconds",
    )
    backup_dir: str = Field(
        default=".db/backups",
        description="Directory for database backups",
    )


class NFOConfig(BaseModel):
    """Configuration for NFO file handling."""

    featured_artists: Optional["FeaturedArtistConfig"] = Field(  # noqa: F821
        default=None,
        description="Featured artist handling configuration",
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
                f"Invalid pattern fields: {invalid_fields}. "
                f"Valid fields: {valid_fields}"
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


class FileManagerConfig(BaseModel):
    """Configuration for file management operations.
    
    Controls file organization, soft delete/restore, and integrity verification.
    All file operations use aiofiles for non-blocking I/O.
    """

    trash_dir: str = Field(
        default=".trash",
        description="Directory for soft-deleted files (relative to workspace_root)",
    )
    hash_algorithm: str = Field(
        default="sha256",
        description="Hash algorithm for file integrity checks: sha256 or xxhash",
    )
    verify_after_move: bool = Field(
        default=True,
        description="Verify file hash after move to ensure integrity",
    )
    max_file_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum file size in bytes for operations (None = no limit)",
    )
    chunk_size: int = Field(
        default=8192,
        ge=1024,
        le=1048576,
        description="Chunk size in bytes for file hashing operations",
    )

    @field_validator("hash_algorithm")
    @classmethod
    def validate_hash_algorithm(cls, v: str) -> str:
        """Validate hash algorithm is supported."""
        valid_algorithms = ["sha256", "xxhash", "md5"]
        v_lower = v.lower()
        if v_lower not in valid_algorithms:
            raise ValueError(
                f"Invalid hash algorithm: {v}. Must be one of {valid_algorithms}"
            )
        return v_lower


class Config(BaseModel):
    """Main configuration class for Fuzzbin."""

    http: HTTPConfig = Field(
        default_factory=HTTPConfig,
        description="HTTP client configuration",
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
    file_manager: FileManagerConfig = Field(
        default_factory=FileManagerConfig,
        description="File management and organization configuration",
    )

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """
        Load configuration from YAML file.

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
        with open(path, "r") as f:
            data = yaml.safe_load(f)
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
        Save configuration to YAML file with atomic write.

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

        # Atomic write pattern: temp file + fsync + rename
        temp_path = path.with_suffix(".tmp")
        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file
            with open(temp_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,  # Preserve field order (Python 3.7+)
                )
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
    "http.timeout": ConfigSafetyLevel.SAFE,
    "http.max_redirects": ConfigSafetyLevel.SAFE,
    "http.verify_ssl": ConfigSafetyLevel.SAFE,
    "http.retry.max_attempts": ConfigSafetyLevel.SAFE,
    "http.retry.backoff_multiplier": ConfigSafetyLevel.SAFE,
    "http.retry.min_wait": ConfigSafetyLevel.SAFE,
    "http.retry.max_wait": ConfigSafetyLevel.SAFE,
    "http.retry.status_codes": ConfigSafetyLevel.SAFE,
    "logging.level": ConfigSafetyLevel.SAFE,
    "logging.format": ConfigSafetyLevel.SAFE,
    "logging.handlers": ConfigSafetyLevel.SAFE,
    "logging.third_party": ConfigSafetyLevel.SAFE,
    "logging.file.path": ConfigSafetyLevel.SAFE,
    "logging.file.max_bytes": ConfigSafetyLevel.SAFE,
    "logging.file.backup_count": ConfigSafetyLevel.SAFE,
    "ytdlp.binary_path": ConfigSafetyLevel.SAFE,
    "ytdlp.default_download_path": ConfigSafetyLevel.SAFE,
    "ytdlp.format": ConfigSafetyLevel.SAFE,
    "ytdlp.extract_audio": ConfigSafetyLevel.SAFE,
    "ytdlp.audio_format": ConfigSafetyLevel.SAFE,
    "ytdlp.additional_args": ConfigSafetyLevel.SAFE,
    "ffprobe.binary_path": ConfigSafetyLevel.SAFE,
    "ffprobe.timeout": ConfigSafetyLevel.SAFE,
    "ffprobe.show_format": ConfigSafetyLevel.SAFE,
    "ffprobe.show_streams": ConfigSafetyLevel.SAFE,
    "nfo.*": ConfigSafetyLevel.SAFE,
    "organizer.*": ConfigSafetyLevel.SAFE,
    "tags.*": ConfigSafetyLevel.SAFE,
    # Requires reload - need to recreate components
    "http.max_connections": ConfigSafetyLevel.REQUIRES_RELOAD,
    "http.max_keepalive_connections": ConfigSafetyLevel.REQUIRES_RELOAD,
    "apis.*.base_url": ConfigSafetyLevel.REQUIRES_RELOAD,
    "apis.*.http.*": ConfigSafetyLevel.REQUIRES_RELOAD,
    "apis.*.rate_limit.*": ConfigSafetyLevel.REQUIRES_RELOAD,
    "apis.*.concurrency.*": ConfigSafetyLevel.REQUIRES_RELOAD,
    "apis.*.cache.enabled": ConfigSafetyLevel.REQUIRES_RELOAD,
    "apis.*.cache.ttl": ConfigSafetyLevel.REQUIRES_RELOAD,
    "apis.*.cache.force_cache": ConfigSafetyLevel.REQUIRES_RELOAD,
    "apis.*.cache.cacheable_methods": ConfigSafetyLevel.REQUIRES_RELOAD,
    "apis.*.cache.cacheable_status_codes": ConfigSafetyLevel.REQUIRES_RELOAD,
    "apis.*.custom.*": ConfigSafetyLevel.REQUIRES_RELOAD,
    # Affects state - changes persistent files/connections
    "database.database_path": ConfigSafetyLevel.AFFECTS_STATE,
    "database.workspace_root": ConfigSafetyLevel.AFFECTS_STATE,
    "database.enable_wal_mode": ConfigSafetyLevel.AFFECTS_STATE,
    "database.connection_timeout": ConfigSafetyLevel.AFFECTS_STATE,
    "database.backup_dir": ConfigSafetyLevel.AFFECTS_STATE,
    "apis.*.cache.storage_path": ConfigSafetyLevel.AFFECTS_STATE,
}


def get_safety_level(field_path: str) -> ConfigSafetyLevel:
    """
    Get safety level for a configuration field.

    Args:
        field_path: Dot-notation path (e.g., "http.timeout", "apis.discogs.rate_limit.requests_per_minute")

    Returns:
        ConfigSafetyLevel indicating how safe it is to change this field at runtime

    Example:
        >>> get_safety_level("http.timeout")
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
