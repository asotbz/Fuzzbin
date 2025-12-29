"""Tests for string normalization utilities."""

import pytest

from fuzzbin.common.string_utils import (
    normalize_string,
    remove_featured_artists,
    normalize_for_matching,
    normalize_filename,
    format_featured_artists,
    remove_version_qualifiers,
    normalize_spotify_title,
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


class TestRemoveVersionQualifiers:
    """Tests for remove_version_qualifiers function."""

    def test_parenthetical_remastered(self):
        """Test removing (Remastered) qualifier."""
        assert remove_version_qualifiers("1984 (Remastered)") == "1984"
        assert remove_version_qualifiers("Nevermind (Remastered)") == "Nevermind"
        assert remove_version_qualifiers("Album (Remaster)") == "Album"

    def test_parenthetical_with_year(self):
        """Test removing remaster qualifiers with years."""
        assert remove_version_qualifiers("Jump (2015 Remaster)") == "Jump"
        assert remove_version_qualifiers("Song (1999 Remastered)") == "Song"
        assert remove_version_qualifiers("Track (2020 Remaster)") == "Track"

    def test_parenthetical_deluxe_edition(self):
        """Test removing deluxe edition qualifiers."""
        assert remove_version_qualifiers("Purple Rain (Deluxe)") == "Purple Rain"
        assert remove_version_qualifiers("Album (Deluxe Edition)") == "Album"
        assert remove_version_qualifiers("Songs (Deluxe Version)") == "Songs"

    def test_parenthetical_anniversary_edition(self):
        """Test removing anniversary edition qualifiers."""
        assert remove_version_qualifiers("Footloose (15th Anniversary Collectors' Edition)") == "Footloose"
        assert remove_version_qualifiers("Album (10th Anniversary Edition)") == "Album"
        assert remove_version_qualifiers("Songs (25th Anniversary)") == "Songs"

    def test_parenthetical_expanded_edition(self):
        """Test removing expanded edition qualifiers."""
        assert remove_version_qualifiers("Heartbeat City (Expanded Edition)") == "Heartbeat City"
        assert remove_version_qualifiers("Album (Expanded)") == "Album"

    def test_parenthetical_radio_edit(self):
        """Test removing radio edit qualifiers."""
        assert remove_version_qualifiers("Song (Radio Edit)") == "Song"
        assert remove_version_qualifiers("Track (Radio Version)") == "Track"
        assert remove_version_qualifiers("Single (Radio)") == "Single"

    def test_parenthetical_other_versions(self):
        """Test removing various version qualifiers."""
        assert remove_version_qualifiers("Track (Live)") == "Track"
        assert remove_version_qualifiers("Song (Acoustic)") == "Song"
        assert remove_version_qualifiers("Track (Explicit)") == "Track"
        assert remove_version_qualifiers("Song (Clean)") == "Song"
        assert remove_version_qualifiers("Track (Instrumental)") == "Track"
        assert remove_version_qualifiers("Song (Album Version)") == "Song"
        assert remove_version_qualifiers("Track (Single Version)") == "Track"

    def test_hyphenated_remaster(self):
        """Test removing hyphenated remaster qualifiers."""
        assert remove_version_qualifiers("Jump - 2015 Remaster") == "Jump"
        assert remove_version_qualifiers("Song - Remastered") == "Song"
        assert remove_version_qualifiers("Track - Remaster") == "Track"

    def test_hyphenated_soundtrack(self):
        """Test removing soundtrack qualifiers."""
        assert remove_version_qualifiers('Footloose - From "Footloose" Soundtrack') == "Footloose"
        assert remove_version_qualifiers("Song - From 'Movie' Soundtrack") == "Song"
        assert remove_version_qualifiers('Track - From "Film" OST') == "Track"

    def test_hyphenated_versions(self):
        """Test removing hyphenated version qualifiers."""
        assert remove_version_qualifiers("Song - Radio Edit") == "Song"
        assert remove_version_qualifiers("Track - Single Version") == "Track"
        assert remove_version_qualifiers("Song - Album Version") == "Song"
        assert remove_version_qualifiers("Track - Live") == "Track"
        assert remove_version_qualifiers("Song - Acoustic") == "Song"

    def test_bracketed_qualifiers(self):
        """Test removing bracketed qualifiers."""
        assert remove_version_qualifiers("Album [Remastered]") == "Album"
        assert remove_version_qualifiers("Song [Deluxe Edition]") == "Song"
        assert remove_version_qualifiers("Track [Expanded]") == "Track"

    def test_multiple_qualifiers(self):
        """Test removing multiple qualifiers in sequence."""
        assert remove_version_qualifiers("Song (Deluxe Edition) - Remastered") == "Song"
        assert remove_version_qualifiers("Track (Expanded) (Remastered)") == "Track"
        assert remove_version_qualifiers("Album - Remaster [Deluxe]") == "Album"

    def test_preserve_title_starting_with_paren(self):
        """Test that titles starting with parentheses are preserved."""
        result = remove_version_qualifiers("(What's the Story) Morning Glory?")
        assert result == "(What's the Story) Morning Glory?"
        assert remove_version_qualifiers("(I Can't Get No) Satisfaction") == "(I Can't Get No) Satisfaction"

    def test_case_insensitive(self):
        """Test that pattern matching is case-insensitive."""
        assert remove_version_qualifiers("Song (REMASTERED)") == "Song"
        assert remove_version_qualifiers("Track (Deluxe EDITION)") == "Track"
        assert remove_version_qualifiers("Album - REMASTER") == "Album"

    def test_whitespace_handling(self):
        """Test proper whitespace handling."""
        assert remove_version_qualifiers("Song  (Remastered)") == "Song"
        assert remove_version_qualifiers("Track(Deluxe)") == "Track"
        assert remove_version_qualifiers("Album - Remaster  ") == "Album"
        assert remove_version_qualifiers("  Song (Live)  ") == "Song"

    def test_no_qualifiers(self):
        """Test that strings without qualifiers pass through unchanged."""
        assert remove_version_qualifiers("1984") == "1984"
        assert remove_version_qualifiers("Nevermind") == "Nevermind"
        assert remove_version_qualifiers("Purple Rain") == "Purple Rain"
        assert remove_version_qualifiers("Jump") == "Jump"

    def test_qualifier_in_middle_not_removed(self):
        """Test that qualifiers in middle of title are preserved."""
        assert remove_version_qualifiers("Live and Let Die") == "Live and Let Die"
        assert remove_version_qualifiers("Acoustic Soul") == "Acoustic Soul"

    def test_empty_string(self):
        """Test handling of empty string."""
        assert remove_version_qualifiers("") == ""

    def test_only_qualifier(self):
        """Test string that is only a qualifier."""
        assert remove_version_qualifiers("(Remastered)") == "(Remastered)"  # Starts with paren


class TestNormalizeSpotifyTitle:
    """Tests for normalize_spotify_title function."""

    def test_basic_version_removal(self):
        """Test basic version qualifier removal."""
        assert normalize_spotify_title("Jump - 2015 Remaster") == "jump"
        assert normalize_spotify_title("1984 (Remastered)") == "1984"
        assert normalize_spotify_title("Heartbeat City (Expanded Edition)") == "heartbeat city"

    def test_soundtrack_removal(self):
        """Test soundtrack qualifier removal."""
        result = normalize_spotify_title('Footloose - From "Footloose" Soundtrack')
        assert result == "footloose"

    def test_with_featured_artists(self):
        """Test combined version and featured artist removal."""
        result = normalize_spotify_title(
            "Blurred Lines ft. T.I. (Deluxe)",
            remove_version_qualifiers_flag=True,
            remove_featured=True,
        )
        assert result == "blurred lines"

    def test_featured_only(self):
        """Test featured artist removal without version removal."""
        result = normalize_spotify_title(
            "Blurred Lines ft. T.I.",
            remove_version_qualifiers_flag=False,
            remove_featured=True,
        )
        assert result == "blurred lines"

    def test_version_only(self):
        """Test version removal without featured artist removal."""
        result = normalize_spotify_title(
            "Song ft. Artist (Remastered)",
            remove_version_qualifiers_flag=True,
            remove_featured=False,
        )
        assert result == "song ft. artist"

    def test_no_normalization(self):
        """Test with all normalization disabled (only lowercase/strip)."""
        result = normalize_spotify_title(
            "Song ft. Artist (Remastered)",
            remove_version_qualifiers_flag=False,
            remove_featured=False,
        )
        assert result == "song ft. artist (remastered)"

    def test_complex_case(self):
        """Test complex case with multiple qualifiers and featured artists."""
        result = normalize_spotify_title(
            "Jump ft. David Lee Roth - 2015 Remaster (Deluxe Edition)",
            remove_version_qualifiers_flag=True,
            remove_featured=True,
        )
        assert result == "jump"

    def test_album_normalization(self):
        """Test album title normalization (no featured artist removal)."""
        result = normalize_spotify_title(
            "Footloose (15th Anniversary Collectors' Edition)",
            remove_version_qualifiers_flag=True,
            remove_featured=False,
        )
        assert result == "footloose"

    def test_track_normalization(self):
        """Test track title normalization (with featured artist removal)."""
        result = normalize_spotify_title(
            "Blurred Lines ft. T.I. - Radio Edit",
            remove_version_qualifiers_flag=True,
            remove_featured=True,
        )
        assert result == "blurred lines"

    def test_whitespace_handling(self):
        """Test proper whitespace handling."""
        result = normalize_spotify_title("  Song (Remastered)  ")
        assert result == "song"

    def test_empty_string(self):
        """Test handling of empty string."""
        assert normalize_spotify_title("") == ""

    def test_lowercase_conversion(self):
        """Test lowercase conversion is always applied."""
        assert normalize_spotify_title("UPPERCASE TITLE") == "uppercase title"
        assert normalize_spotify_title("MixedCase") == "mixedcase"

    def test_preserve_title_starting_with_paren(self):
        """Test titles starting with parentheses are preserved in output."""
        result = normalize_spotify_title("(What's the Story) Morning Glory?")
        assert result == "(what's the story) morning glory?"

    def test_real_spotify_examples(self):
        """Test with real Spotify metadata examples."""
        # Van Halen example
        assert normalize_spotify_title("Jump - 2015 Remaster") == "jump"
        
        # Kenny Loggins example
        result = normalize_spotify_title('Footloose - From "Footloose" Soundtrack')
        assert result == "footloose"
        
        # The Cars example
        assert normalize_spotify_title("You Might Think") == "you might think"
        
        # Album examples
        assert normalize_spotify_title("1984 (Remastered)") == "1984"
        assert normalize_spotify_title("Footloose (15th Anniversary Collectors' Edition)") == "footloose"
        assert normalize_spotify_title("Heartbeat City (Expanded Edition)") == "heartbeat city"
