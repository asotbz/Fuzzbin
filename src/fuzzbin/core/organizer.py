"""File organizer for music video metadata."""

import string
from pathlib import Path
from typing import Dict, Set, Optional, TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ..common.config import OrganizerConfig

from ..common.string_utils import normalize_filename
from ..parsers.models import MusicVideoNFO
from .exceptions import InvalidPathError, InvalidPatternError, MissingFieldError

logger = structlog.get_logger(__name__)


class MediaPaths(BaseModel):
    """Fully qualified paths for media files."""

    video_path: Path = Field(description="Absolute path to video file")
    nfo_path: Path = Field(description="Absolute path to NFO file")

    model_config = {
        "frozen": True,  # Immutable result
    }


def _extract_pattern_fields(pattern: str) -> Set[str]:
    """
    Extract field names from pattern using string.Formatter.

    Args:
        pattern: Path pattern with {field} placeholders

    Returns:
        Set of field names found in pattern

    Example:
        >>> _extract_pattern_fields("{artist}/{title}")
        {'artist', 'title'}
    """
    formatter = string.Formatter()
    field_names = set()
    for _, field_name, _, _ in formatter.parse(pattern):
        if field_name:
            field_names.add(field_name)
    return field_names


def _validate_pattern_fields(pattern_fields: Set[str], pattern: str) -> None:
    """
    Validate pattern fields exist in MusicVideoNFO model.

    Args:
        pattern_fields: Set of field names from pattern
        pattern: Original pattern string for error messages

    Raises:
        InvalidPatternError: If pattern contains unknown fields
    """
    valid_fields = set(MusicVideoNFO.model_fields.keys())
    invalid_fields = pattern_fields - valid_fields
    if invalid_fields:
        raise InvalidPatternError(
            f"Invalid pattern fields: {invalid_fields}. Valid fields: {valid_fields}",
            pattern=pattern,
        )


def _get_field_values(nfo_data: MusicVideoNFO, pattern_fields: Set[str]) -> Dict[str, str]:
    """
    Extract field values from NFO data and validate they're not None/empty.

    Args:
        nfo_data: MusicVideoNFO object containing metadata
        pattern_fields: Set of field names to extract

    Returns:
        Dictionary mapping field names to string values

    Raises:
        MissingFieldError: If required pattern field is None or empty
        InvalidPatternError: If pattern uses 'tags' field (list type)
    """
    field_values = {}
    for field in pattern_fields:
        value = getattr(nfo_data, field)

        # Special case: tags (list) - not allowed
        if field == "tags":
            raise InvalidPatternError(
                "Field 'tags' is a list and cannot be used directly in path pattern. "
                "Use scalar fields like 'artist', 'title', etc.",
                pattern=None,
            )

        # Special case: featured_artists (list) - join with comma-space
        if field == "featured_artists":
            if not value:  # Empty list
                raise MissingFieldError(
                    f"Field '{field}' is required by pattern but is empty in NFO data",
                    field=field,
                )
            field_values[field] = ", ".join(value)
            continue

        # Check for None or empty string
        if value is None or (isinstance(value, str) and not value.strip()):
            raise MissingFieldError(
                f"Field '{field}' is required by pattern but is None or empty in NFO data",
                field=field,
            )

        field_values[field] = str(value)

    return field_values


def build_media_paths(
    root_path: Path,
    nfo_data: MusicVideoNFO,
    pattern: Optional[str] = None,
    normalize: Optional[bool] = None,
    config: Optional["OrganizerConfig"] = None,
) -> MediaPaths:
    """
    Build fully qualified paths for video and NFO files.

    This function supports two usage patterns:
    1. **Legacy/Explicit**: Pass pattern and normalize explicitly
    2. **Config-based**: Pass config object providing defaults (can override)

    Args:
        root_path: Root directory for media files
        nfo_data: MusicVideoNFO model containing metadata
        pattern: Path pattern with {field} placeholders (required if config not provided)
        normalize: Apply filename normalization (overrides config if provided)
        config: OrganizerConfig providing default pattern and normalize settings

    Returns:
        MediaPaths object with video_path and nfo_path

    Raises:
        TypeError: If both pattern and config are None
        InvalidPatternError: If pattern contains unknown fields or uses 'tags'
        MissingFieldError: If required pattern field is None/empty in NFO data
        InvalidPathError: If root_path doesn't exist or isn't a directory

    Example:
        >>> # Legacy usage
        >>> nfo = MusicVideoNFO(artist="Robin Thicke", title="Blurred Lines")
        >>> paths = build_media_paths(
        ...     root_path=Path("/var/media/music_videos"),
        ...     nfo_data=nfo,
        ...     pattern="{artist}/{title}",
        ...     normalize=True
        ... )
        >>> paths.video_path
        Path('/var/media/music_videos/robin_thicke/blurred_lines.mp4')

        >>> # Config-based usage
        >>> from fuzzbin.common.config import OrganizerConfig
        >>> config = OrganizerConfig(
        ...     path_pattern="{artist}/{title}",
        ...     normalize_filenames=True
        ... )
        >>> paths = build_media_paths(
        ...     root_path=Path("/var/media/music_videos"),
        ...     nfo_data=nfo,
        ...     config=config
        ... )
    """
    # Resolve parameters: explicit params override config defaults
    if config is not None:
        pattern = pattern or config.path_pattern
        normalize = normalize if normalize is not None else config.normalize_filenames
    else:
        # Legacy behavior: require pattern parameter
        if pattern is None:
            raise TypeError(
                "pattern is required when config is not provided. "
                "Pass either pattern explicitly or provide config with path_pattern."
            )
        normalize = normalize or False

    # 1. Validate root_path
    if not root_path.exists():
        raise InvalidPathError(f"Root path does not exist: {root_path}", path=root_path)
    if not root_path.is_dir():
        raise InvalidPathError(
            f"Root path is not a directory: {root_path}", path=root_path
        )

    # 2. Extract and validate pattern fields
    pattern_fields = _extract_pattern_fields(pattern)
    logger.debug("extracted_pattern_fields", fields=pattern_fields, pattern=pattern)

    _validate_pattern_fields(pattern_fields, pattern)

    # 3. Get field values from NFO data
    field_values = _get_field_values(nfo_data, pattern_fields)

    # 4. Apply normalization to field values if requested
    if normalize:
        field_values = {k: normalize_filename(v) for k, v in field_values.items()}
        logger.debug("normalized_field_values", values=field_values)

    # 5. Build relative path from pattern
    relative_path = pattern.format(**field_values)

    # 6. Hardcode video extension to .mp4
    video_extension = ".mp4"

    # 7. Build full paths
    video_path = root_path / f"{relative_path}{video_extension}"
    nfo_path = root_path / f"{relative_path}.nfo"

    logger.info(
        "media_paths_built",
        video_path=str(video_path),
        nfo_path=str(nfo_path),
        pattern=pattern,
        normalized=normalize,
    )

    return MediaPaths(video_path=video_path, nfo_path=nfo_path)
