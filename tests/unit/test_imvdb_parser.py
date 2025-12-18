"""Tests for IMVDb response parser."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fuzzbin.parsers.imvdb_models import (
    EmptySearchResultsError,
    IMVDbEntity,
    IMVDbEntityVideo,
    IMVDbVideo,
    IMVDbVideoSearchResult,
    VideoNotFoundError,
)
from fuzzbin.parsers.imvdb_parser import IMVDbParser


@pytest.fixture
def examples_dir():
    """Get the examples directory path."""
    return Path(__file__).parent.parent.parent / "examples"


@pytest.fixture
def video_response(examples_dir):
    """Load example video response."""
    with open(examples_dir / "imvdb_video_response.json") as f:
        return json.load(f)


@pytest.fixture
def entity_response(examples_dir):
    """Load example entity response."""
    with open(examples_dir / "imvdb_entity_response.json") as f:
        return json.load(f)


@pytest.fixture
def search_videos_response(examples_dir):
    """Load example search videos response."""
    with open(examples_dir / "imvdb_search_videos_response.json") as f:
        return json.load(f)


@pytest.fixture
def search_entities_response(examples_dir):
    """Load example search entities response."""
    with open(examples_dir / "imvdb_search_entities_response.json") as f:
        return json.load(f)


class TestIMVDbVideoModel:
    """Tests for IMVDbVideo model."""

    def test_parse_video_response(self, video_response):
        """Test parsing a real video response."""
        video = IMVDbVideo.model_validate(video_response)
        
        assert video.id == 121779770452
        assert video.song_title == "Blurred Lines"
        assert video.year == 2013
        assert len(video.artists) == 1
        assert video.artists[0].name == "Robin Thicke"
        assert len(video.featured_artists) == 2
        assert len(video.directors) == 1
        assert video.directors[0].entity_name == "Diane Martel"
        assert len(video.sources) == 3
        assert video.is_exact_match is True  # Default value

    def test_video_sources(self, video_response):
        """Test parsing video sources."""
        video = IMVDbVideo.model_validate(video_response)
        
        # Check YouTube primary source
        primary_sources = [s for s in video.sources if s.is_primary]
        assert len(primary_sources) == 1
        assert primary_sources[0].source == "youtube"
        assert primary_sources[0].source_data == "zwT6DZCQi9k"

    def test_video_optional_fields(self):
        """Test that optional fields work correctly."""
        minimal_data = {"id": 12345}
        video = IMVDbVideo.model_validate(minimal_data)
        
        assert video.id == 12345
        assert video.song_title is None
        assert video.year is None
        assert video.artists == []
        assert video.featured_artists == []

    def test_video_extra_fields_ignored(self):
        """Test that extra fields are ignored."""
        data = {
            "id": 12345,
            "song_title": "Test",
            "unknown_field": "should be ignored",
            "another_unknown": 999,
        }
        video = IMVDbVideo.model_validate(data)
        
        assert video.id == 12345
        assert video.song_title == "Test"
        assert not hasattr(video, "unknown_field")


class TestIMVDbEntityModel:
    """Tests for IMVDbEntity model."""

    def test_parse_entity_response(self, entity_response):
        """Test parsing a real entity response via parser."""
        entity = IMVDbParser.parse_entity(entity_response)
        
        assert entity.id == 838673
        assert entity.slug == "robin-thicke"
        assert entity.artist_video_count == 4
        assert entity.featured_video_count == 0
        assert len(entity.artist_videos) == 19
        assert entity.artist_videos_total == 19

    def test_entity_video_list(self, entity_response):
        """Test entity video list parsing."""
        entity = IMVDbParser.parse_entity(entity_response)
        
        # Check first video
        first_video = entity.artist_videos[0]
        assert isinstance(first_video, IMVDbEntityVideo)
        assert first_video.id == 244847000641
        assert first_video.song_title == "Back Together"
        assert first_video.year == 2015

    def test_entity_optional_fields(self):
        """Test entity with minimal data."""
        minimal_data = {
            "id": 12345,
            "slug": "test-artist",
            "url": "https://imvdb.com/n/test-artist",
            "artist_video_count": 0,
            "featured_video_count": 0,
        }
        entity = IMVDbEntity.model_validate(minimal_data)
        
        assert entity.id == 12345
        assert entity.slug == "test-artist"
        assert entity.name is None
        assert entity.artist_videos == []


class TestIMVDbSearchResultModel:
    """Tests for IMVDbVideoSearchResult model."""

    def test_parse_search_results(self, search_videos_response):
        """Test parsing search results."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        assert results.pagination.total_results == 196
        assert results.pagination.current_page == 1
        assert results.pagination.per_page == 25
        assert results.pagination.total_pages == 8
        assert len(results.results) == 25

    def test_search_result_videos(self, search_videos_response):
        """Test individual video results."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        first_result = results.results[0]
        assert isinstance(first_result, IMVDbEntityVideo)
        assert first_result.id == 121779770452
        assert first_result.song_title == "Blurred Lines"
        assert first_result.year == 2013


class TestIMVDbParser:
    """Tests for IMVDbParser class."""

    def test_parse_video(self, video_response):
        """Test parse_video method."""
        video = IMVDbParser.parse_video(video_response)
        
        assert isinstance(video, IMVDbVideo)
        assert video.id == 121779770452
        assert video.song_title == "Blurred Lines"

    def test_parse_entity(self, entity_response):
        """Test parse_entity method."""
        entity = IMVDbParser.parse_entity(entity_response)
        
        assert isinstance(entity, IMVDbEntity)
        assert entity.id == 838673
        assert entity.slug == "robin-thicke"

    def test_parse_search_results(self, search_videos_response):
        """Test parse_search_results method."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        assert isinstance(results, IMVDbVideoSearchResult)
        assert results.pagination.total_results == 196


class TestFindBestVideoMatch:
    """Tests for find_best_video_match method."""

    def test_exact_match(self, search_videos_response):
        """Test exact match found."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        video = IMVDbParser.find_best_video_match(
            results.results,
            "Robin Thicke",
            "Blurred Lines"
        )
        
        assert video.id == 121779770452
        assert video.song_title == "Blurred Lines"
        assert video.is_exact_match is True

    def test_case_insensitive_match(self, search_videos_response):
        """Test case-insensitive matching."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        video = IMVDbParser.find_best_video_match(
            results.results,
            "robin thicke",
            "BLURRED LINES"
        )
        
        assert video.id == 121779770452
        assert video.is_exact_match is True

    def test_whitespace_normalization(self, search_videos_response):
        """Test whitespace normalization in matching."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        video = IMVDbParser.find_best_video_match(
            results.results,
            "  Robin Thicke  ",
            "  Blurred Lines  "
        )
        
        assert video.id == 121779770452
        assert video.is_exact_match is True

    def test_empty_results_raises_error(self):
        """Test that empty results raises EmptySearchResultsError."""
        with pytest.raises(EmptySearchResultsError) as exc_info:
            IMVDbParser.find_best_video_match(
                [],
                "Artist",
                "Title"
            )
        
        assert "Artist" in str(exc_info.value)
        assert "Title" in str(exc_info.value)

    def test_no_match_raises_error(self, search_videos_response):
        """Test that no match raises VideoNotFoundError."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        with pytest.raises(VideoNotFoundError) as exc_info:
            IMVDbParser.find_best_video_match(
                results.results,
                "Nonexistent Artist",
                "Nonexistent Title"
            )
        
        assert "Nonexistent Artist" in str(exc_info.value)
        assert "Nonexistent Title" in str(exc_info.value)

    def test_fuzzy_match_with_typo(self, search_videos_response):
        """Test fuzzy matching with minor typo."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        # Intentional typo: "Blured" instead of "Blurred"
        video = IMVDbParser.find_best_video_match(
            results.results,
            "Robin Thicke",
            "Blured Lines",
            threshold=0.7  # Lower threshold for typo
        )
        
        assert video.song_title == "Blurred Lines"
        assert video.is_exact_match is False

    def test_fuzzy_match_below_threshold(self, search_videos_response):
        """Test that fuzzy match below threshold raises error."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        with pytest.raises(VideoNotFoundError):
            IMVDbParser.find_best_video_match(
                results.results,
                "Completely Different Artist",
                "Totally Different Title",
                threshold=0.8
            )

    def test_featured_artists_stripped(self, search_videos_response):
        """Test that featured artists are stripped in matching."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        # Search with featured artist notation
        video = IMVDbParser.find_best_video_match(
            results.results,
            "Robin Thicke ft. T.I.",
            "Blurred Lines"
        )
        
        assert video.id == 121779770452
        assert video.is_exact_match is True

    def test_multiple_artists_in_results(self, search_videos_response):
        """Test matching when multiple artists in results."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        # "Rollacoasta" is second result
        video = IMVDbParser.find_best_video_match(
            results.results,
            "Robin Thicke",
            "Rollacoasta"
        )
        
        assert video.id == 968122970313
        assert video.song_title == "Rollacoasta"
        assert video.is_exact_match is True

    def test_primary_artists_only_matched(self, search_videos_response):
        """Test that only primary artists are matched, not featured."""
        results = IMVDbParser.parse_search_results(search_videos_response)
        
        # Try to match by featured artist name (should not work for exact match)
        # T.I. is a featured artist on "Blurred Lines"
        with pytest.raises(VideoNotFoundError):
            IMVDbParser.find_best_video_match(
                results.results,
                "T.I.",
                "Blurred Lines",
                threshold=0.9  # High threshold to avoid fuzzy matches
            )


class TestExceptionHierarchy:
    """Tests for custom exception classes."""

    def test_video_not_found_error_basic(self):
        """Test VideoNotFoundError basic usage."""
        error = VideoNotFoundError()
        assert "Video not found" in str(error)

    def test_video_not_found_error_with_details(self):
        """Test VideoNotFoundError with artist and title."""
        error = VideoNotFoundError(artist="Artist", title="Title")
        assert "Artist" in str(error)
        assert "Title" in str(error)

    def test_video_not_found_error_custom_message(self):
        """Test VideoNotFoundError with custom message."""
        error = VideoNotFoundError(message="Custom error message")
        assert "Custom error message" in str(error)

    def test_empty_search_results_error(self):
        """Test EmptySearchResultsError."""
        error = EmptySearchResultsError(artist="Artist", title="Title")
        assert "no results" in str(error).lower()
        assert "Artist" in str(error)
        assert "Title" in str(error)

    def test_empty_search_results_is_video_not_found(self):
        """Test that EmptySearchResultsError is subclass of VideoNotFoundError."""
        assert issubclass(EmptySearchResultsError, VideoNotFoundError)
        
        error = EmptySearchResultsError()
        assert isinstance(error, VideoNotFoundError)
