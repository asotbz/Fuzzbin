"""Fuzzbin package initialization."""

from pathlib import Path
from typing import Optional

import structlog

from .common.config import Config
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
from .core import (
    build_media_paths,
    MediaPaths,
    OrganizerError,
    InvalidPatternError,
    MissingFieldError,
    InvalidPathError,
)

__version__ = "0.1.0"
__all__ = [
    "AsyncHTTPClient",
    "RateLimitedAPIClient",
    "IMVDbClient",
    "DiscogsClient",
    "RateLimiter",
    "ConcurrencyLimiter",
    "Config",
    "configure",
    "get_config",
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

# Global config state
_config: Optional[Config] = None


def configure(
    config_path: Optional[Path] = None, config: Optional[Config] = None
) -> None:
    """
    Configure the fuzzbin package.

    This function should be called once at application startup to initialize
    the configuration and logging.

    Args:
        config_path: Path to YAML configuration file
        config: Pre-loaded Config object (takes precedence over config_path)

    Example:
        >>> import fuzzbin
        >>> from pathlib import Path
        >>> fuzzbin.configure(config_path=Path("config.yaml"))
    """
    global _config

    if config is not None:
        _config = config
    elif config_path is not None:
        _config = Config.from_yaml(config_path)
    else:
        # Use defaults
        _config = Config()

    # Setup logging based on config
    setup_logging(_config.logging)
    logger.info("fuzzbin_configured", version=__version__)


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
        configure()  # Auto-configure with defaults
    return _config
