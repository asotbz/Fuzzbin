"""File organizer for music video metadata."""

import string
from pathlib import Path
from typing import Dict, Set

import structlog
from pydantic import BaseModel, Field

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

        # Special case: tags (list)
        if field == "tags":
            raise InvalidPatternError(
                "Field 'tags' is a list and cannot be used directly in path pattern. "
                "Use scalar fields like 'artist', 'title', etc.",
                pattern=None,
            )

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
    pattern: str,
    nfo_data: MusicVideoNFO,
    video_extension: str = ".mp4",
    normalize: bool = False,
) -> MediaPaths:
    """
    Build fully qualified paths for video and NFO files.

    Args:
        root_path: Root directory for media files
        pattern: Path pattern with {field} placeholders (e.g., "{artist}/{title}")
        nfo_data: MusicVideoNFO model containing metadata
        video_extension: Video file extension (default: ".mp4")
        normalize: Apply filename normalization (default: False)

    Returns:
        MediaPaths object with video_path and nfo_path

    Raises:
        InvalidPatternError: If pattern contains unknown fields or uses 'tags'
        MissingFieldError: If required pattern field is None/empty in NFO data
        InvalidPathError: If root_path doesn't exist or isn't a directory

    Example:
        >>> nfo = MusicVideoNFO(artist="Robin Thicke", title="Blurred Lines")
        >>> paths = build_media_paths(
        ...     root_path=Path("/var/media/music_videos"),
        ...     pattern="{artist}/{title}",
        ...     nfo_data=nfo,
        ...     normalize=True
        ... )
        >>> paths.video_path
        Path('/var/media/music_videos/robin_thicke/blurred_lines.mp4')
        >>> paths.nfo_path
        Path('/var/media/music_videos/robin_thicke/blurred_lines.nfo')
    """
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

    # 4. Apply normalization if requested
    if normalize:
        field_values = {k: normalize_filename(v) for k, v in field_values.items()}
        logger.debug("normalized_field_values", values=field_values)

    # 5. Build relative path from pattern
    relative_path = pattern.format(**field_values)

    # 6. Ensure extension has leading dot
    if not video_extension.startswith("."):
        video_extension = f".{video_extension}"

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
