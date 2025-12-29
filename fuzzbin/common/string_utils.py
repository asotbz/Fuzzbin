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
    Handles both standalone and parenthetical notations.

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
        >>> remove_featured_artists("The Warrior (feat. Patty Smyth)")
        'The Warrior'
        >>> remove_featured_artists("No Featured Artists")
        'No Featured Artists'
    """
    # First, handle parenthetical featured artists: (feat. X), (ft. X), etc.
    # This removes the entire parenthetical including the parentheses
    parenthetical_pattern = r"\s*\((?:ft\.?|feat\.?|featuring|f/)[^)]*\)"
    result = re.sub(parenthetical_pattern, "", text, flags=re.IGNORECASE)

    # Then handle standalone featured artists: "ft. X", "feat. X", etc.
    # Pattern matches: ft., ft, feat., feat, featuring, f/
    # Use word boundaries for ft/feat variants, but not for f/ which uses /
    # Handle both mid-string and start-of-string cases
    standalone_pattern = r"(?:^|\s+)(?:ft\.?|feat\.?|featuring|f/)(?:\s+.*)?$"
    result = re.sub(standalone_pattern, "", result, flags=re.IGNORECASE)

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


def remove_version_qualifiers(text: str) -> str:
    """
    Remove version/edition qualifiers from track or album titles.

    Removes common qualifiers that Spotify adds to remastered/deluxe/special editions:
    - Parenthetical: (Remastered), (Deluxe Edition), (Anniversary Edition), etc.
    - Hyphenated: - 2015 Remaster, - From "Movie" Soundtrack, - Radio Edit, etc.
    - Bracketed: [Remastered], [Deluxe Edition], etc.

    Handles edge cases:
    - Preserves titles that START with parentheses (e.g., "(What's the Story) Morning Glory?")
    - Removes multiple qualifiers in sequence
    - Handles nested parentheses in soundtrack references

    Args:
        text: Title with potential version qualifiers

    Returns:
        Title with qualifiers removed and whitespace trimmed

    Example:
        >>> remove_version_qualifiers("Jump - 2015 Remaster")
        'Jump'
        >>> remove_version_qualifiers("1984 (Remastered)")
        '1984'
        >>> remove_version_qualifiers("Footloose (15th Anniversary Collectors' Edition)")
        'Footloose'
        >>> remove_version_qualifiers("Heartbeat City (Expanded Edition)")
        'Heartbeat City'
        >>> remove_version_qualifiers("Footloose - From \"Footloose\" Soundtrack")
        'Footloose'
        >>> remove_version_qualifiers("(What's the Story) Morning Glory?")
        "(What's the Story) Morning Glory?"
    """
    result = text.strip()
    
    # Don't process titles that start with parentheses (they're part of the actual title)
    if result.startswith("("):
        return result
    
    # Pattern for parenthetical qualifiers (must appear at end of string)
    # Matches: (Remastered), (Deluxe Edition), (2015 Remaster), etc.
    parenthetical_pattern = re.compile(
        r"\s*\([^)]*(?:"
        r"remaster(?:ed)?|deluxe|anniversary|expanded|edition|version|mix|edit|"
        r"live|acoustic|radio|single|album|explicit|clean|instrumental|karaoke|demo|bonus|"
        r"collector'?s?|limited|\d{4}\s*remaster"
        r")\b[^)]*\)\s*$",
        re.IGNORECASE,
    )
    
    # Pattern for hyphenated qualifiers (must appear at end of string)
    # Matches: - 2015 Remaster, - From "Movie" Soundtrack, - Radio Edit, etc.
    hyphenated_pattern = re.compile(
        r"\s*-\s*(?:"
        r"\d{4}\s*remaster(?:ed)?|"
        r"remaster(?:ed)?|"
        r"from\s+[\"'][^\"']*[\"'](?:\s+(?:soundtrack|ost))?|"
        r"radio\s+edit|"
        r"single\s+version|"
        r"album\s+version|"
        r"live|"
        r"acoustic|"
        r"explicit|"
        r"clean|"
        r"instrumental"
        r")\s*$",
        re.IGNORECASE,
    )
    
    # Pattern for bracketed qualifiers (less common, but some labels use them)
    # Matches: [Remastered], [Deluxe Edition], etc.
    bracketed_pattern = re.compile(
        r"\s*\[[^\]]*(?:"
        r"remaster(?:ed)?|deluxe|anniversary|expanded|edition|version"
        r")\b[^\]]*\]\s*$",
        re.IGNORECASE,
    )
    
    # Apply patterns repeatedly until no more matches
    # (handles cases with multiple qualifiers like "Song (Deluxe) - Remastered")
    max_iterations = 5  # Safety limit
    for _ in range(max_iterations):
        original = result
        result = parenthetical_pattern.sub("", result).strip()
        result = hyphenated_pattern.sub("", result).strip()
        result = bracketed_pattern.sub("", result).strip()
        
        # Stop if no changes were made
        if result == original:
            break
    
    return result


def normalize_spotify_title(
    text: str,
    remove_version_qualifiers_flag: bool = True,
    remove_featured: bool = False,
) -> str:
    """
    Normalize Spotify track or album titles for matching purposes.

    Combines multiple normalization steps:
    1. Remove version qualifiers (Remastered, Deluxe Edition, etc.)
    2. Remove featured artist notation (ft., feat., etc.)
    3. Convert to lowercase and strip whitespace

    This is the recommended function for normalizing Spotify metadata before
    IMVDb searches or duplicate detection.

    Args:
        text: Track or album title from Spotify
        remove_version_qualifiers_flag: Remove edition/version suffixes (default: True)
        remove_featured: Remove featured artist notation (default: False, use True for tracks)

    Returns:
        Normalized title suitable for matching operations

    Example:
        >>> normalize_spotify_title("Jump - 2015 Remaster")
        'jump'
        >>> normalize_spotify_title("Footloose - From \"Footloose\" Soundtrack")
        'footloose'
        >>> normalize_spotify_title("1984 (Remastered)")
        '1984'
        >>> normalize_spotify_title("Blurred Lines ft. T.I.", remove_featured=True)
        'blurred lines'
        >>> normalize_spotify_title("Artist ft. Other (Deluxe)", remove_version_qualifiers_flag=True, remove_featured=True)
        'artist'
    """
    result = text
    
    # Step 1: Remove version qualifiers (if enabled)
    if remove_version_qualifiers_flag:
        result = remove_version_qualifiers(result)
    
    # Step 2: Remove featured artists (if enabled)
    if remove_featured:
        result = remove_featured_artists(result)
    
    # Step 3: Normalize to lowercase and strip
    result = normalize_string(result)
    
    return result


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
    normalized = unicodedata.normalize("NFKD", text)

    # Remove combining characters (accents)
    # Category 'Mn' = Nonspacing_Mark (combining diacriticals)
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")

    # Convert to lowercase
    normalized = normalized.lower()

    # Remove hyphens
    normalized = normalized.replace("-", "")

    # Remove special characters (keep alphanumeric and spaces)
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)

    # Replace spaces with underscores
    normalized = normalized.replace(" ", "_")

    # Condense multiple underscores to single
    normalized = re.sub(r"_+", "_", normalized)

    # Strip leading/trailing underscores
    normalized = normalized.strip("_")

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
