"""Unit tests for SearchService."""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from fuzzbin.services.search_service import (
    Facet,
    FacetedSearchResults,
    FacetValue,
    SearchResult,
    SearchResults,
    SearchService,
    SearchSuggestions,
)


@pytest.fixture
def mock_repository():
    """Mock VideoRepository for testing."""
    repository = AsyncMock()

    # Query builder with method chaining
    query = MagicMock()
    query.where_title = MagicMock(return_value=query)
    query.where_artist = MagicMock(return_value=query)
    query.where_album = MagicMock(return_value=query)
    query.where_year = MagicMock(return_value=query)
    query.where_status = MagicMock(return_value=query)
    query.where_collection = MagicMock(return_value=query)
    query.where_tag = MagicMock(return_value=query)
    query.search = MagicMock(return_value=query)
    query.order_by = MagicMock(return_value=query)
    query.limit = MagicMock(return_value=query)
    query.offset = MagicMock(return_value=query)
    query.include_deleted = MagicMock(return_value=query)
    query.execute = AsyncMock(return_value=[
        {"id": 1, "title": "Test Video", "artist": "Test Artist"},
        {"id": 2, "title": "Another Video", "artist": "Another Artist"},
    ])
    query.count = AsyncMock(return_value=100)
    repository.query = MagicMock(return_value=query)

    # Video relationships
    repository.get_video_artists = AsyncMock(return_value=[{"id": 1, "name": "Test Artist"}])
    repository.get_video_collections = AsyncMock(return_value=[])
    repository.get_video_tags = AsyncMock(return_value=[{"id": 1, "name": "rock"}])

    # Stats - these need to return proper values
    repository.get_video_count = AsyncMock(return_value=100)
    repository.get_artist_count = AsyncMock(return_value=50)
    repository.get_collection_count = AsyncMock(return_value=10)
    repository.get_tag_count = AsyncMock(return_value=25)

    # List methods for cross-entity search
    repository.list_artists = AsyncMock(return_value=[
        {"id": 1, "name": "Test Artist", "video_count": 20},
        {"id": 2, "name": "Another Artist", "video_count": 15},
    ])
    repository.list_collections = AsyncMock(return_value=[
        {"id": 1, "name": "Favorites", "video_count": 10},
    ])
    repository.list_tags = AsyncMock(return_value=[
        {"id": 1, "name": "rock", "video_count": 30},
        {"id": 2, "name": "pop", "video_count": 25},
    ])

    # Status counts for facets
    repository.get_status_counts = AsyncMock(return_value={
        "discovered": 50,
        "downloaded": 30,
        "organized": 20,
    })
    repository.get_year_counts = AsyncMock(return_value={
        2023: 40,
        2022: 35,
        2021: 25,
    })

    # Suggestions
    repository.get_unique_titles = AsyncMock(return_value=["Test Title", "Test Video"])
    repository.get_unique_artists = AsyncMock(return_value=["Test Artist"])
    repository.get_unique_albums = AsyncMock(return_value=["Test Album"])

    return repository


@pytest.fixture
def search_service(mock_repository):
    """Create SearchService instance for testing."""
    return SearchService(repository=mock_repository)


# ==================== Basic Search Tests ====================


class TestSearchServiceBasic:
    """Tests for basic search operations."""

    @pytest.mark.asyncio
    async def test_search_videos_by_query(self, search_service, mock_repository):
        """Test searching videos by text query."""
        results = await search_service.search_videos(query="test")

        assert isinstance(results, dict)
        assert results["total"] == 100
        assert len(results["items"]) == 2
        assert results["page"] == 1

    @pytest.mark.asyncio
    async def test_search_videos_pagination(self, search_service, mock_repository):
        """Test search pagination."""
        results = await search_service.search_videos(
            query="test",
            page=2,
            page_size=10,
        )

        assert isinstance(results, dict)
        assert results["page"] == 2
        assert results["page_size"] == 10
        query = mock_repository.query.return_value
        query.limit.assert_called_with(10)
        # offset should be (2-1)*10 = 10
        query.offset.assert_called_with(10)

    @pytest.mark.asyncio
    async def test_search_videos_include_deleted(self, search_service, mock_repository):
        """Test including deleted videos in search."""
        results = await search_service.search_videos(
            query="test",
            include_deleted=True,
        )

        assert isinstance(results, dict)
        query = mock_repository.query.return_value
        query.include_deleted.assert_called()


# ==================== Cross-Entity Search Tests ====================


class TestSearchServiceCrossEntity:
    """Tests for cross-entity search."""

    @pytest.mark.asyncio
    async def test_search_all_entities(self, search_service, mock_repository):
        """Test searching across all entities."""
        results = await search_service.search_all(query="test")

        assert isinstance(results, SearchResults)
        assert results.query == "test"
        # Should have videos from search
        assert len(results.videos) > 0


# ==================== Faceted Search Tests ====================


class TestSearchServiceFaceted:
    """Tests for faceted search."""

    @pytest.mark.asyncio
    async def test_search_with_facets(self, search_service, mock_repository):
        """Test faceted search returns facets."""
        results = await search_service.search_with_facets(query="test")

        assert isinstance(results, FacetedSearchResults)
        assert results.total > 0
        assert isinstance(results.facets, list)

    @pytest.mark.asyncio
    async def test_search_with_facets_has_items(self, search_service, mock_repository):
        """Test that faceted search returns items."""
        results = await search_service.search_with_facets(query="test")

        assert isinstance(results.items, list)
        assert len(results.items) > 0


# ==================== Suggestions Tests ====================


class TestSearchServiceSuggestions:
    """Tests for search suggestions."""

    @pytest.mark.asyncio
    async def test_get_suggestions_for_query(self, search_service, mock_repository):
        """Test getting autocomplete suggestions."""
        suggestions = await search_service.get_suggestions(query="test")

        assert isinstance(suggestions, SearchSuggestions)
        assert suggestions.query == "test"

    @pytest.mark.asyncio
    async def test_suggestions_has_titles(self, search_service, mock_repository):
        """Test that suggestions include titles."""
        suggestions = await search_service.get_suggestions(query="test")

        assert hasattr(suggestions, "titles")
        assert isinstance(suggestions.titles, list)


# ==================== Cached Aggregations Tests ====================


class TestSearchServiceCached:
    """Tests for cached aggregations."""

    @pytest.mark.asyncio
    async def test_get_tag_cloud(self, search_service, mock_repository):
        """Test getting tag cloud."""
        # Mock get_tag_videos for each tag
        mock_repository.get_tag_videos = AsyncMock(return_value=[{"id": 1}])

        tag_cloud = await search_service.get_tag_cloud()

        assert isinstance(tag_cloud, list)

    @pytest.mark.asyncio
    async def test_get_top_artists(self, search_service, mock_repository):
        """Test getting top artists."""
        # Mock get_artist_videos
        mock_repository.get_artist_videos = AsyncMock(return_value=[{"id": 1}])

        artists = await search_service.get_top_artists(limit=10)

        assert isinstance(artists, list)

    @pytest.mark.asyncio
    async def test_get_top_collections(self, search_service, mock_repository):
        """Test getting top collections."""
        # Mock get_collection_videos
        mock_repository.get_collection_videos = AsyncMock(return_value=[{"id": 1}])

        collections = await search_service.get_top_collections(limit=10)

        assert isinstance(collections, list)

    @pytest.mark.asyncio
    async def test_get_library_stats(self, search_service, mock_repository):
        """Test getting library statistics."""
        stats = await search_service.get_library_stats()

        assert isinstance(stats, dict)
        assert "total_videos" in stats


# ==================== Edge Cases ====================


class TestSearchServiceEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_results(self, search_service, mock_repository):
        """Test that empty query returns results."""
        results = await search_service.search_videos(query="")

        assert isinstance(results, dict)
        assert results["total"] > 0

    @pytest.mark.asyncio
    async def test_no_results(self, search_service, mock_repository):
        """Test handling of no search results."""
        mock_repository.query().execute = AsyncMock(return_value=[])
        mock_repository.query().count = AsyncMock(return_value=0)

        results = await search_service.search_videos(query="nonexistent12345")

        assert isinstance(results, dict)
        assert results["total"] == 0
        assert len(results["items"]) == 0

    @pytest.mark.asyncio
    async def test_pagination_handles_page_calculation(self, search_service, mock_repository):
        """Test that pagination calculates correctly."""
        results = await search_service.search_videos(
            query="test",
            page=1,
            page_size=10,
        )

        assert isinstance(results, dict)
        assert "total_pages" in results
        # With 100 total and page_size=10, should be 10 pages
        assert results["total_pages"] == 10
