"""String normalization utilities for matching and comparison."""

import re
import unicodedata
from typing import List, Optional


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


def normalize_filename(text: str) -> str:
    """
    Normalize text for use in filenames and directory names.

    Applies the following transformations in order:
    1. Normalize unicode (NFKD decomposition)
    2. Remove combining characters (accents/diacritics)
    3. Convert to lowercase
    4. Remove hyphens
    5. Remove special characters (keep only alphanumeric and spaces)
    6. Replace spaces with underscores
    7. Condense multiple underscores to single
    8. Strip leading/trailing underscores

    Args:
        text: String to normalize

    Returns:
        Normalized string suitable for filesystem use

    Example:
        >>> normalize_filename("Björk - Humúríús")
        'bjork_humurius'
        >>> normalize_filename("Tëst  Multiple   Spaces")
        'test_multiple_spaces'
        >>> normalize_filename("AC/DC")
        'acdc'
        >>> normalize_filename("Artist (Remix)")
        'artist_remix'
    """
    # Normalize unicode (NFKD decomposition)
    normalized = unicodedata.normalize('NFKD', text)

    # Remove combining characters (accents)
    # Category 'Mn' = Nonspacing_Mark (combining diacriticals)
    normalized = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')

    # Convert to lowercase
    normalized = normalized.lower()

    # Remove hyphens
    normalized = normalized.replace('-', '')

    # Remove special characters (keep alphanumeric and spaces)
    normalized = re.sub(r'[^a-z0-9\s]', '', normalized)

    # Replace spaces with underscores
    normalized = normalized.replace(' ', '_')

    # Condense multiple underscores to single
    normalized = re.sub(r'_+', '_', normalized)

    # Strip leading/trailing underscores
    normalized = normalized.strip('_')

    return normalized


def format_featured_artists(featured_artists: List[str]) -> str:
    """
    Format a list of featured artists for appending to a field.

    Produces format: "ft. Artist1, Artist2, Artist3"

    Args:
        featured_artists: List of featured artist names

    Returns:
        Formatted string with "ft. " prefix and comma-separated artists,
        or empty string if list is empty

    Example:
        >>> format_featured_artists(["T.I.", "Pharrell Williams"])
        'ft. T.I., Pharrell Williams'
        >>> format_featured_artists(["Drake"])
        'ft. Drake'
        >>> format_featured_artists([])
        ''
    """
    if not featured_artists:
        return ""

    # Join with comma and space
    artists_str = ", ".join(featured_artists)

    return f"ft. {artists_str}"
