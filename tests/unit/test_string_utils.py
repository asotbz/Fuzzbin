"""Tests for string normalization utilities."""

import pytest

from fuzzbin.common.string_utils import (
    normalize_string,
    remove_featured_artists,
    normalize_for_matching,
    normalize_filename,
    format_featured_artists,
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


class TestNormalizeFilename:
    """Tests for normalize_filename function."""

    def test_diacritics_removed(self):
        """Test diacritic normalization."""
        assert normalize_filename("Björk") == "bjork"
        assert normalize_filename("Café") == "cafe"
        assert normalize_filename("Señor") == "senor"
        assert normalize_filename("Naïve") == "naive"
        assert normalize_filename("Zürich") == "zurich"

    def test_lowercase_conversion(self):
        """Test conversion to lowercase."""
        assert normalize_filename("UPPERCASE") == "uppercase"
        assert normalize_filename("MixedCase") == "mixedcase"
        assert normalize_filename("CamelCase") == "camelcase"

    def test_special_chars_removed(self):
        """Test special character removal."""
        assert normalize_filename("AC/DC") == "acdc"
        assert normalize_filename("Artist (Remix)") == "artist_remix"
        assert normalize_filename("Song!@#$%") == "song"
        assert normalize_filename("Test*File?Name") == "testfilename"

    def test_hyphens_removed(self):
        """Test hyphen removal."""
        assert normalize_filename("Test-Hyphen") == "testhyphen"
        assert normalize_filename("Multi-Word-Title") == "multiwordtitle"
        assert normalize_filename("One-Two-Three") == "onetwothree"

    def test_spaces_to_underscores(self):
        """Test space to underscore conversion."""
        assert normalize_filename("Multiple Words") == "multiple_words"
        assert normalize_filename("A B C") == "a_b_c"
        assert normalize_filename("Test Title") == "test_title"

    def test_multiple_underscores_condensed(self):
        """Test multiple underscores condensed to single."""
        assert normalize_filename("Too   Many   Spaces") == "too_many_spaces"
        assert normalize_filename("Test    Title") == "test_title"

    def test_leading_trailing_underscores_stripped(self):
        """Test leading/trailing underscores removed."""
        assert normalize_filename("  Leading Trailing  ") == "leading_trailing"
        assert normalize_filename("   Spaces   ") == "spaces"

    def test_combined_transformations(self):
        """Test combination of all transformations."""
        assert normalize_filename("Björk - Humúríús") == "bjork_humurius"
        assert normalize_filename("AC/DC - Back In Black") == "acdc_back_in_black"
        assert normalize_filename("Tëst (Remix) - 2020") == "test_remix_2020"

    def test_numbers_preserved(self):
        """Test that numbers are preserved."""
        assert normalize_filename("Track 01") == "track_01"
        assert normalize_filename("2020 Album") == "2020_album"
        assert normalize_filename("Mix123") == "mix123"

    def test_empty_result_from_special_chars_only(self):
        """Test that strings with only special chars result in empty string."""
        assert normalize_filename("!!!") == ""
        assert normalize_filename("@#$%") == ""
        assert normalize_filename("---") == ""

    def test_unicode_characters(self):
        """Test various unicode characters."""
        assert normalize_filename("Tëst Ñame") == "test_name"
        assert normalize_filename("Ärger Über Ümlaute") == "arger_uber_umlaute"

    def test_mixed_case_with_special_chars(self):
        """Test mixed case with special characters."""
        assert normalize_filename("Test-File_Name (v2)") == "testfilename_v2"
        assert normalize_filename("My Song! (2020)") == "my_song_2020"


class TestFormatFeaturedArtists:
    """Tests for format_featured_artists function."""

    def test_single_artist(self):
        """Test formatting with single featured artist."""
        result = format_featured_artists(["Drake"])
        assert result == "ft. Drake"

    def test_two_artists(self):
        """Test formatting with two featured artists."""
        result = format_featured_artists(["T.I.", "Pharrell Williams"])
        assert result == "ft. T.I., Pharrell Williams"

    def test_multiple_artists(self):
        """Test formatting with multiple featured artists."""
        result = format_featured_artists(["Artist 1", "Artist 2", "Artist 3"])
        assert result == "ft. Artist 1, Artist 2, Artist 3"

    def test_empty_list(self):
        """Test that empty list returns empty string."""
        result = format_featured_artists([])
        assert result == ""

    def test_artist_with_periods(self):
        """Test artist names with periods are preserved."""
        result = format_featured_artists(["T.I.", "Dr. Dre"])
        assert result == "ft. T.I., Dr. Dre"

    def test_artist_with_special_chars(self):
        """Test artist names with special characters."""
        result = format_featured_artists(["Jay-Z", "Beyoncé"])
        assert result == "ft. Jay-Z, Beyoncé"

    def test_no_trailing_space(self):
        """Test that result has no trailing space."""
        result = format_featured_artists(["Artist"])
        assert not result.endswith(" ")
        assert result == "ft. Artist"

    def test_no_leading_space(self):
        """Test that result has correct leading format."""
        result = format_featured_artists(["Artist"])
        assert result.startswith("ft. ")

    def test_four_artists(self):
        """Test formatting with four featured artists."""
        result = format_featured_artists(["A", "B", "C", "D"])
        assert result == "ft. A, B, C, D"
