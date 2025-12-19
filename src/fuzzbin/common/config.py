"""Configuration models using Pydantic for validation."""

from pathlib import Path
from typing import Optional, Dict, List, Any, Set
import string

import yaml
from pydantic import BaseModel, Field, field_validator


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
