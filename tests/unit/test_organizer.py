"""Unit tests for file organizer."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from fuzzbin.core.organizer import build_media_paths, MediaPaths
from fuzzbin.core.exceptions import (
    InvalidPatternError,
    MissingFieldError,
    InvalidPathError,
)
from fuzzbin.common.string_utils import normalize_filename
from fuzzbin.parsers import MusicVideoNFO


class TestNormalizeFilename:
    """Tests for normalize_filename utility."""

    def test_diacritics_removed(self):
        """Test diacritic normalization."""
        assert normalize_filename("Björk") == "bjork"
        assert normalize_filename("Café") == "cafe"
        assert normalize_filename("Señor") == "senor"
        assert normalize_filename("Naïve") == "naive"

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

    def test_hyphens_removed(self):
        """Test hyphen removal."""
        assert normalize_filename("Test-Hyphen") == "testhyphen"
        assert normalize_filename("Multi-Word-Title") == "multiwordtitle"

    def test_spaces_to_underscores(self):
        """Test space to underscore conversion."""
        assert normalize_filename("Multiple Words") == "multiple_words"
        assert normalize_filename("A B C") == "a_b_c"

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


class TestBuildMediaPaths:
    """Tests for build_media_paths function."""

    @pytest.fixture
    def root_path(self, tmp_path):
        """Create temp root directory."""
        return tmp_path

    @pytest.fixture
    def sample_nfo(self):
        """Sample MusicVideoNFO for testing."""
        return MusicVideoNFO(
            artist="Robin Thicke",
            title="Blurred Lines",
            year=2013,
            album="Blurred Lines",
            genre="R&B",
        )

    def test_simple_pattern(self, root_path, sample_nfo):
        """Test simple pattern with single field."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="{title}",
            nfo_data=sample_nfo,
        )

        assert paths.video_path == root_path / "Blurred Lines.mp4"
        assert paths.nfo_path == root_path / "Blurred Lines.nfo"

    def test_nested_pattern(self, root_path, sample_nfo):
        """Test nested directory pattern."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="{artist}/{title}",
            nfo_data=sample_nfo,
        )

        assert paths.video_path == root_path / "Robin Thicke" / "Blurred Lines.mp4"
        assert paths.nfo_path == root_path / "Robin Thicke" / "Blurred Lines.nfo"

    def test_multi_level_nested(self, root_path, sample_nfo):
        """Test deeply nested pattern."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="{genre}/{artist}/{year}/{title}",
            nfo_data=sample_nfo,
        )

        expected_video = root_path / "R&B" / "Robin Thicke" / "2013" / "Blurred Lines.mp4"
        assert paths.video_path == expected_video
        assert paths.nfo_path == root_path / "R&B" / "Robin Thicke" / "2013" / "Blurred Lines.nfo"

    def test_normalization_enabled(self, root_path, sample_nfo):
        """Test with normalization enabled."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="{artist}/{title}",
            nfo_data=sample_nfo,
            normalize=True,
        )

        assert paths.video_path == root_path / "robin_thicke" / "blurred_lines.mp4"
        assert paths.nfo_path == root_path / "robin_thicke" / "blurred_lines.nfo"

    def test_custom_extension(self, root_path, sample_nfo):
        """Test custom video extension."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="{title}",
            nfo_data=sample_nfo,
            video_extension=".mkv",
        )

        assert paths.video_path.suffix == ".mkv"
        assert paths.nfo_path.suffix == ".nfo"

    def test_extension_without_dot(self, root_path, sample_nfo):
        """Test extension automatically gets dot prepended."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="{title}",
            nfo_data=sample_nfo,
            video_extension="avi",
        )

        assert paths.video_path.suffix == ".avi"

    def test_invalid_pattern_field(self, root_path, sample_nfo):
        """Test error on invalid pattern field."""
        with pytest.raises(InvalidPatternError) as exc_info:
            build_media_paths(
                root_path=root_path,
                pattern="{invalid_field}",
                nfo_data=sample_nfo,
            )

        assert "invalid_field" in str(exc_info.value)
        assert exc_info.value.pattern == "{invalid_field}"

    def test_missing_required_field(self, root_path):
        """Test error when pattern field is None in NFO."""
        nfo = MusicVideoNFO(artist="Artist")  # title is None

        with pytest.raises(MissingFieldError) as exc_info:
            build_media_paths(
                root_path=root_path,
                pattern="{artist}/{title}",
                nfo_data=nfo,
            )

        assert "title" in str(exc_info.value)
        assert exc_info.value.field == "title"

    def test_empty_field_value(self, root_path):
        """Test error when pattern field is empty string."""
        nfo = MusicVideoNFO(artist="", title="Title")

        with pytest.raises(MissingFieldError) as exc_info:
            build_media_paths(
                root_path=root_path,
                pattern="{artist}/{title}",
                nfo_data=nfo,
            )

        assert "artist" in str(exc_info.value)

    def test_whitespace_only_field(self, root_path):
        """Test error when pattern field contains only whitespace."""
        nfo = MusicVideoNFO(artist="   ", title="Title")

        with pytest.raises(MissingFieldError) as exc_info:
            build_media_paths(
                root_path=root_path,
                pattern="{artist}/{title}",
                nfo_data=nfo,
            )

        assert "artist" in str(exc_info.value)

    def test_tags_field_not_allowed(self, root_path):
        """Test that tags field (list) raises error."""
        nfo = MusicVideoNFO(artist="Artist", title="Title", tags=["tag1"])

        with pytest.raises(InvalidPatternError) as exc_info:
            build_media_paths(
                root_path=root_path,
                pattern="{artist}/{tags}",
                nfo_data=nfo,
            )

        assert "tags" in str(exc_info.value).lower()

    def test_invalid_root_path_not_exists(self, sample_nfo):
        """Test error when root_path doesn't exist."""
        nonexistent = Path("/nonexistent/path/that/does/not/exist")
        with pytest.raises(InvalidPathError) as exc_info:
            build_media_paths(
                root_path=nonexistent,
                pattern="{title}",
                nfo_data=sample_nfo,
            )

        assert "does not exist" in str(exc_info.value)
        assert exc_info.value.path == nonexistent

    def test_invalid_root_path_is_file(self, tmp_path, sample_nfo):
        """Test error when root_path is a file, not directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")

        with pytest.raises(InvalidPathError) as exc_info:
            build_media_paths(
                root_path=file_path,
                pattern="{title}",
                nfo_data=sample_nfo,
            )

        assert "not a directory" in str(exc_info.value)

    def test_year_field_int_conversion(self, root_path, sample_nfo):
        """Test year (int) is converted to string in path."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="{year}",
            nfo_data=sample_nfo,
        )

        assert paths.video_path == root_path / "2013.mp4"

    def test_normalization_with_diacritics(self, root_path):
        """Test normalization with diacritics in NFO data."""
        nfo = MusicVideoNFO(artist="Björk", title="Humúríús")

        paths = build_media_paths(
            root_path=root_path,
            pattern="{artist}/{title}",
            nfo_data=nfo,
            normalize=True,
        )

        assert paths.video_path == root_path / "bjork" / "humurius.mp4"

    def test_normalization_with_special_chars(self, root_path):
        """Test normalization with special characters."""
        nfo = MusicVideoNFO(artist="AC/DC", title="Back In Black")

        paths = build_media_paths(
            root_path=root_path,
            pattern="{artist}/{title}",
            nfo_data=nfo,
            normalize=True,
        )

        assert paths.video_path == root_path / "acdc" / "back_in_black.mp4"

    def test_media_paths_immutable(self, root_path, sample_nfo):
        """Test MediaPaths is immutable (frozen)."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="{title}",
            nfo_data=sample_nfo,
        )

        with pytest.raises(ValidationError):
            paths.video_path = Path("/new/path")


class TestPatternEdgeCases:
    """Test edge cases in pattern parsing."""

    @pytest.fixture
    def root_path(self, tmp_path):
        return tmp_path

    @pytest.fixture
    def sample_nfo(self):
        return MusicVideoNFO(artist="Artist", title="Title", year=2020)

    def test_pattern_with_literal_text(self, root_path, sample_nfo):
        """Test pattern with literal text mixed with fields."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="videos/{artist}/mv_{title}",
            nfo_data=sample_nfo,
        )

        assert paths.video_path == root_path / "videos" / "Artist" / "mv_Title.mp4"

    def test_pattern_no_fields(self, root_path, sample_nfo):
        """Test pattern with no field placeholders (all literal)."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="static/filename",
            nfo_data=sample_nfo,
        )

        assert paths.video_path == root_path / "static" / "filename.mp4"

    def test_duplicate_fields_in_pattern(self, root_path, sample_nfo):
        """Test pattern with duplicate field usage."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="{artist}/{artist}_{title}",
            nfo_data=sample_nfo,
        )

        assert paths.video_path == root_path / "Artist" / "Artist_Title.mp4"

    def test_single_field_pattern(self, root_path, sample_nfo):
        """Test pattern with single field."""
        paths = build_media_paths(
            root_path=root_path,
            pattern="{artist}",
            nfo_data=sample_nfo,
        )

        assert paths.video_path == root_path / "Artist.mp4"

    def test_all_fields_pattern(self, root_path):
        """Test pattern using all available fields."""
        nfo = MusicVideoNFO(
            title="Title",
            album="Album",
            studio="Studio",
            year=2020,
            director="Director",
            genre="Genre",
            artist="Artist",
        )

        paths = build_media_paths(
            root_path=root_path,
            pattern="{genre}/{artist}/{album}/{year}/{director}/{title}",
            nfo_data=nfo,
        )

        expected = root_path / "Genre" / "Artist" / "Album" / "2020" / "Director" / "Title.mp4"
        assert paths.video_path == expected
