"""Core business logic for Fuzzbin.

This package contains core business logic and domain models including
the file organizer for music video metadata.
"""

from .exceptions import (
    InvalidPathError,
    InvalidPatternError,
    MissingFieldError,
    OrganizerError,
)
from .organizer import MediaPaths, build_media_paths

__all__ = [
    "build_media_paths",
    "MediaPaths",
    "OrganizerError",
    "InvalidPatternError",
    "MissingFieldError",
    "InvalidPathError",
]
