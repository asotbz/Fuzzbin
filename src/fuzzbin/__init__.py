"""Fuzzbin package initialization."""

from pathlib import Path
from typing import Optional

import structlog

from .common.config import Config, DatabaseConfig, NFOConfig, OrganizerConfig
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
from .clients.ytdlp_client import YTDLPClient
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
from .core.exceptions import (
    YTDLPError,
    YTDLPNotFoundError,
    YTDLPExecutionError,
    YTDLPParseError,
    DownloadCancelledError,
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
    DuplicateRecordError,
    BackupError,
    QueryError,
    TransactionError,
)

__version__ = "0.1.0"
__all__ = [
    "AsyncHTTPClient",
    "RateLimitedAPIClient",
    "IMVDbClient",
    "DiscogsClient",
    "YTDLPClient",
    "RateLimiter",
    "ConcurrencyLimiter",
    "Config",
    "DatabaseConfig",
    "NFOConfig",
    "OrganizerConfig",
    "configure",
    "get_config",
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
]

# Module-level logger (not configured yet)
logger = structlog.get_logger(__name__)

# Global config and repository state
_config: Optional[Config] = None
_repository: Optional[VideoRepository] = None


async def configure(
    config_path: Optional[Path] = None, config: Optional[Config] = None
) -> None:
    """
    Configure the fuzzbin package (async).

    This function should be called once at application startup to initialize
    the configuration, logging, and database connection.

    Args:
        config_path: Path to YAML configuration file
        config: Pre-loaded Config object (takes precedence over config_path)

    Example:
        >>> import fuzzbin
        >>> from pathlib import Path
        >>> await fuzzbin.configure(config_path=Path("config.yaml"))
    """
    global _config, _repository

    if config is not None:
        _config = config
    elif config_path is not None:
        _config = Config.from_yaml(config_path)
    else:
        # Use defaults
        _config = Config()

    # Setup logging based on config
    setup_logging(_config.logging)
    
    # Initialize database repository
    _repository = await VideoRepository.from_config(_config.database)
    
    logger.info(
        "fuzzbin_configured",
        version=__version__,
        database_path=_config.database.database_path,
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
        
        _repository = await VideoRepository.from_config(_config.database)
        logger.info(
            "repository_auto_initialized",
            database_path=_config.database.database_path,
        )
    
    return _repository
