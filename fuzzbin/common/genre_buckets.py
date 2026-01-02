"""
Genre bucket classification for mapping specific genres to broad categories.

This module provides regex-based genre classification that maps detailed genre
strings (e.g., from Spotify or Discogs) to one of six broad buckets:
Metal, Hip Hop/R&B, Country, Pop, Electronic, Rock.

The classification uses pattern matching with priority-based tie-breaking
for genres that could match multiple buckets (e.g., "electropop" matches
both Pop and Electronic, but Pop wins due to priority).

Example:
    >>> from fuzzbin.common.genre_buckets import classify_genres
    >>> bucket, original = classify_genres(["prog rock", "grunge"])
    >>> print(bucket)  # "Rock"
    >>> print(original)  # ["prog rock", "grunge"]
"""

import re
from typing import List, Optional, Tuple

# Regex patterns for each genre bucket
# Patterns use word boundaries (\b) to avoid partial matches
BUCKET_PATTERNS = {
    "Metal": [
        r"\bmetal\b",
        r"\bdoom\b",
        r"\bsludge\b",
        r"\bstoner\b",
        r"\bthrash\b",
        r"\bdeath\b",
        r"\bblack\b",
        r"\bgrind\b",
        r"\bmetalcore\b",
        r"\bdeathcore\b",
        r"\bnu\s*metal\b",
        r"\bpower\s*metal\b",
        r"\bheavy\s*metal\b",
    ],
    "Hip Hop/R&B": [
        r"\bhip[\s-]?hop\b",
        r"\brap\b",
        r"\btrap\b",
        r"\bdrill\b",
        r"\bgrime\b",
        r"\br&b\b",
        r"\brnb\b",
        r"\bsoul\b",
        r"\bneo[\s-]?soul\b",
        r"\bnew\s*jack\b",
        r"\bg[-\s]?funk\b",
        r"\bcrunk\b",
        r"\bboom\s*bap\b",
    ],
    "Country": [
        r"\bcountry\b",
        r"\boutlaw\b",
        r"\bbluegrass\b",
        r"\bamericana\b",
        r"\bhonky\s*tonk\b",
        r"\bnashville\b",
        r"\balt[-\s]?country\b",
        r"\btexas\s*country\b",
        r"\bwestern\b",
        r"\bfolk\s*country\b",
    ],
    "Pop": [
        r"\bpop\b",
        r"\bdance\s*pop\b",
        r"\bteen\s*pop\b",
        r"\bpop\s*rock\b",
        r"\belectropop\b",
        r"\bsynth\s*pop\b",
        r"\bindie\s*pop\b",
        r"\bk[-\s]?pop\b",
        r"\bj[-\s]?pop\b",
        r"\bchamber\s*pop\b",
        r"\bpower\s*pop\b",
        r"\bart\s*pop\b",
        r"\bhyperpop\b",
    ],
    "Electronic": [
        r"\belectronic\b",
        r"\bedm\b",
        r"\bhouse\b",
        r"\btechno\b",
        r"\btrance\b",
        r"\bdubstep\b",
        r"\bdrum\s*(?:&|and)?\s*bass\b|\bdnb\b",
        r"\bjungle\b",
        r"\bambient\b",
        r"\bidm\b",
        r"\bbreakbeat\b",
        r"\btrip[\s-]?hop\b",
        r"\bdisco\b",
        # UK garage-specific (avoid ambiguity with "garage rock")
        r"\buk\s*garage\b|\b2[-\s]?step\b|\bbassline\b",
        r"\bdeep\s*house\b",
        r"\bprogressive\s*house\b",
        r"\bhardstyle\b",
        r"\bsynthwave\b|\bvaporwave\b|\bfuture\s*bass\b",
        r"\bdowntempo\b|\bchillwave\b",
    ],
    "Rock": [
        r"\brock\b",
        r"\balternative\b",
        r"\bindie\b",
        r"\bgrunge\b",
        r"\bemo\b",
        r"\bhard\s*rock\b",
        r"\bpsychedelic\b",
        r"\bpost[-\s]?punk\b",
        r"\bpunk\b",
        r"\bshoegaze\b",
        r"\bclassic\b",
        r"\bprog(ressive)?\b",
        r"\bart\s*rock\b",
        r"\bgarage\s*rock\b",
    ],
}

# Priority order for tie-breaking when a genre matches multiple buckets
# - Pop before Electronic means electropop/synth-pop tends to bucket as Pop
# - Metal first means "alternative metal" → Metal, not Rock
PRIORITY = ["Metal", "Hip Hop/R&B", "Country", "Pop", "Electronic", "Rock"]

# Pre-compile all patterns for performance
_COMPILED_PATTERNS = {
    bucket: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for bucket, patterns in BUCKET_PATTERNS.items()
}


def _match_bucket(genre: str) -> Optional[str]:
    """
    Match a single genre string against bucket patterns.

    Args:
        genre: A genre string to classify

    Returns:
        The matching bucket name, or None if no match
    """
    matched_buckets = []

    for bucket in PRIORITY:
        patterns = _COMPILED_PATTERNS[bucket]
        for pattern in patterns:
            if pattern.search(genre):
                matched_buckets.append(bucket)
                break  # One match per bucket is enough

    if not matched_buckets:
        return None

    # Return highest priority bucket
    for bucket in PRIORITY:
        if bucket in matched_buckets:
            return bucket

    return None


def classify_genres(genres: Optional[List[str]]) -> Tuple[Optional[str], List[str]]:
    """
    Classify a list of genres into a broad bucket category.

    Takes a list of specific genre strings and returns the most appropriate
    broad bucket based on frequency of matches and priority ordering.

    Args:
        genres: List of genre strings (e.g., from Spotify artist data).
            Can be None or empty.

    Returns:
        Tuple of (bucket, original_genres) where:
        - bucket: The broad category ("Metal", "Hip Hop/R&B", "Country",
            "Pop", "Electronic", "Rock") or None if no match
        - original_genres: The input list (or empty list if None provided)

    Example:
        >>> classify_genres(["prog rock", "grunge"])
        ('Rock', ['prog rock', 'grunge'])

        >>> classify_genres(["alternative metal", "hard rock"])
        ('Metal', ['alternative metal', 'hard rock'])

        >>> classify_genres(["electropop", "dance pop"])
        ('Pop', ['electropop', 'dance pop'])

        >>> classify_genres([])
        (None, [])

        >>> classify_genres(None)
        (None, [])
    """
    if not genres:
        return (None, [])

    # Count matches for each bucket across all genres
    bucket_counts: dict[str, int] = {bucket: 0 for bucket in PRIORITY}

    for genre in genres:
        matched_bucket = _match_bucket(genre)
        if matched_bucket:
            bucket_counts[matched_bucket] += 1

    # Find bucket(s) with maximum matches
    max_count = max(bucket_counts.values())
    if max_count == 0:
        return (None, genres)

    # Use priority order as tie-breaker
    for bucket in PRIORITY:
        if bucket_counts[bucket] == max_count:
            return (bucket, genres)

    return (None, genres)


def classify_single_genre(genre: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Classify a single genre string into a broad bucket category.

    Convenience wrapper around classify_genres for single-genre input.

    Args:
        genre: A single genre string, or None

    Returns:
        Tuple of (bucket, original_genre) where:
        - bucket: The broad category or None if no match
        - original_genre: The input string (or None if None provided)

    Example:
        >>> classify_single_genre("alternative rock")
        ('Rock', 'alternative rock')

        >>> classify_single_genre("death metal")
        ('Metal', 'death metal')

        >>> classify_single_genre(None)
        (None, None)
    """
    if not genre:
        return (None, None)

    bucket = _match_bucket(genre)
    return (bucket, genre)


# Valid bucket names for validation
VALID_BUCKETS = frozenset(PRIORITY)
