"""Tests for string normalization utilities."""

import pytest

from fuzzbin.common.string_utils import (
    normalize_string,
    remove_featured_artists,
    normalize_for_matching,
)


class TestNormalizeString:
    """Tests for normalize_string function."""

    def test_lowercase_conversion(self):
        """Test that strings are converted to lowercase."""
        assert normalize_string("HELLO WORLD") == "hello world"
        assert normalize_string("MiXeD CaSe") == "mixed case"

    def test_whitespace_stripping(self):
        """Test that leading/trailing whitespace is removed."""
        assert normalize_string("  hello  ") == "hello"
        assert normalize_string("\t\ntest\n\t") == "test"
        assert normalize_string("   spaced   ") == "spaced"

    def test_combined_normalization(self):
        """Test lowercase and strip combined."""
        assert normalize_string("  HELLO WORLD  ") == "hello world"
        assert normalize_string("\t\nMiXeD CaSe\n") == "mixed case"

    def test_already_normalized(self):
        """Test that already normalized strings pass through."""
        assert normalize_string("hello world") == "hello world"
        assert normalize_string("test") == "test"

    def test_empty_string(self):
        """Test handling of empty string."""
        assert normalize_string("") == ""
        assert normalize_string("   ") == ""


class TestRemoveFeaturedArtists:
    """Tests for remove_featured_artists function."""

    def test_ft_with_period(self):
        """Test removing 'ft.' pattern."""
        assert remove_featured_artists("Robin Thicke ft. T.I.") == "Robin Thicke"
        assert remove_featured_artists("Artist ft. Other") == "Artist"

    def test_ft_without_period(self):
        """Test removing 'ft' pattern without period."""
        assert remove_featured_artists("Robin Thicke ft T.I.") == "Robin Thicke"
        assert remove_featured_artists("Artist ft Other") == "Artist"

    def test_feat_with_period(self):
        """Test removing 'feat.' pattern."""
        assert remove_featured_artists("Artist feat. Featured") == "Artist"
        assert remove_featured_artists("Song feat. Guest") == "Song"

    def test_feat_without_period(self):
        """Test removing 'feat' pattern without period."""
        assert remove_featured_artists("Artist feat Featured") == "Artist"
        assert remove_featured_artists("Song feat Guest") == "Song"

    def test_featuring(self):
        """Test removing 'featuring' pattern."""
        assert remove_featured_artists("Artist featuring Other") == "Artist"
        assert remove_featured_artists("Song featuring Guest Artist") == "Song"

    def test_f_slash(self):
        """Test removing 'f/' pattern."""
        assert remove_featured_artists("Artist f/ Other") == "Artist"
        assert remove_featured_artists("Song f/ Featured") == "Song"

    def test_case_insensitive(self):
        """Test that patterns are case-insensitive."""
        assert remove_featured_artists("Artist FT. Other") == "Artist"
        assert remove_featured_artists("Song Ft Other") == "Song"
        assert remove_featured_artists("Artist FEAT. Other") == "Artist"
        assert remove_featured_artists("Song Featuring Other") == "Song"
        assert remove_featured_artists("Artist F/ Other") == "Artist"

    def test_multiple_featured_artists(self):
        """Test removing multiple featured artists."""
        assert remove_featured_artists("Artist ft. Other & Another") == "Artist"
        assert remove_featured_artists("Song feat. A, B, and C") == "Song"

    def test_no_featured_artists(self):
        """Test strings without featured artist notation."""
        assert remove_featured_artists("Robin Thicke") == "Robin Thicke"
        assert remove_featured_artists("Blurred Lines") == "Blurred Lines"
        assert remove_featured_artists("No Features Here") == "No Features Here"

    def test_featured_in_middle_not_removed(self):
        """Test that 'ft' or 'feat' not at word boundary is not removed."""
        # These should not be affected as they're part of words
        assert remove_featured_artists("Fifty Shades") == "Fifty Shades"
        assert remove_featured_artists("Software Testing") == "Software Testing"

    def test_trailing_whitespace_removed(self):
        """Test that trailing whitespace after removal is cleaned up."""
        result = remove_featured_artists("Artist ft. Other")
        assert result == "Artist"
        assert not result.endswith(" ")

    def test_empty_string(self):
        """Test handling of empty string."""
        assert remove_featured_artists("") == ""

    def test_only_featured_text(self):
        """Test string that is only featured artist text."""
        assert remove_featured_artists("ft. Someone") == ""
        assert remove_featured_artists("featuring Artist") == ""


class TestNormalizeForMatching:
    """Tests for normalize_for_matching function."""

    def test_default_removes_featured(self):
        """Test that featured artists are removed by default."""
        result = normalize_for_matching("Robin Thicke ft. T.I.")
        assert result == "robin thicke"

    def test_lowercase_and_strip(self):
        """Test lowercase and strip combined."""
        result = normalize_for_matching("  HELLO WORLD  ")
        assert result == "hello world"

    def test_combined_normalization(self):
        """Test full normalization with featured artist removal."""
        result = normalize_for_matching("  Robin Thicke FT. T.I.  ")
        assert result == "robin thicke"

    def test_remove_featured_false(self):
        """Test that featured artists are kept when remove_featured=False."""
        result = normalize_for_matching("Artist ft. Other", remove_featured=False)
        assert result == "artist ft. other"

    def test_no_featured_artists(self):
        """Test string without featured artists."""
        result = normalize_for_matching("Robin Thicke")
        assert result == "robin thicke"

    def test_complex_case(self):
        """Test complex case with mixed elements."""
        result = normalize_for_matching("  ROBIN THICKE feat. T.I. & Pharrell  ")
        assert result == "robin thicke"

    def test_empty_string(self):
        """Test handling of empty string."""
        assert normalize_for_matching("") == ""

    def test_song_title_with_featured(self):
        """Test song titles that include featured artists."""
        result = normalize_for_matching("Blurred Lines ft. T.I.")
        assert result == "blurred lines"

    def test_preserve_featured_when_disabled(self):
        """Test that featured text is preserved when removal disabled."""
        result = normalize_for_matching(
            "Artist featuring Other", remove_featured=False
        )
        assert result == "artist featuring other"
