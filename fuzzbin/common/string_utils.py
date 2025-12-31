"""String normalization utilities for matching and comparison."""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple


# Primary genre mapping table
# Maps Discogs genres/styles to primary categories
# Unmapped genres pass through unchanged
PRIMARY_GENRE_MAP: Dict[str, str] = {
    # Rock variants
    "rock": "Rock",
    "alternative rock": "Rock",
    "indie rock": "Rock",
    "hard rock": "Rock",
    "soft rock": "Rock",
    "progressive rock": "Rock",
    "prog rock": "Rock",
    "classic rock": "Rock",
    "punk rock": "Rock",
    "punk": "Rock",
    "post-punk": "Rock",
    "new wave": "Rock",
    "grunge": "Rock",
    "garage rock": "Rock",
    "psychedelic rock": "Rock",
    "art rock": "Rock",
    "glam rock": "Rock",
    "blues rock": "Rock",
    "southern rock": "Rock",
    "roots rock": "Rock",
    "heartland rock": "Rock",
    "arena rock": "Rock",
    "power pop": "Rock",
    "britpop": "Rock",
    "shoegaze": "Rock",
    "emo": "Rock",
    "post-rock": "Rock",
    "stoner rock": "Rock",
    "noise rock": "Rock",
    # Pop variants
    "pop": "Pop",
    "pop rock": "Pop",
    "synth-pop": "Pop",
    "synthpop": "Pop",
    "electropop": "Pop",
    "dance-pop": "Pop",
    "teen pop": "Pop",
    "bubblegum": "Pop",
    "adult contemporary": "Pop",
    "soft pop": "Pop",
    "indie pop": "Pop",
    "chamber pop": "Pop",
    "dream pop": "Pop",
    "europop": "Pop",
    "k-pop": "Pop",
    "j-pop": "Pop",
    "latin pop": "Pop",
    # Hip Hop / R&B variants
    "hip hop": "Hip Hop/R&B",
    "hip-hop": "Hip Hop/R&B",
    "rap": "Hip Hop/R&B",
    "r&b": "Hip Hop/R&B",
    "rnb": "Hip Hop/R&B",
    "rhythm & blues": "Hip Hop/R&B",
    "rhythm and blues": "Hip Hop/R&B",
    "soul": "Hip Hop/R&B",
    "neo soul": "Hip Hop/R&B",
    "neo-soul": "Hip Hop/R&B",
    "funk": "Hip Hop/R&B",
    "contemporary r&b": "Hip Hop/R&B",
    "urban": "Hip Hop/R&B",
    "gangsta rap": "Hip Hop/R&B",
    "trap": "Hip Hop/R&B",
    "boom bap": "Hip Hop/R&B",
    "conscious hip hop": "Hip Hop/R&B",
    "alternative hip hop": "Hip Hop/R&B",
    "dirty south": "Hip Hop/R&B",
    "crunk": "Hip Hop/R&B",
    "g-funk": "Hip Hop/R&B",
    "new jack swing": "Hip Hop/R&B",
    "quiet storm": "Hip Hop/R&B",
    "motown": "Hip Hop/R&B",
    "disco": "Hip Hop/R&B",
    # Country variants
    "country": "Country",
    "country rock": "Country",
    "country pop": "Country",
    "alt-country": "Country",
    "alternative country": "Country",
    "americana": "Country",
    "bluegrass": "Country",
    "honky tonk": "Country",
    "outlaw country": "Country",
    "nashville sound": "Country",
    "bro-country": "Country",
    "country & western": "Country",
    "western": "Country",
    "folk rock": "Country",
    # Electronic variants
    "electronic": "Electronic",
    "electronica": "Electronic",
    "edm": "Electronic",
    "house": "Electronic",
    "deep house": "Electronic",
    "tech house": "Electronic",
    "progressive house": "Electronic",
    "techno": "Electronic",
    "trance": "Electronic",
    "drum and bass": "Electronic",
    "dnb": "Electronic",
    "dubstep": "Electronic",
    "ambient": "Electronic",
    "idm": "Electronic",
    "industrial": "Electronic",
    "ebm": "Electronic",
    "synthwave": "Electronic",
    "retrowave": "Electronic",
    "chillwave": "Electronic",
    "vaporwave": "Electronic",
    "downtempo": "Electronic",
    "trip hop": "Electronic",
    "trip-hop": "Electronic",
    "breakbeat": "Electronic",
    "big beat": "Electronic",
    "uk garage": "Electronic",
    "2-step": "Electronic",
    "grime": "Electronic",
    "future bass": "Electronic",
    # Metal variants
    "metal": "Metal",
    "heavy metal": "Metal",
    "thrash metal": "Metal",
    "death metal": "Metal",
    "black metal": "Metal",
    "doom metal": "Metal",
    "power metal": "Metal",
    "progressive metal": "Metal",
    "nu metal": "Metal",
    "nu-metal": "Metal",
    "metalcore": "Metal",
    "deathcore": "Metal",
    "symphonic metal": "Metal",
    "gothic metal": "Metal",
    "folk metal": "Metal",
    "speed metal": "Metal",
    "hair metal": "Metal",
    "glam metal": "Metal",
    "groove metal": "Metal",
    "sludge metal": "Metal",
    "post-metal": "Metal",
    "djent": "Metal",
    # Jazz variants
    "jazz": "Jazz",
    "smooth jazz": "Jazz",
    "jazz fusion": "Jazz",
    "fusion": "Jazz",
    "bebop": "Jazz",
    "hard bop": "Jazz",
    "cool jazz": "Jazz",
    "free jazz": "Jazz",
    "latin jazz": "Jazz",
    "acid jazz": "Jazz",
    "nu jazz": "Jazz",
    "swing": "Jazz",
    "big band": "Jazz",
    "vocal jazz": "Jazz",
    "contemporary jazz": "Jazz",
    # Classical variants
    "classical": "Classical",
    "baroque": "Classical",
    "romantic": "Classical",
    "modern classical": "Classical",
    "contemporary classical": "Classical",
    "orchestral": "Classical",
    "opera": "Classical",
    "choral": "Classical",
    "chamber music": "Classical",
    "symphony": "Classical",
    "concerto": "Classical",
    "minimalism": "Classical",
    "neo-classical": "Classical",
    "neoclassical": "Classical",
    # Folk variants
    "folk": "Folk",
    "traditional folk": "Folk",
    "contemporary folk": "Folk",
    "acoustic": "Folk",
    "singer-songwriter": "Folk",
    "singer/songwriter": "Folk",
    "world": "Folk",
    "world music": "Folk",
    "celtic": "Folk",
    "irish folk": "Folk",
    "british folk": "Folk",
    "appalachian": "Folk",
    "traditional": "Folk",
    "ethnic": "Folk",
    "roots": "Folk",
    # Reggae variants (map to Other for now, could be its own category)
    "reggae": "Other",
    "ska": "Other",
    "dub": "Other",
    "dancehall": "Other",
    "roots reggae": "Other",
    # Blues variants
    "blues": "Other",
    "delta blues": "Other",
    "chicago blues": "Other",
    "electric blues": "Other",
    "acoustic blues": "Other",
    # Latin variants
    "latin": "Other",
    "salsa": "Other",
    "merengue": "Other",
    "bachata": "Other",
    "reggaeton": "Other",
    "cumbia": "Other",
    "bossa nova": "Other",
    "samba": "Other",
    "tango": "Other",
    # Gospel/Religious
    "gospel": "Other",
    "christian": "Other",
    "christian rock": "Other",
    "ccm": "Other",
    "worship": "Other",
    # Soundtrack/Score
    "soundtrack": "Other",
    "score": "Other",
    "film score": "Other",
    "video game music": "Other",
    # Miscellaneous
    "experimental": "Other",
    "avant-garde": "Other",
    "spoken word": "Other",
    "comedy": "Other",
    "children's": "Other",
    "holiday": "Other",
    "christmas": "Other",
    "new age": "Other",
    "easy listening": "Other",
    "lounge": "Other",
    "exotica": "Other",
}


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


def normalize_genre(genre: str) -> Tuple[str, str, bool]:
    """
    Normalize a genre string to a primary category.

    Uses PRIMARY_GENRE_MAP to map Discogs genres/styles to one of the
    primary categories: Rock, Pop, Hip Hop/R&B, Country, Electronic,
    Jazz, Classical, Metal, Folk, Other.

    Unmapped genres pass through unchanged, preserving specificity.

    Args:
        genre: Genre string from Discogs or other source

    Returns:
        Tuple of (original, normalized, is_mapped) where:
        - original: The input genre string (stripped)
        - normalized: The primary category or original if unmapped
        - is_mapped: True if genre was found in mapping table

    Example:
        >>> normalize_genre("Alternative Rock")
        ('Alternative Rock', 'Rock', True)
        >>> normalize_genre("grunge")
        ('grunge', 'Rock', True)
        >>> normalize_genre("Afrobeat")
        ('Afrobeat', 'Afrobeat', False)
        >>> normalize_genre("  Hip Hop  ")
        ('Hip Hop', 'Hip Hop/R&B', True)
    """
    original = genre.strip()
    lookup_key = original.lower()

    if lookup_key in PRIMARY_GENRE_MAP:
        return (original, PRIMARY_GENRE_MAP[lookup_key], True)

    return (original, original, False)


def get_primary_genre_categories() -> List[str]:
    """
    Get the list of primary genre categories.

    Returns:
        List of primary genre category names in display order

    Example:
        >>> get_primary_genre_categories()
        ['Rock', 'Pop', 'Hip Hop/R&B', 'Country', 'Electronic', 'Jazz', 'Classical', 'Metal', 'Folk', 'Other']
    """
    return [
        "Rock",
        "Pop",
        "Hip Hop/R&B",
        "Country",
        "Electronic",
        "Jazz",
        "Classical",
        "Metal",
        "Folk",
        "Other",
    ]
