"""String normalization utilities for matching and comparison."""

import re
from typing import Optional


def normalize_string(text: str) -> str:
    """
    Normalize a string for matching by converting to lowercase and stripping whitespace.

    Args:
        text: String to normalize

    Returns:
        Normalized string (lowercase, stripped)

    Example:
        >>> normalize_string("  Robin Thicke  ")
        'robin thicke'
        >>> normalize_string("Blurred LINES")
        'blurred lines'
    """
    return text.strip().lower()


def remove_featured_artists(text: str) -> str:
    """
    Remove featured artists from a string.

    Detects patterns like "ft.", "feat.", "featuring", "f/" (case-insensitive)
    and removes everything after the pattern, including the pattern itself.

    Args:
        text: String potentially containing featured artist notation

    Returns:
        String with featured artists removed

    Example:
        >>> remove_featured_artists("Robin Thicke ft. T.I.")
        'Robin Thicke'
        >>> remove_featured_artists("Artist feat. Other & Another")
        'Artist'
        >>> remove_featured_artists("Song f/ Featured")
        'Song'
        >>> remove_featured_artists("No Featured Artists")
        'No Featured Artists'
    """
    # Pattern matches: ft., ft, feat., feat, featuring, f/
    # Use word boundaries for ft/feat variants, but not for f/ which uses /
    # Handle both mid-string and start-of-string cases
    pattern = r'(?:^|\s+)(?:ft\.?|feat\.?|featuring|f/)(?:\s+.*)?$'
    result = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return result.strip()


def normalize_for_matching(text: str, remove_featured: bool = True) -> str:
    """
    Normalize a string for matching operations.

    Combines string normalization (lowercase, strip) with optional featured
    artist removal for consistent search behavior.

    Args:
        text: String to normalize
        remove_featured: Whether to remove featured artist notation (default: True)

    Returns:
        Normalized string ready for matching

    Example:
        >>> normalize_for_matching("Robin Thicke ft. T.I.")
        'robin thicke'
        >>> normalize_for_matching("  Blurred LINES  ")
        'blurred lines'
        >>> normalize_for_matching("Artist feat. Other", remove_featured=False)
        'artist feat. other'
    """
    result = text
    if remove_featured:
        result = remove_featured_artists(result)
    return normalize_string(result)
