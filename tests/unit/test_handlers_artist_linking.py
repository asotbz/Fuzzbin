"""Unit tests for artist linking in task handlers.

Tests featured artist extraction and storage from IMVDb responses
in handle_add_single_import and handle_metadata_enrich handlers.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fuzzbin.tasks.models import Job, JobType
from fuzzbin.tasks.handlers import handle_add_single_import, handle_metadata_enrich


@pytest.fixture
def examples_dir():
    """Get path to examples directory."""
    return Path(__file__).parent.parent.parent / "examples"


@pytest.fixture
def imvdb_video_response(examples_dir):
    """Load IMVDb video response example with featured artists."""
    with open(examples_dir / "imvdb_video_response.json") as f:
        return json.load(f)


@pytest.fixture
def mock_repository():
    """Mock VideoRepository with artist linking methods."""
    repository = AsyncMock()
    repository.create_video = AsyncMock(return_value=1)
    repository.update_video = AsyncMock()
    repository.get_video = AsyncMock(
        return_value=MagicMock(
            id=1,
            title="Blurred Lines",
            artist="Robin Thicke",
            director=None,
            year=None,
        )
    )
    repository.get_video_by_imvdb_id = AsyncMock(side_effect=Exception("Not found"))
    repository.upsert_artist = AsyncMock(side_effect=lambda name, **kwargs: hash(name) % 1000)
    repository.link_video_artist = AsyncMock()
    repository.unlink_all_video_artists = AsyncMock(return_value=0)
    repository.get_video_artists = AsyncMock(return_value=[])

    # Transaction
    repository.transaction = MagicMock()
    repository.transaction.__aenter__ = AsyncMock()
    repository.transaction.__aexit__ = AsyncMock()

    # Query mock
    query = AsyncMock()
    query.where_title = MagicMock(return_value=query)
    query.where_artist = MagicMock(return_value=query)
    query.execute = AsyncMock(return_value=[])
    repository.query = MagicMock(return_value=query)

    return repository


@pytest.fixture
def mock_config():
    """Mock fuzzbin config with IMVDb configured."""
    config = MagicMock()
    config.apis = {
        "imvdb": MagicMock(
            name="imvdb",
            base_url="https://imvdb.com/api/v1",
            custom={"app_key": "test-key"},
        )
    }
    return config


@pytest.fixture
def add_single_import_job():
    """Create a job for handle_add_single_import."""
    return Job(
        type=JobType.IMPORT_ADD_SINGLE,
        metadata={
            "source": "imvdb",
            "id": "121779770452",
            "skip_existing": False,
            "initial_status": "discovered",
        },
    )


@pytest.fixture
def metadata_enrich_job():
    """Create a job for handle_metadata_enrich."""
    return Job(
        type=JobType.METADATA_ENRICH,
        metadata={
            "video_ids": [1],
            "sources": ["imvdb"],
            "overwrite": False,
        },
    )


class TestAddSingleImportArtistLinking:
    """Tests for artist linking in handle_add_single_import."""

    @pytest.mark.asyncio
    async def test_links_primary_artists_from_imvdb(
        self, add_single_import_job, mock_repository, mock_config, imvdb_video_response
    ):
        """Test that primary artists are linked from IMVDb response."""
        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.api.imvdb_client.IMVDbClient") as MockIMVDbClient,
        ):
            # Setup mocks
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repository)
            mock_fuzzbin.get_config = MagicMock(return_value=mock_config)

            # Mock IMVDb client
            mock_client = AsyncMock()
            mock_video = MagicMock()
            mock_video.id = 121779770452
            mock_video.song_title = "Blurred Lines"
            mock_video.year = 2013

            # Primary artist
            mock_artist = MagicMock()
            mock_artist.name = "Robin Thicke"
            mock_video.artists = [mock_artist]

            # Featured artists
            featured1 = MagicMock()
            featured1.name = "T.I."
            featured2 = MagicMock()
            featured2.name = "Pharrell Williams"
            mock_video.featured_artists = [featured1, featured2]

            # Directors
            mock_director = MagicMock()
            mock_director.entity_name = "Diane Martel"
            mock_video.directors = [mock_director]

            mock_video.sources = []

            mock_client.get_video = AsyncMock(return_value=mock_video)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockIMVDbClient.from_config = MagicMock(return_value=mock_client)

            # Run handler
            await handle_add_single_import(add_single_import_job)

            # Verify primary artist was linked
            primary_calls = [
                call
                for call in mock_repository.link_video_artist.call_args_list
                if call.kwargs.get("role") == "primary"
            ]
            assert len(primary_calls) == 1
            assert primary_calls[0].kwargs["position"] == 0

    @pytest.mark.asyncio
    async def test_links_featured_artists_from_imvdb(
        self, add_single_import_job, mock_repository, mock_config, imvdb_video_response
    ):
        """Test that featured artists are linked from IMVDb response."""
        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.api.imvdb_client.IMVDbClient") as MockIMVDbClient,
        ):
            # Setup mocks
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repository)
            mock_fuzzbin.get_config = MagicMock(return_value=mock_config)

            # Mock IMVDb client
            mock_client = AsyncMock()
            mock_video = MagicMock()
            mock_video.id = 121779770452
            mock_video.song_title = "Blurred Lines"
            mock_video.year = 2013

            # Primary artist
            mock_artist = MagicMock()
            mock_artist.name = "Robin Thicke"
            mock_video.artists = [mock_artist]

            # Featured artists
            featured1 = MagicMock()
            featured1.name = "T.I."
            featured2 = MagicMock()
            featured2.name = "Pharrell Williams"
            mock_video.featured_artists = [featured1, featured2]

            mock_video.directors = []
            mock_video.sources = []

            mock_client.get_video = AsyncMock(return_value=mock_video)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockIMVDbClient.from_config = MagicMock(return_value=mock_client)

            # Run handler
            await handle_add_single_import(add_single_import_job)

            # Verify featured artists were linked
            featured_calls = [
                call
                for call in mock_repository.link_video_artist.call_args_list
                if call.kwargs.get("role") == "featured"
            ]
            assert len(featured_calls) == 2

            # Verify positions start at 0 for featured artists
            positions = [call.kwargs["position"] for call in featured_calls]
            assert positions == [0, 1]

    @pytest.mark.asyncio
    async def test_upsert_artist_called_for_all_artists(
        self, add_single_import_job, mock_repository, mock_config
    ):
        """Test that upsert_artist is called for primary and featured artists."""
        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.api.imvdb_client.IMVDbClient") as MockIMVDbClient,
        ):
            # Setup mocks
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repository)
            mock_fuzzbin.get_config = MagicMock(return_value=mock_config)

            # Mock IMVDb client
            mock_client = AsyncMock()
            mock_video = MagicMock()
            mock_video.id = 121779770452
            mock_video.song_title = "Blurred Lines"
            mock_video.year = 2013

            # Artists
            mock_artist = MagicMock()
            mock_artist.name = "Robin Thicke"
            mock_video.artists = [mock_artist]

            featured1 = MagicMock()
            featured1.name = "T.I."
            featured2 = MagicMock()
            featured2.name = "Pharrell Williams"
            mock_video.featured_artists = [featured1, featured2]

            mock_video.directors = []
            mock_video.sources = []

            mock_client.get_video = AsyncMock(return_value=mock_video)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockIMVDbClient.from_config = MagicMock(return_value=mock_client)

            # Run handler
            await handle_add_single_import(add_single_import_job)

            # Verify upsert_artist was called for all 3 artists
            artist_names = [
                call.kwargs["name"] for call in mock_repository.upsert_artist.call_args_list
            ]
            assert "Robin Thicke" in artist_names
            assert "T.I." in artist_names
            assert "Pharrell Williams" in artist_names

    @pytest.mark.asyncio
    async def test_no_artist_linking_when_skipped(
        self, add_single_import_job, mock_repository, mock_config
    ):
        """Test that artists are not linked when video already exists."""
        # Make repository return existing video
        mock_repository.get_video_by_imvdb_id = AsyncMock(return_value={"id": 99})

        # Enable skip_existing
        add_single_import_job.metadata["skip_existing"] = True

        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.api.imvdb_client.IMVDbClient") as MockIMVDbClient,
        ):
            # Setup mocks
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repository)
            mock_fuzzbin.get_config = MagicMock(return_value=mock_config)

            # Mock IMVDb client
            mock_client = AsyncMock()
            mock_video = MagicMock()
            mock_video.id = 121779770452
            mock_video.sources = []

            mock_client.get_video = AsyncMock(return_value=mock_video)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            MockIMVDbClient.from_config = MagicMock(return_value=mock_client)

            # Run handler
            await handle_add_single_import(add_single_import_job)

            # Verify no artist linking occurred
            mock_repository.link_video_artist.assert_not_called()


class TestMetadataEnrichArtistLinking:
    """Tests for artist linking in handle_metadata_enrich."""

    @pytest.mark.asyncio
    async def test_enrichment_links_artists_from_imvdb(
        self, metadata_enrich_job, mock_repository, mock_config
    ):
        """Test that enrichment links artists from IMVDb search results."""
        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.api.imvdb_client.IMVDbClient") as MockIMVDbClient,
        ):
            # Setup mocks
            mock_fuzzbin.get_config = MagicMock(return_value=mock_config)
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repository)

            # Mock IMVDb client
            mock_client = AsyncMock()

            # Search result
            mock_search_result = MagicMock()
            mock_search_result.id = 121779770452
            mock_client.search_videos = AsyncMock(return_value=[mock_search_result])

            # Full video data
            mock_video = MagicMock()
            mock_video.id = 121779770452
            mock_video.year = 2013

            # Directors
            mock_director = MagicMock()
            mock_director.name = "Diane Martel"
            mock_video.directors = [mock_director]

            # Primary artist
            mock_artist = MagicMock()
            mock_artist.name = "Robin Thicke"
            mock_video.artists = [mock_artist]

            # Featured artists
            featured1 = MagicMock()
            featured1.name = "T.I."
            featured2 = MagicMock()
            featured2.name = "Pharrell Williams"
            mock_video.featured_artists = [featured1, featured2]

            mock_client.get_video = AsyncMock(return_value=mock_video)
            mock_client.aclose = AsyncMock()
            MockIMVDbClient.from_config = MagicMock(return_value=mock_client)

            # Run handler
            await handle_metadata_enrich(metadata_enrich_job)

            # Verify existing artist links were cleared
            mock_repository.unlink_all_video_artists.assert_called_once_with(1)

            # Verify primary artist was linked
            primary_calls = [
                call
                for call in mock_repository.link_video_artist.call_args_list
                if call.kwargs.get("role") == "primary"
            ]
            assert len(primary_calls) == 1

            # Verify featured artists were linked
            featured_calls = [
                call
                for call in mock_repository.link_video_artist.call_args_list
                if call.kwargs.get("role") == "featured"
            ]
            assert len(featured_calls) == 2

    @pytest.mark.asyncio
    async def test_enrichment_clears_existing_artist_links(
        self, metadata_enrich_job, mock_repository, mock_config
    ):
        """Test that enrichment clears existing artist links before re-linking."""
        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.api.imvdb_client.IMVDbClient") as MockIMVDbClient,
        ):
            # Setup mocks
            mock_fuzzbin.get_config = MagicMock(return_value=mock_config)
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repository)

            # Mock IMVDb client
            mock_client = AsyncMock()

            mock_search_result = MagicMock()
            mock_search_result.id = 121779770452
            mock_client.search_videos = AsyncMock(return_value=[mock_search_result])

            mock_video = MagicMock()
            mock_video.id = 121779770452
            mock_video.year = 2013
            mock_video.directors = []

            mock_artist = MagicMock()
            mock_artist.name = "Robin Thicke"
            mock_video.artists = [mock_artist]
            mock_video.featured_artists = []

            mock_client.get_video = AsyncMock(return_value=mock_video)
            mock_client.aclose = AsyncMock()
            MockIMVDbClient.from_config = MagicMock(return_value=mock_client)

            # Run handler
            await handle_metadata_enrich(metadata_enrich_job)

            # Verify unlink was called before linking
            mock_repository.unlink_all_video_artists.assert_called_once()
            # And that link was called after
            mock_repository.link_video_artist.assert_called()

    @pytest.mark.asyncio
    async def test_no_artist_linking_when_no_imvdb_match(
        self, metadata_enrich_job, mock_repository, mock_config
    ):
        """Test that no artist linking occurs when IMVDb search returns no results."""
        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.api.imvdb_client.IMVDbClient") as MockIMVDbClient,
        ):
            # Setup mocks
            mock_fuzzbin.get_config = MagicMock(return_value=mock_config)
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repository)

            # Mock IMVDb client with empty search results
            mock_client = AsyncMock()
            mock_client.search_videos = AsyncMock(return_value=[])
            mock_client.aclose = AsyncMock()
            MockIMVDbClient.from_config = MagicMock(return_value=mock_client)

            # Run handler
            await handle_metadata_enrich(metadata_enrich_job)

            # Verify no artist linking occurred
            mock_repository.unlink_all_video_artists.assert_not_called()
            mock_repository.link_video_artist.assert_not_called()

    @pytest.mark.asyncio
    async def test_featured_artist_positions_start_at_zero(
        self, metadata_enrich_job, mock_repository, mock_config
    ):
        """Test that featured artists have positions starting at 0."""
        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.api.imvdb_client.IMVDbClient") as MockIMVDbClient,
        ):
            # Setup mocks
            mock_fuzzbin.get_config = MagicMock(return_value=mock_config)
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repository)

            # Mock IMVDb client
            mock_client = AsyncMock()

            mock_search_result = MagicMock()
            mock_search_result.id = 121779770452
            mock_client.search_videos = AsyncMock(return_value=[mock_search_result])

            mock_video = MagicMock()
            mock_video.id = 121779770452
            mock_video.year = 2013
            mock_video.directors = []
            mock_video.artists = []

            # Three featured artists
            featured1 = MagicMock()
            featured1.name = "Featured 1"
            featured2 = MagicMock()
            featured2.name = "Featured 2"
            featured3 = MagicMock()
            featured3.name = "Featured 3"
            mock_video.featured_artists = [featured1, featured2, featured3]

            mock_client.get_video = AsyncMock(return_value=mock_video)
            mock_client.aclose = AsyncMock()
            MockIMVDbClient.from_config = MagicMock(return_value=mock_client)

            # Run handler
            await handle_metadata_enrich(metadata_enrich_job)

            # Verify featured artists have positions 0, 1, 2
            featured_calls = [
                call
                for call in mock_repository.link_video_artist.call_args_list
                if call.kwargs.get("role") == "featured"
            ]
            positions = [call.kwargs["position"] for call in featured_calls]
            assert positions == [0, 1, 2]
