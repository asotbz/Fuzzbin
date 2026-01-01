"""Fuzzbin package initialization."""

from pathlib import Path
from typing import Optional

import structlog

from .common.config import (
    Config,
    DatabaseConfig,
    NFOConfig,
    OrganizerConfig,
    FFProbeConfig,
    ThumbnailConfig,
    TagsConfig,
    AutoDecadeConfig,
    FileManagerConfig,
    ConfigSafetyLevel,
    get_safety_level,
)
from .common.config_manager import (
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
from .common.logging_config import setup_logging
from .common.http_client import AsyncHTTPClient
from .common.rate_limiter import RateLimiter
from .common.concurrency_limiter import ConcurrencyLimiter
from .common.string_utils import (
    normalize_string,
    remove_featured_artists,
    normalize_for_matching,
    normalize_filename,
)
from .api.base_client import RateLimitedAPIClient
from .api.imvdb_client import IMVDbClient
from .api.discogs_client import DiscogsClient
from .api.spotify_client import SpotifyClient
from .api.spotify_auth import SpotifyTokenManager
from .clients.ytdlp_client import YTDLPClient
from .clients.ffprobe_client import FFProbeClient
from .clients.ffmpeg_client import FFmpegClient
from .parsers import (
    ArtistNFO,
    MusicVideoNFO,
    FeaturedArtistConfig,
    ArtistNFOParser,
    MusicVideoNFOParser,
    IMVDbVideo,
    IMVDbEntity,
    IMVDbEntitySearchResult,
    IMVDbEntitySearchResponse,
    IMVDbVideoSearchResult,
    IMVDbParser,
    VideoNotFoundError,
    EmptySearchResultsError,
    DiscogsMaster,
    DiscogsRelease,
    DiscogsSearchResult,
    DiscogsArtistReleasesResult,
    DiscogsParser,
    MasterNotFoundError,
    ReleaseNotFoundError,
    FFProbeFormat,
    FFProbeVideoStream,
    FFProbeAudioStream,
    FFProbeMediaInfo,
    FFProbeParser,
)
from .parsers.ytdlp_models import (
    YTDLPSearchResult,
    YTDLPDownloadResult,
    DownloadProgress,
    CancellationToken,
    DownloadHooks,
)
from .core import (
    build_media_paths,
    MediaPaths,
    OrganizerError,
    InvalidPatternError,
    MissingFieldError,
    InvalidPathError,
)
from .core.file_manager import (
    FileManager,
    FileManagerError,
    HashMismatchError,
    RollbackError,
    FileTooLargeError,
    DuplicateCandidate,
    LibraryIssue,
    LibraryReport,
)
from .core.exceptions import (
    YTDLPError,
    YTDLPNotFoundError,
    YTDLPExecutionError,
    YTDLPParseError,
    DownloadCancelledError,
    FFProbeError,
    FFProbeNotFoundError,
    FFProbeExecutionError,
    FFProbeParseError,
    FFmpegError,
    FFmpegNotFoundError,
    FFmpegExecutionError,
    ThumbnailTooLargeError,
)
from .core.db import (
    VideoRepository,
    VideoQuery,
    NFOExporter,
    DatabaseBackup,
    DatabaseError,
    DatabaseConnectionError,
    MigrationError,
    VideoNotFoundError as DBVideoNotFoundError,
    ArtistNotFoundError,
    CollectionNotFoundError,
    TagNotFoundError,
    DuplicateRecordError,
    BackupError,
    QueryError,
    TransactionError,
)
from .workflows import (
    ImportResult,
    NFOImporter,
    SpotifyPlaylistImporter,
)

__version__ = "0.1.0"
__all__ = [
    "AsyncHTTPClient",
    "RateLimitedAPIClient",
    "IMVDbClient",
    "DiscogsClient",
    "SpotifyClient",
    "SpotifyTokenManager",
    "YTDLPClient",
    "FFProbeClient",
    "FFmpegClient",
    "RateLimiter",
    "ConcurrencyLimiter",
    "Config",
    "DatabaseConfig",
    "NFOConfig",
    "OrganizerConfig",
    "FFProbeConfig",
    "ThumbnailConfig",
    "TagsConfig",
    "AutoDecadeConfig",
    "FileManagerConfig",
    "ConfigSafetyLevel",
    "get_safety_level",
    "ConfigManager",
    "ConfigChangeEvent",
    "ConfigSnapshot",
    "ConfigHistory",
    "ClientStats",
    "get_client_stats",
    "ConfigManagerError",
    "ConfigValidationError",
    "ConfigSaveError",
    "ClientReloadError",
    "configure",
    "get_config",
    "get_config_manager",
    "get_repository",
    "VideoRepository",
    "VideoQuery",
    "NFOExporter",
    "DatabaseBackup",
    "DatabaseError",
    "DatabaseConnectionError",
    "MigrationError",
    "DBVideoNotFoundError",
    "ArtistNotFoundError",
    "CollectionNotFoundError",
    "TagNotFoundError",
    "DuplicateRecordError",
    "BackupError",
    "QueryError",
    "TransactionError",
    "ArtistNFO",
    "MusicVideoNFO",
    "FeaturedArtistConfig",
    "ArtistNFOParser",
    "MusicVideoNFOParser",
    "IMVDbVideo",
    "IMVDbEntity",
    "IMVDbEntitySearchResult",
    "IMVDbEntitySearchResponse",
    "IMVDbVideoSearchResult",
    "IMVDbParser",
    "VideoNotFoundError",
    "EmptySearchResultsError",
    "DiscogsMaster",
    "DiscogsRelease",
    "DiscogsSearchResult",
    "DiscogsArtistReleasesResult",
    "DiscogsParser",
    "MasterNotFoundError",
    "ReleaseNotFoundError",
    "YTDLPSearchResult",
    "YTDLPDownloadResult",
    "DownloadProgress",
    "CancellationToken",
    "DownloadHooks",
    "YTDLPError",
    "YTDLPNotFoundError",
    "YTDLPExecutionError",
    "YTDLPParseError",
    "DownloadCancelledError",
    "FFProbeFormat",
    "FFProbeVideoStream",
    "FFProbeAudioStream",
    "FFProbeMediaInfo",
    "FFProbeParser",
    "FFProbeError",
    "FFProbeNotFoundError",
    "FFProbeExecutionError",
    "FFProbeParseError",
    "FFmpegError",
    "FFmpegNotFoundError",
    "FFmpegExecutionError",
    "ThumbnailTooLargeError",
    "normalize_string",
    "remove_featured_artists",
    "normalize_for_matching",
    "normalize_filename",
    "build_media_paths",
    "MediaPaths",
    "OrganizerError",
    "InvalidPatternError",
    "MissingFieldError",
    "InvalidPathError",
    "FileManager",
    "FileManagerError",
    "HashMismatchError",
    "RollbackError",
    "FileTooLargeError",
    "DuplicateCandidate",
    "LibraryIssue",
    "LibraryReport",
    "ImportResult",
    "NFOImporter",
    "SpotifyPlaylistImporter",
]

# Module-level logger (not configured yet)
logger = structlog.get_logger(__name__)

# Global config and repository state
_config: Optional[Config] = None
_repository: Optional[VideoRepository] = None
_config_manager: Optional[ConfigManager] = None


async def configure(config_path: Optional[Path] = None, config: Optional[Config] = None) -> None:
    """
    Configure the fuzzbin package (async).

    This function should be called once at application startup to initialize
    the configuration, logging, and database connection.

    Path Resolution:
    - If config_path is provided, load from that file
    - Otherwise, search in FUZZBIN_CONFIG_DIR, then defaults
    - Config paths (database, cache, thumbnails) are resolved against config_dir
    - Library paths (media, NFO, trash) are resolved against library_dir

    Args:
        config_path: Path to YAML configuration file
        config: Pre-loaded Config object (takes precedence over config_path)

    Example:
        >>> import fuzzbin
        >>> from pathlib import Path
        >>> await fuzzbin.configure(config_path=Path("config.yaml"))
    """
    global _config, _repository, _config_manager

    from fuzzbin.common.config import _get_default_config_dir

    if config is not None:
        _config = config
    elif config_path is not None:
        _config = Config.from_yaml(config_path)
    else:
        # Search for config.yaml in default locations.
        #
        # Important: fuzzbin.get_config() can be called before configure() (sync).
        # That initializes _config with defaults, but we still want configure() to
        # load YAML if available.
        default_config_dir = _get_default_config_dir()
        default_config_path = default_config_dir / "config.yaml"

        # Also allow running from a repo / working directory without copying files
        # into the default config_dir.
        cwd_config_path = Path.cwd() / "config.yaml"

        if default_config_path.exists():
            _config = Config.from_yaml(default_config_path)
            config_path = default_config_path
        elif cwd_config_path.exists():
            _config = Config.from_yaml(cwd_config_path)
            config_path = cwd_config_path
        elif _config is None:
            # Use defaults only if not already configured
            _config = Config()

    # Resolve paths (config_dir, library_dir) from environment or defaults
    _config.resolve_paths(create_dirs=True)

    # Setup logging based on config
    setup_logging(_config.logging)

    # Initialize database repository (only if not already initialized)
    if _repository is None:
        _repository = await VideoRepository.from_config(
            _config.database,
            config_dir=_config.config_dir,
            library_dir=_config.library_dir,
        )

    # Initialize config manager (only if not already initialized)
    if _config_manager is None:
        _config_manager = ConfigManager(
            config=_config,
            config_path=config_path,
        )

    logger.info(
        "fuzzbin_configured",
        version=__version__,
        config_path=str(config_path) if config_path else None,
        config_dir=str(_config.config_dir),
        library_dir=str(_config.library_dir),
        database_path=str(_config.get_database_path()),
    )


def get_config() -> Config:
    """
    Get current configuration, initializing with defaults if needed.

    Returns:
        Current Config object

    Example:
        >>> import fuzzbin
        >>> config = fuzzbin.get_config()
        >>> print(config.http.timeout)
        30
    """
    global _config
    if _config is None:
        # Note: This will not initialize the repository since it's not async
        # Users should call await configure() explicitly
        _config = Config()
        setup_logging(_config.logging)
    return _config


def get_config_manager() -> ConfigManager:
    """
    Get configuration manager instance, initializing if needed.

    Returns:
        ConfigManager instance

    Note:
        This creates a manager without a config_path if not previously configured.
        Call configure() first for full functionality.

    Example:
        >>> import fuzzbin
        >>> await fuzzbin.configure(config_path=Path("config.yaml"))
        >>> manager = fuzzbin.get_config_manager()
        >>> await manager.update("http.timeout", 60)
    """
    global _config_manager, _config

    if _config_manager is None:
        if _config is None:
            _config = Config()
            setup_logging(_config.logging)

        _config_manager = ConfigManager(
            config=_config,
            config_path=None,  # No auto-save without explicit configure()
        )
        logger.info("config_manager_auto_initialized")

    return _config_manager


async def get_repository() -> VideoRepository:
    """
    Get video repository instance, initializing if needed (async).

    Returns:
        VideoRepository instance

    Raises:
        RuntimeError: If repository not initialized (call configure() first)

    Example:
        >>> import fuzzbin
        >>> await fuzzbin.configure()
        >>> repo = await fuzzbin.get_repository()
        >>> videos = await repo.query().where_artist("Madonna").execute()
    """
    global _repository, _config

    if _repository is None:
        if _config is None:
            _config = Config()
            setup_logging(_config.logging)

        _repository = await VideoRepository.from_config(
            _config.database,
            config_dir=_config.config_dir,
        )
        logger.info(
            "repository_auto_initialized",
            database_path=str(_config.get_database_path()),
        )

    return _repository
