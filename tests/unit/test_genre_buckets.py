"""Unit tests for genre bucket classification."""

import pytest

from fuzzbin.common.genre_buckets import (
    BUCKET_PATTERNS,
    PRIORITY,
    VALID_BUCKETS,
    classify_genres,
    classify_single_genre,
)


class TestClassifyGenres:
    """Test classify_genres function."""

    def test_empty_list_returns_none(self):
        """Empty genre list should return None bucket."""
        bucket, genres = classify_genres([])
        assert bucket is None
        assert genres == []

    def test_none_input_returns_none(self):
        """None input should return None bucket and empty list."""
        bucket, genres = classify_genres(None)
        assert bucket is None
        assert genres == []

    def test_rock_classification(self):
        """Rock genres should classify to Rock bucket."""
        test_cases = [
            ["rock"],
            ["alternative rock"],
            ["indie rock"],
            ["grunge"],
            ["punk"],
            ["post-punk"],
            ["shoegaze"],
            ["progressive rock"],
            ["prog rock"],
            ["emo"],
            ["hard rock"],
            ["psychedelic rock"],
            ["garage rock"],
        ]
        for genres in test_cases:
            bucket, returned_genres = classify_genres(genres)
            assert bucket == "Rock", f"Expected 'Rock' for {genres}, got '{bucket}'"
            assert returned_genres == genres

    def test_metal_classification(self):
        """Metal genres should classify to Metal bucket."""
        test_cases = [
            ["metal"],
            ["heavy metal"],
            ["death metal"],
            ["black metal"],
            ["thrash metal"],
            ["doom metal"],
            ["power metal"],
            ["nu metal"],
            ["metalcore"],
            ["deathcore"],
            ["sludge metal"],
            ["stoner metal"],
        ]
        for genres in test_cases:
            bucket, _ = classify_genres(genres)
            assert bucket == "Metal", f"Expected 'Metal' for {genres}, got '{bucket}'"

    def test_hip_hop_rnb_classification(self):
        """Hip Hop/R&B genres should classify correctly."""
        test_cases = [
            ["hip hop"],
            ["hip-hop"],
            ["rap"],
            ["trap"],
            ["r&b"],
            ["rnb"],
            ["soul"],
            ["neo soul"],
            ["g-funk"],
            ["boom bap"],
            ["drill"],
            ["grime"],
            ["crunk"],
        ]
        for genres in test_cases:
            bucket, _ = classify_genres(genres)
            assert bucket == "Hip Hop/R&B", f"Expected 'Hip Hop/R&B' for {genres}, got '{bucket}'"

    def test_country_classification(self):
        """Country genres should classify to Country bucket."""
        test_cases = [
            ["country"],
            ["country rock"],
            ["americana"],
            ["bluegrass"],
            ["outlaw country"],
            ["alt-country"],
            ["honky tonk"],
            ["nashville sound"],
            ["texas country"],
        ]
        for genres in test_cases:
            bucket, _ = classify_genres(genres)
            assert bucket == "Country", f"Expected 'Country' for {genres}, got '{bucket}'"

    def test_pop_classification(self):
        """Pop genres should classify to Pop bucket."""
        test_cases = [
            ["pop"],
            ["pop rock"],
            ["dance pop"],
            ["electropop"],
            ["synth pop"],
            ["indie pop"],
            ["k-pop"],
            ["j-pop"],
            ["teen pop"],
            ["chamber pop"],
            ["power pop"],
            ["art pop"],
            ["hyperpop"],
        ]
        for genres in test_cases:
            bucket, _ = classify_genres(genres)
            assert bucket == "Pop", f"Expected 'Pop' for {genres}, got '{bucket}'"

    def test_electronic_classification(self):
        """Electronic genres should classify to Electronic bucket."""
        test_cases = [
            ["electronic"],
            ["edm"],
            ["house"],
            ["techno"],
            ["trance"],
            ["dubstep"],
            ["drum & bass"],
            ["dnb"],
            ["jungle"],
            ["ambient"],
            ["idm"],
            ["trip hop"],
            ["disco"],
            ["uk garage"],
            ["2-step"],
            ["deep house"],
            ["progressive house"],
            ["hardstyle"],
            ["synthwave"],
            ["vaporwave"],
            ["future bass"],
            ["downtempo"],
            ["chillwave"],
        ]
        for genres in test_cases:
            bucket, _ = classify_genres(genres)
            assert bucket == "Electronic", f"Expected 'Electronic' for {genres}, got '{bucket}'"

    def test_priority_metal_over_rock(self):
        """Metal should win over Rock in mixed genres (priority order)."""
        # "alternative metal" matches both Metal and Rock (via "alternative")
        bucket, _ = classify_genres(["alternative metal"])
        assert bucket == "Metal"

        # Multiple genres where Metal appears
        bucket, _ = classify_genres(["hard rock", "heavy metal"])
        # Both have 1 match each, Metal wins by priority
        assert bucket == "Metal"

    def test_priority_hip_hop_over_rock(self):
        """Hip Hop/R&B should win over Rock in mixed genres."""
        bucket, _ = classify_genres(["rap rock"])
        # "rap" matches Hip Hop/R&B, "rock" matches Rock
        # Hip Hop/R&B is higher priority
        assert bucket == "Hip Hop/R&B"

    def test_priority_pop_over_electronic(self):
        """Pop should win over Electronic for genres like electropop."""
        bucket, _ = classify_genres(["electropop"])
        # Matches Pop via "electropop" pattern, but might also match Electronic
        # Pop is higher priority than Electronic
        assert bucket == "Pop"

    def test_frequency_matters(self):
        """Bucket with most matches should win (before priority tie-break)."""
        # 3 Rock genres vs 1 Metal genre
        bucket, _ = classify_genres(["rock", "alternative", "indie", "metal"])
        assert bucket == "Rock"

        # 2 Metal vs 1 Rock - Metal wins by count
        bucket, _ = classify_genres(["thrash metal", "death metal", "rock"])
        assert bucket == "Metal"

    def test_garage_rock_vs_uk_garage(self):
        """garage rock should be Rock, uk garage should be Electronic."""
        bucket, _ = classify_genres(["garage rock"])
        assert bucket == "Rock"

        bucket, _ = classify_genres(["uk garage"])
        assert bucket == "Electronic"

        # Plain "garage" is ambiguous - depends on other context
        # With rock context, should be Rock
        bucket, _ = classify_genres(["garage", "rock"])
        assert bucket == "Rock"

    def test_case_insensitive(self):
        """Classification should be case-insensitive."""
        bucket1, _ = classify_genres(["METAL"])
        bucket2, _ = classify_genres(["metal"])
        bucket3, _ = classify_genres(["Metal"])
        assert bucket1 == bucket2 == bucket3 == "Metal"

        bucket1, _ = classify_genres(["HIP HOP"])
        bucket2, _ = classify_genres(["hip hop"])
        assert bucket1 == bucket2 == "Hip Hop/R&B"

    def test_unmatched_genres_return_none(self):
        """Genres not matching any pattern should return None bucket."""
        bucket, genres = classify_genres(["jazz", "classical", "world music"])
        assert bucket is None
        assert genres == ["jazz", "classical", "world music"]

    def test_original_genres_preserved(self):
        """Original genres list should be returned unchanged."""
        original = ["Prog Rock", "Art Rock", "Progressive"]
        bucket, returned = classify_genres(original)
        assert returned is original  # Same object
        assert returned == ["Prog Rock", "Art Rock", "Progressive"]


class TestClassifySingleGenre:
    """Test classify_single_genre function."""

    def test_none_input(self):
        """None input should return (None, None)."""
        bucket, genre = classify_single_genre(None)
        assert bucket is None
        assert genre is None

    def test_empty_string(self):
        """Empty string should return (None, None)."""
        bucket, genre = classify_single_genre("")
        assert bucket is None
        assert genre is None

    def test_single_rock_genre(self):
        """Single rock genre should classify correctly."""
        bucket, genre = classify_single_genre("alternative rock")
        assert bucket == "Rock"
        assert genre == "alternative rock"

    def test_single_metal_genre(self):
        """Single metal genre should classify correctly."""
        bucket, genre = classify_single_genre("death metal")
        assert bucket == "Metal"
        assert genre == "death metal"

    def test_unmatched_genre(self):
        """Unmatched genre should return None bucket with original."""
        bucket, genre = classify_single_genre("jazz fusion")
        assert bucket is None
        assert genre == "jazz fusion"


class TestBucketPatterns:
    """Test bucket patterns structure."""

    def test_all_priority_buckets_have_patterns(self):
        """Every bucket in PRIORITY should have patterns defined."""
        for bucket in PRIORITY:
            assert bucket in BUCKET_PATTERNS
            assert len(BUCKET_PATTERNS[bucket]) > 0

    def test_valid_buckets_matches_priority(self):
        """VALID_BUCKETS should match PRIORITY list."""
        assert VALID_BUCKETS == frozenset(PRIORITY)

    def test_priority_order(self):
        """Priority order should be Metal, Hip Hop/R&B, Country, Pop, Electronic, Rock."""
        expected = ["Metal", "Hip Hop/R&B", "Country", "Pop", "Electronic", "Rock"]
        assert PRIORITY == expected


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_whitespace_in_genres(self):
        """Genres with extra whitespace should still match."""
        bucket, _ = classify_genres(["  rock  "])
        # The regex uses word boundaries, so this should still match
        assert bucket == "Rock"

    def test_hyphenated_variants(self):
        """Test hyphenated and non-hyphenated variants."""
        # post-punk and post punk
        bucket1, _ = classify_genres(["post-punk"])
        bucket2, _ = classify_genres(["post punk"])
        assert bucket1 == bucket2 == "Rock"

        # alt-country
        bucket, _ = classify_genres(["alt-country"])
        assert bucket == "Country"

    def test_compound_genres(self):
        """Test compound genre names."""
        bucket, _ = classify_genres(["drum and bass"])
        assert bucket == "Electronic"

        bucket, _ = classify_genres(["drum & bass"])
        assert bucket == "Electronic"

    def test_subgenre_specificity(self):
        """More specific subgenres should still classify to parent bucket."""
        bucket, _ = classify_genres(["melodic death metal"])
        assert bucket == "Metal"

        bucket, _ = classify_genres(["symphonic power metal"])
        assert bucket == "Metal"

        bucket, _ = classify_genres(["progressive trance"])
        assert bucket == "Electronic"

    def test_mixed_matched_and_unmatched(self):
        """Mix of matched and unmatched genres should use matched ones."""
        bucket, _ = classify_genres(["jazz", "fusion", "rock"])
        # Only "rock" matches, so should be Rock
        assert bucket == "Rock"

        bucket, _ = classify_genres(["world music", "afrobeat", "hip hop"])
        # Only "hip hop" matches
        assert bucket == "Hip Hop/R&B"
