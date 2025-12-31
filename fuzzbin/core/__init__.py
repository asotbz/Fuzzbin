"""Core business logic for Fuzzbin.

This package contains core business logic and domain models including
the file organizer for music video metadata and the event bus for
real-time WebSocket updates.
"""

from .event_bus import (
    EventBus,
    get_event_bus,
    init_event_bus,
    reset_event_bus,
)
from .exceptions import (
    InvalidPathError,
    InvalidPatternError,
    MissingFieldError,
    OrganizerError,
)
from .organizer import MediaPaths, build_media_paths

__all__ = [
    "build_media_paths",
    "EventBus",
    "get_event_bus",
    "init_event_bus",
    "InvalidPathError",
    "InvalidPatternError",
    "MediaPaths",
    "MissingFieldError",
    "OrganizerError",
    "reset_event_bus",
]
