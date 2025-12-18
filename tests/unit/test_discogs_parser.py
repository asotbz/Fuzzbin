"""Tests for Discogs response parser."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fuzzbin.parsers.discogs_models import (
    DiscogsArtistRelease,
    DiscogsArtistReleasesResult,
    DiscogsMaster,
    DiscogsPagination,
    DiscogsRelease,
    DiscogsSearchResult,
    DiscogsSearchResultItem,
    DiscogsVideo,
    EmptySearchResultsError,
    MasterNotFoundError,
    ReleaseNotFoundError,
)
from fuzzbin.parsers.discogs_parser import DiscogsParser


@pytest.fixture
def examples_dir():
    """Get the examples directory path."""
    return Path(__file__).parent.parent.parent / "examples"


@pytest.fixture
def search_response(examples_dir):
    """Load example search response."""
    with open(examples_dir / "discogs_search_response.json") as f:
        return json.load(f)


@pytest.fixture
def master_response(examples_dir):
    """Load example master response."""
    with open(examples_dir / "discogs_master_response.json") as f:
        return json.load(f)


@pytest.fixture
def release_response(examples_dir):
    """Load example release response."""
    with open(examples_dir / "discogs_release_response.json") as f:
        return json.load(f)


@pytest.fixture
def artist_releases_response(examples_dir):
    """Load example artist releases response."""
    with open(examples_dir / "discogs_artist_releases_response.json") as f:
        return json.load(f)


class TestDiscogsPaginationModel:
    """Tests for DiscogsPagination model."""

    def test_parse_pagination(self, search_response):
        """Test parsing pagination metadata."""
        pagination = DiscogsPagination.model_validate(search_response["pagination"])

        assert pagination.page == 1
        assert pagination.pages == 1
        assert pagination.per_page == 50
        assert pagination.items == 10
        assert pagination.urls == {}

    def test_pagination_with_urls(self, artist_releases_response):
        """Test pagination with navigation URLs."""
        pagination = DiscogsPagination.model_validate(
            artist_releases_response["pagination"]
        )

        assert pagination.page == 1
        assert pagination.pages == 43
        assert pagination.items == 2138
        assert "last" in pagination.urls
        assert "next" in pagination.urls

    def test_pagination_optional_fields(self):
        """Test pagination with minimal data."""
        minimal_data = {"page": 1, "pages": 5, "per_page": 25, "items": 100}
        pagination = DiscogsPagination.model_validate(minimal_data)

        assert pagination.page == 1
        assert pagination.urls is None


class TestDiscogsMasterModel:
    """Tests for DiscogsMaster model."""

    def test_parse_master_response(self, master_response):
        """Test parsing a real master response."""
        master = DiscogsMaster.model_validate(master_response)

        assert master.id == 13814
        assert master.title == "Nevermind"
        assert master.year == 1992
        assert len(master.artists) == 1
        assert master.artists[0].name == "Nirvana"
        assert master.artists[0].id == 125246
        assert master.genres == ["Rock"]
        assert master.styles == ["Grunge"]
        assert len(master.tracklist) == 12
        assert len(master.images) == 6
        assert len(master.videos) == 12
        assert master.main_release == 25823602
        assert master.is_exact_match is True  # Default value

    def test_master_tracklist(self, master_response):
        """Test parsing master tracklist."""
        master = DiscogsMaster.model_validate(master_response)

        first_track = master.tracklist[0]
        assert first_track.position == "A1"
        assert first_track.type_ == "track"
        assert first_track.title == "Smells Like Teen Spirit"
        assert first_track.duration == "5:00"
        assert first_track.extraartists == []

        # Check track with extraartists
        last_track = master.tracklist[-1]
        assert last_track.title == "Something In The Way"
        assert len(last_track.extraartists) == 1
        assert last_track.extraartists[0].name == "Kirk Canning"
        assert last_track.extraartists[0].role == "Cello"

    def test_master_videos(self, master_response):
        """Test parsing master videos."""
        master = DiscogsMaster.model_validate(master_response)

        first_video = master.videos[0]
        assert isinstance(first_video, DiscogsVideo)
        assert first_video.uri == "https://www.youtube.com/watch?v=hTWKbfoikeg"
        assert first_video.title == "Nirvana - Smells Like Teen Spirit (Official Music Video)"
        assert first_video.duration == 279
        assert first_video.embed is True

    def test_master_optional_fields(self):
        """Test master with minimal data."""
        minimal_data = {
            "id": 12345,
            "title": "Test Album",
        }
        master = DiscogsMaster.model_validate(minimal_data)

        assert master.id == 12345
        assert master.title == "Test Album"
        assert master.artists == []
        assert master.year is None
        assert master.tracklist == []

    def test_master_extra_fields_ignored(self):
        """Test that extra fields are ignored."""
        data = {
            "id": 12345,
            "title": "Test",
            "unknown_field": "should be ignored",
        }
        master = DiscogsMaster.model_validate(data)

        assert master.id == 12345
        assert not hasattr(master, "unknown_field")


class TestDiscogsReleaseModel:
    """Tests for DiscogsRelease model."""

    def test_parse_release_response(self, release_response):
        """Test parsing a real release response."""
        release = DiscogsRelease.model_validate(release_response)

        assert release.id == 25823602
        assert release.title == "Nevermind"
        assert release.year == 1992
        assert release.released == "1992"
        assert release.country == "Colombia"
        assert len(release.artists) == 1
        assert release.artists[0].name == "Nirvana"
        assert release.genres == ["Rock"]
        assert release.styles == ["Grunge"]
        assert len(release.tracklist) == 12
        assert len(release.labels) == 1
        assert release.labels[0].name == "DGC"
        assert release.master_id == 13814
        assert release.is_exact_match is True

    def test_release_labels(self, release_response):
        """Test parsing release labels."""
        release = DiscogsRelease.model_validate(release_response)

        label = release.labels[0]
        assert label.name == "DGC"
        assert label.catno == "11613707014"
        assert label.id == 86487

    def test_release_optional_fields(self):
        """Test release with minimal data."""
        minimal_data = {
            "id": 12345,
            "title": "Test Release",
        }
        release = DiscogsRelease.model_validate(minimal_data)

        assert release.id == 12345
        assert release.country is None
        assert release.labels == []


class TestDiscogsSearchResultModel:
    """Tests for DiscogsSearchResult model."""

    def test_parse_search_results(self, search_response):
        """Test parsing search results."""
        results = DiscogsParser.parse_search_response(search_response)

        assert results.pagination.page == 1
        assert results.pagination.items == 10
        assert len(results.results) == 10

    def test_search_result_items(self, search_response):
        """Test individual search result items."""
        results = DiscogsParser.parse_search_response(search_response)

        first_result = results.results[0]
        assert isinstance(first_result, DiscogsSearchResultItem)
        assert first_result.id == 42473
        assert first_result.type == "master"
        assert first_result.master_id == 42473
        assert first_result.title == "Nirvana - From The Muddy Banks Of The Wishkah"
        assert first_result.year == "1996"

        # Check second result (Nevermind)
        second_result = results.results[1]
        assert second_result.master_id == 13814
        assert second_result.title == "Nirvana - Nevermind"
        assert second_result.year == "1992"

    def test_search_result_metadata(self, search_response):
        """Test search result metadata fields."""
        results = DiscogsParser.parse_search_response(search_response)

        result = results.results[1]
        assert result.country == "Colombia"
        assert result.genre == ["Rock"]
        assert result.style == ["Grunge"]
        assert "Vinyl" in result.format
        assert result.thumb is not None
        assert result.cover_image is not None


class TestDiscogsArtistReleaseModel:
    """Tests for DiscogsArtistRelease model."""

    def test_parse_artist_releases(self, artist_releases_response):
        """Test parsing artist releases."""
        # Parse manually first
        result = DiscogsArtistReleasesResult.model_validate(artist_releases_response)

        assert result.pagination.page == 1
        assert result.pagination.items == 2138
        assert len(result.releases) > 0

    def test_artist_release_fields(self, artist_releases_response):
        """Test artist release fields."""
        result = DiscogsArtistReleasesResult.model_validate(artist_releases_response)

        # First release is type "release"
        first_release = result.releases[0]
        assert first_release.id == 32495904
        assert first_release.type == "release"
        assert first_release.artist == "Nirvana"
        assert first_release.year == 1988

        # Second release is type "master"
        second_release = result.releases[1]
        assert second_release.type == "master"
        assert second_release.main_release == 392900


class TestDiscogsParser:
    """Tests for DiscogsParser class."""

    def test_parse_search_response(self, search_response):
        """Test parse_search_response method."""
        results = DiscogsParser.parse_search_response(search_response)

        assert isinstance(results, DiscogsSearchResult)
        assert len(results.results) == 10

    def test_parse_master_response(self, master_response):
        """Test parse_master_response method."""
        master = DiscogsParser.parse_master_response(master_response)

        assert isinstance(master, DiscogsMaster)
        assert master.id == 13814
        assert master.is_exact_match is True

    def test_parse_release_response(self, release_response):
        """Test parse_release_response method."""
        release = DiscogsParser.parse_release_response(release_response)

        assert isinstance(release, DiscogsRelease)
        assert release.id == 25823602
        assert release.is_exact_match is True

    def test_parse_artist_releases_response(self, artist_releases_response):
        """Test parse_artist_releases_response filters to masters only."""
        result = DiscogsParser.parse_artist_releases_response(artist_releases_response)

        assert isinstance(result, DiscogsArtistReleasesResult)
        # All returned releases should be type "master"
        assert all(r.type == "master" for r in result.releases)
        # Should be fewer than total in response (which has both master and release types)
        assert len(result.releases) < result.pagination.items


class TestMasterValidation:
    """Tests for master response validation."""

    def test_master_with_valid_artist_and_track(self, master_response):
        """Test validation with matching artist and track."""
        master = DiscogsParser.parse_master_response(
            master_response, artist="Nirvana", track_title="Smells Like Teen Spirit"
        )

        assert master.is_exact_match is True

    def test_master_with_valid_artist_only(self, master_response):
        """Test validation with matching artist only."""
        master = DiscogsParser.parse_master_response(
            master_response, artist="Nirvana"
        )

        assert master.is_exact_match is True

    def test_master_with_valid_track_only(self, master_response):
        """Test validation with matching track only."""
        master = DiscogsParser.parse_master_response(
            master_response, track_title="Lithium"
        )

        assert master.is_exact_match is True

    def test_master_with_invalid_artist(self, master_response):
        """Test validation with non-matching artist."""
        master = DiscogsParser.parse_master_response(
            master_response,
            artist="Pearl Jam",
            track_title="Smells Like Teen Spirit",
        )

        assert master.is_exact_match is False

    def test_master_with_invalid_track(self, master_response):
        """Test validation with non-matching track."""
        master = DiscogsParser.parse_master_response(
            master_response, artist="Nirvana", track_title="Nonexistent Track"
        )

        assert master.is_exact_match is False

    def test_master_case_insensitive_validation(self, master_response):
        """Test validation is case-insensitive."""
        master = DiscogsParser.parse_master_response(
            master_response, artist="nirvana", track_title="LITHIUM"
        )

        assert master.is_exact_match is True

    def test_master_whitespace_normalization(self, master_response):
        """Test validation normalizes whitespace."""
        master = DiscogsParser.parse_master_response(
            master_response, artist="  Nirvana  ", track_title="  Lithium  "
        )

        assert master.is_exact_match is True

    def test_master_track_in_any_position(self, master_response):
        """Test validation finds track in any position."""
        # Test first track (A1)
        master = DiscogsParser.parse_master_response(
            master_response, track_title="Smells Like Teen Spirit"
        )
        assert master.is_exact_match is True

        # Test middle track (B3)
        master = DiscogsParser.parse_master_response(
            master_response, track_title="Drain You"
        )
        assert master.is_exact_match is True

        # Test last track (B7)
        master = DiscogsParser.parse_master_response(
            master_response, track_title="Something In The Way"
        )
        assert master.is_exact_match is True


class TestReleaseValidation:
    """Tests for release response validation."""

    def test_release_with_valid_artist_and_track(self, release_response):
        """Test validation with matching artist and track."""
        release = DiscogsParser.parse_release_response(
            release_response, artist="Nirvana", track_title="In Bloom"
        )

        assert release.is_exact_match is True

    def test_release_with_invalid_artist(self, release_response):
        """Test validation with non-matching artist."""
        release = DiscogsParser.parse_release_response(
            release_response, artist="Soundgarden", track_title="In Bloom"
        )

        assert release.is_exact_match is False

    def test_release_case_insensitive(self, release_response):
        """Test release validation is case-insensitive."""
        release = DiscogsParser.parse_release_response(
            release_response, artist="NIRVANA", track_title="polly"
        )

        assert release.is_exact_match is True


class TestFindEarliestMaster:
    """Tests for find_earliest_master method."""

    def test_find_earliest_from_search(self, search_response):
        """Test finding earliest master from search results."""
        results = DiscogsParser.parse_search_response(search_response)
        earliest = DiscogsParser.find_earliest_master(results)

        # Should find master 13814 (Nevermind) from 1992, not 42473 from 1996
        assert earliest.master_id == 13814
        assert earliest.year == "1992"
        assert "Nevermind" in earliest.title

    def test_find_earliest_with_context(self, search_response):
        """Test finding earliest with artist/title context for logging."""
        results = DiscogsParser.parse_search_response(search_response)
        earliest = DiscogsParser.find_earliest_master(
            results, artist="Nirvana", track_title="Smells Like Teen Spirit"
        )

        assert earliest.master_id == 13814

    def test_find_earliest_lowest_id_tiebreaker(self):
        """Test that lowest master_id is used as tiebreaker for same year."""
        # Create mock results with same year, different master_ids
        mock_data = {
            "pagination": {"page": 1, "pages": 1, "per_page": 50, "items": 3},
            "results": [
                {
                    "id": 300,
                    "type": "master",
                    "title": "Album C",
                    "master_id": 300,
                    "year": "1992",
                },
                {
                    "id": 100,
                    "type": "master",
                    "title": "Album A",
                    "master_id": 100,
                    "year": "1992",
                },
                {
                    "id": 200,
                    "type": "master",
                    "title": "Album B",
                    "master_id": 200,
                    "year": "1992",
                },
            ],
        }

        results = DiscogsParser.parse_search_response(mock_data)
        earliest = DiscogsParser.find_earliest_master(results)

        # Should return master_id 100 (lowest)
        assert earliest.master_id == 100
        assert earliest.title == "Album A"

    def test_find_earliest_filters_non_masters(self):
        """Test that non-master results are filtered out."""
        mock_data = {
            "pagination": {"page": 1, "pages": 1, "per_page": 50, "items": 2},
            "results": [
                {
                    "id": 12345,
                    "type": "release",  # Not a master
                    "title": "Some Release",
                    "year": "1990",
                },
                {
                    "id": 200,
                    "type": "master",
                    "title": "Some Master",
                    "master_id": 200,
                    "year": "1992",
                },
            ],
        }

        results = DiscogsParser.parse_search_response(mock_data)
        earliest = DiscogsParser.find_earliest_master(results)

        # Should return the master, not the earlier release
        assert earliest.master_id == 200
        assert earliest.year == "1992"

    def test_find_earliest_empty_results_raises_error(self):
        """Test that empty search results raises error."""
        mock_data = {
            "pagination": {"page": 1, "pages": 0, "per_page": 50, "items": 0},
            "results": [],
        }

        results = DiscogsParser.parse_search_response(mock_data)

        with pytest.raises(EmptySearchResultsError) as exc_info:
            DiscogsParser.find_earliest_master(results, artist="Artist", track_title="Title")

        assert "Artist" in str(exc_info.value)
        assert "Title" in str(exc_info.value)

    def test_find_earliest_no_masters_raises_error(self):
        """Test that results with no masters raises error."""
        mock_data = {
            "pagination": {"page": 1, "pages": 1, "per_page": 50, "items": 1},
            "results": [
                {
                    "id": 12345,
                    "type": "release",  # Not a master
                    "title": "Some Release",
                    "year": "1990",
                }
            ],
        }

        results = DiscogsParser.parse_search_response(mock_data)

        with pytest.raises(EmptySearchResultsError):
            DiscogsParser.find_earliest_master(results)


class TestFilterMusicVideos:
    """Tests for _filter_music_videos method."""

    def test_filter_excludes_audio_videos(self):
        """Test that videos with 'audio' in title are excluded."""
        videos = [
            DiscogsVideo(
                uri="http://example.com/1",
                title="Song Title (Official Music Video)",
                duration=180,
                embed=True,
            ),
            DiscogsVideo(
                uri="http://example.com/2",
                title="Song Title (Audio)",
                duration=180,
                embed=True,
            ),
            DiscogsVideo(
                uri="http://example.com/3",
                title="Song Title - Official Audio",
                duration=180,
                embed=True,
            ),
        ]

        filtered = DiscogsParser._filter_music_videos(videos)

        assert len(filtered) == 1
        assert "Music Video" in filtered[0].title

    def test_filter_excludes_lyric_videos(self):
        """Test that videos with 'lyric' in title are excluded."""
        videos = [
            DiscogsVideo(
                uri="http://example.com/1",
                title="Song Title (Official Video)",
                duration=180,
                embed=True,
            ),
            DiscogsVideo(
                uri="http://example.com/2",
                title="Song Title (Lyric Video)",
                duration=180,
                embed=True,
            ),
            DiscogsVideo(
                uri="http://example.com/3",
                title="Song Title - Lyrics",
                duration=180,
                embed=True,
            ),
        ]

        filtered = DiscogsParser._filter_music_videos(videos)

        assert len(filtered) == 1
        assert "Official Video" in filtered[0].title

    def test_filter_excludes_live_videos(self):
        """Test that videos with 'live' in title are excluded."""
        videos = [
            DiscogsVideo(
                uri="http://example.com/1",
                title="Song Title (Music Video)",
                duration=180,
                embed=True,
            ),
            DiscogsVideo(
                uri="http://example.com/2",
                title="Song Title (Live at Reading)",
                duration=180,
                embed=True,
            ),
            DiscogsVideo(
                uri="http://example.com/3",
                title="Song Title - Live Performance",
                duration=180,
                embed=True,
            ),
        ]

        filtered = DiscogsParser._filter_music_videos(videos)

        assert len(filtered) == 1
        assert "Music Video" in filtered[0].title

    def test_filter_case_insensitive(self):
        """Test that filtering is case-insensitive."""
        videos = [
            DiscogsVideo(
                uri="http://example.com/1",
                title="Song Title (AUDIO)",
                duration=180,
                embed=True,
            ),
            DiscogsVideo(
                uri="http://example.com/2",
                title="Song Title (Lyric Video)",
                duration=180,
                embed=True,
            ),
            DiscogsVideo(
                uri="http://example.com/3",
                title="Song Title (LIVE)",
                duration=180,
                embed=True,
            ),
            DiscogsVideo(
                uri="http://example.com/4",
                title="Song Title (Official Video)",
                duration=180,
                embed=True,
            ),
        ]

        filtered = DiscogsParser._filter_music_videos(videos)

        assert len(filtered) == 1
        assert "Official Video" in filtered[0].title

    def test_filter_with_real_master_videos(self, master_response):
        """Test filtering with real master response videos."""
        master = DiscogsMaster.model_validate(master_response)
        filtered = DiscogsParser._filter_music_videos(master.videos)

        # Original has 12 videos, but some are audio-only
        assert len(filtered) < len(master.videos)

        # Check that official music videos are kept
        titles = [v.title for v in filtered]
        assert any("Official Music Video" in t for t in titles)

        # Check that audio-only are excluded
        assert not any("Audio)" in t for t in titles)

    def test_filter_empty_list(self):
        """Test filtering empty video list."""
        filtered = DiscogsParser._filter_music_videos([])
        assert filtered == []

    def test_filter_all_excluded(self):
        """Test when all videos are excluded."""
        videos = [
            DiscogsVideo(
                uri="http://example.com/1",
                title="Song (Audio)",
                duration=180,
                embed=True,
            ),
            DiscogsVideo(
                uri="http://example.com/2",
                title="Song (Lyric Video)",
                duration=180,
                embed=True,
            ),
        ]

        filtered = DiscogsParser._filter_music_videos(videos)
        assert len(filtered) == 0


class TestExceptionHierarchy:
    """Tests for custom exception classes."""

    def test_master_not_found_error_basic(self):
        """Test MasterNotFoundError basic usage."""
        error = MasterNotFoundError()
        assert "Master release not found" in str(error)

    def test_master_not_found_error_with_id(self):
        """Test MasterNotFoundError with master_id."""
        error = MasterNotFoundError(master_id=12345)
        assert "12345" in str(error)

    def test_master_not_found_error_with_details(self):
        """Test MasterNotFoundError with artist and title."""
        error = MasterNotFoundError(artist="Artist", title="Title")
        assert "Artist" in str(error)
        assert "Title" in str(error)

    def test_release_not_found_error_basic(self):
        """Test ReleaseNotFoundError basic usage."""
        error = ReleaseNotFoundError()
        assert "Release not found" in str(error)

    def test_release_not_found_error_with_id(self):
        """Test ReleaseNotFoundError with release_id."""
        error = ReleaseNotFoundError(release_id=67890)
        assert "67890" in str(error)

    def test_empty_search_results_error(self):
        """Test EmptySearchResultsError."""
        error = EmptySearchResultsError(artist="Artist", title="Title")
        assert "no results" in str(error).lower()
        assert "Artist" in str(error)
        assert "Title" in str(error)

    def test_exception_attributes(self):
        """Test that exception attributes are stored."""
        error = MasterNotFoundError(master_id=123, artist="Test", title="Song")
        assert error.master_id == 123
        assert error.artist == "Test"
        assert error.title == "Song"
