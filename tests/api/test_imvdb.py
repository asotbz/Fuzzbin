"""Tests for IMVDb API endpoints."""

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from fuzzbin.api.imvdb_client import IMVDbClient
from fuzzbin.parsers.imvdb_models import (
    IMVDbArtist,
    IMVDbDirector,
    IMVDbEntitySearchResponse,
    IMVDbEntitySearchResult,
    IMVDbEntityVideo,
    IMVDbPagination,
    IMVDbSource,
    IMVDbVideo,
    IMVDbVideoSearchResult,
)
from fuzzbin.web.dependencies import get_imvdb_client


class TestIMVDbVideoSearch:
    """Tests for IMVDb video search endpoint."""

    @pytest.fixture
    def mock_video_search_result(self):
        """Mock video search results from IMVDbClient."""
        return IMVDbVideoSearchResult(
            pagination=IMVDbPagination(
                total_results=2,
                current_page=1,
                per_page=25,
                total_pages=1,
            ),
            results=[
                IMVDbEntityVideo(
                    id=121779770452,
                    song_title="Blurred Lines",
                    song_slug="blurred-lines",
                    url="https://imvdb.com/video/robin-thicke/blurred-lines",
                    year=2013,
                    production_status="r",
                    multiple_versions=False,
                    version_number=1,
                    is_imvdb_pick=False,
                    verified_credits=False,
                    artists=[
                        IMVDbArtist(
                            name="Robin Thicke",
                            slug="robin-thicke",
                            url="https://imvdb.com/n/robin-thicke",
                        )
                    ],
                    image={
                        "o": "https://s3.amazonaws.com/images.imvdb.com/video/test_ov.jpg",
                        "t": "https://s3.amazonaws.com/images.imvdb.com/video/test_tv.jpg",
                    },
                ),
                IMVDbEntityVideo(
                    id=121779770453,
                    song_title="Give It 2 U",
                    song_slug="give-it-2-u",
                    url="https://imvdb.com/video/robin-thicke/give-it-2-u",
                    year=2013,
                    production_status="r",
                    multiple_versions=False,
                    version_number=1,
                    is_imvdb_pick=False,
                    verified_credits=True,
                    artists=[
                        IMVDbArtist(
                            name="Robin Thicke",
                            slug="robin-thicke",
                            url="https://imvdb.com/n/robin-thicke",
                        )
                    ],
                    image=None,
                ),
            ],
        )

    @pytest.fixture
    def mock_imvdb_client(self, mock_video_search_result):
        """Create a mock IMVDb client."""
        mock_client = MagicMock(spec=IMVDbClient)
        mock_client.search_videos = AsyncMock(return_value=mock_video_search_result)
        mock_client.search_entities = AsyncMock()
        mock_client.get_video = AsyncMock()
        mock_client.get_entity = AsyncMock()
        return mock_client

    def test_search_videos_success(
        self, test_app: TestClient, mock_imvdb_client, mock_video_search_result
    ):
        """Test successful video search."""

        # Override the dependency
        async def override_get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
            yield mock_imvdb_client

        test_app.app.dependency_overrides[get_imvdb_client] = override_get_imvdb_client

        try:
            response = test_app.get(
                "/imvdb/search/videos",
                params={
                    "artist": "Robin Thicke",
                    "track": "Blurred Lines",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_results"] == 2
            assert data["current_page"] == 1
            assert data["per_page"] == 25
            assert data["total_pages"] == 1
            assert len(data["results"]) == 2
            assert data["results"][0]["id"] == 121779770452
            assert data["results"][0]["song_title"] == "Blurred Lines"
            assert data["results"][0]["artists"][0]["name"] == "Robin Thicke"
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)

    def test_search_videos_missing_artist(self, test_app: TestClient, mock_imvdb_client):
        """Test search endpoint requires artist parameter."""

        async def override_get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
            yield mock_imvdb_client

        test_app.app.dependency_overrides[get_imvdb_client] = override_get_imvdb_client

        try:
            response = test_app.get(
                "/imvdb/search/videos",
                params={"track": "Blurred Lines"},
            )
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)

    def test_search_videos_missing_track(self, test_app: TestClient, mock_imvdb_client):
        """Test search endpoint requires track parameter."""

        async def override_get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
            yield mock_imvdb_client

        test_app.app.dependency_overrides[get_imvdb_client] = override_get_imvdb_client

        try:
            response = test_app.get(
                "/imvdb/search/videos",
                params={"artist": "Robin Thicke"},
            )
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)

    def test_search_videos_pagination_params(
        self, test_app: TestClient, mock_imvdb_client, mock_video_search_result
    ):
        """Test search endpoint accepts pagination parameters."""

        async def override_get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
            yield mock_imvdb_client

        test_app.app.dependency_overrides[get_imvdb_client] = override_get_imvdb_client

        try:
            response = test_app.get(
                "/imvdb/search/videos",
                params={
                    "artist": "Robin Thicke",
                    "track": "Blurred Lines",
                    "page": 2,
                    "per_page": 50,
                },
            )

            assert response.status_code == 200
            # Verify the client was called with correct params
            mock_imvdb_client.search_videos.assert_called_once_with(
                artist="Robin Thicke",
                track_title="Blurred Lines",
                page=2,
                per_page=50,
            )
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)

    def test_search_videos_per_page_max(self, test_app: TestClient, mock_imvdb_client):
        """Test search endpoint validates per_page max value."""

        async def override_get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
            yield mock_imvdb_client

        test_app.app.dependency_overrides[get_imvdb_client] = override_get_imvdb_client

        try:
            response = test_app.get(
                "/imvdb/search/videos",
                params={
                    "artist": "Robin Thicke",
                    "track": "Blurred Lines",
                    "per_page": 101,  # Exceeds max of 100
                },
            )
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)


class TestIMVDbEntitySearch:
    """Tests for IMVDb entity search endpoint."""

    @pytest.fixture
    def mock_entity_search_result(self):
        """Mock entity search results from IMVDbClient."""
        return IMVDbEntitySearchResponse(
            pagination=IMVDbPagination(
                total_results=3,
                current_page=1,
                per_page=25,
                total_pages=1,
            ),
            results=[
                IMVDbEntitySearchResult(
                    id=12345,
                    name="Robin Thicke",
                    slug="robin-thicke",
                    url="https://imvdb.com/n/robin-thicke",
                    discogs_id=456789,
                    byline="R&B Singer",
                    bio="Robin Alan Thicke is an American singer...",
                    image="https://s3.amazonaws.com/images.imvdb.com/entity/robin-thicke.jpg",
                    artist_video_count=25,
                    featured_video_count=3,
                ),
                IMVDbEntitySearchResult(
                    id=67890,
                    name="Diane Martel",
                    slug="diane-martel",
                    url="https://imvdb.com/n/diane-martel",
                    discogs_id=None,
                    byline="Director",
                    bio="Diane Martel is a music video director...",
                    image=None,
                    artist_video_count=0,
                    featured_video_count=0,
                ),
            ],
        )

    @pytest.fixture
    def mock_imvdb_client(self, mock_entity_search_result):
        """Create a mock IMVDb client."""
        mock_client = MagicMock(spec=IMVDbClient)
        mock_client.search_entities = AsyncMock(return_value=mock_entity_search_result)
        mock_client.search_videos = AsyncMock()
        mock_client.get_video = AsyncMock()
        mock_client.get_entity = AsyncMock()
        return mock_client

    def test_search_entities_success(self, test_app: TestClient, mock_imvdb_client):
        """Test successful entity search."""

        async def override_get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
            yield mock_imvdb_client

        test_app.app.dependency_overrides[get_imvdb_client] = override_get_imvdb_client

        try:
            response = test_app.get(
                "/imvdb/search/entities",
                params={"q": "Robin Thicke"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_results"] == 3
            assert len(data["results"]) == 2
            assert data["results"][0]["id"] == 12345
            assert data["results"][0]["name"] == "Robin Thicke"
            assert data["results"][0]["discogs_id"] == 456789
            assert data["results"][0]["artist_video_count"] == 25
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)

    def test_search_entities_missing_query(self, test_app: TestClient, mock_imvdb_client):
        """Test search endpoint requires query parameter."""

        async def override_get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
            yield mock_imvdb_client

        test_app.app.dependency_overrides[get_imvdb_client] = override_get_imvdb_client

        try:
            response = test_app.get("/imvdb/search/entities")
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)


class TestIMVDbGetVideo:
    """Tests for IMVDb get video endpoint."""

    @pytest.fixture
    def mock_video_detail(self):
        """Mock video detail from IMVDbClient."""
        return IMVDbVideo(
            id=121779770452,
            song_title="Blurred Lines",
            song_slug="blurred-lines",
            url="https://imvdb.com/video/robin-thicke/blurred-lines",
            year=2013,
            production_status="r",
            multiple_versions=False,
            version_number=1,
            is_imvdb_pick=False,
            verified_credits=False,
            artists=[
                IMVDbArtist(
                    name="Robin Thicke",
                    slug="robin-thicke",
                    url="https://imvdb.com/n/robin-thicke",
                )
            ],
            featured_artists=[
                IMVDbArtist(
                    name="T.I.",
                    slug="ti",
                    url="https://imvdb.com/n/ti",
                ),
                IMVDbArtist(
                    name="Pharrell Williams",
                    slug="pharrell-williams",
                    url="https://imvdb.com/n/pharrell-williams",
                ),
            ],
            sources=[
                IMVDbSource(
                    source="youtube",
                    source_slug="youtube",
                    source_data="zwT6DZCQi9k",
                    is_primary=True,
                ),
                IMVDbSource(
                    source="vimeo",
                    source_slug="vimeo",
                    source_data=64611906,
                    is_primary=False,
                ),
            ],
            directors=[
                IMVDbDirector(
                    position_name="Director",
                    position_code="dir",
                    entity_name="Diane Martel",
                    entity_slug="diane-martel",
                    entity_id=31567,
                    entity_url="https://imvdb.com/n/diane-martel",
                    position_notes=None,
                    position_id=31567,
                )
            ],
            image={
                "o": "https://s3.amazonaws.com/images.imvdb.com/video/test_ov.jpg",
                "t": "https://s3.amazonaws.com/images.imvdb.com/video/test_tv.jpg",
            },
            credits={
                "total_credits": 21,
                "crew": [
                    {
                        "position_name": "Director",
                        "position_code": "dir",
                        "entity_name": "Diane Martel",
                        "entity_slug": "diane-martel",
                        "entity_id": 31567,
                        "entity_url": "https://imvdb.com/n/diane-martel",
                        "position_notes": None,
                        "position_id": 31567,
                    }
                ],
            },
        )

    @pytest.fixture
    def mock_imvdb_client(self, mock_video_detail):
        """Create a mock IMVDb client."""
        mock_client = MagicMock(spec=IMVDbClient)
        mock_client.get_video = AsyncMock(return_value=mock_video_detail)
        mock_client.search_videos = AsyncMock()
        mock_client.search_entities = AsyncMock()
        mock_client.get_entity = AsyncMock()
        return mock_client

    def test_get_video_success(self, test_app: TestClient, mock_imvdb_client, mock_video_detail):
        """Test successful video retrieval."""

        async def override_get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
            yield mock_imvdb_client

        test_app.app.dependency_overrides[get_imvdb_client] = override_get_imvdb_client

        try:
            response = test_app.get("/imvdb/videos/121779770452")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 121779770452
            assert data["song_title"] == "Blurred Lines"
            assert data["year"] == 2013
            assert len(data["artists"]) == 1
            assert data["artists"][0]["name"] == "Robin Thicke"
            assert len(data["featured_artists"]) == 2
            assert data["featured_artists"][0]["name"] == "T.I."
            assert len(data["sources"]) == 2
            assert data["sources"][0]["source"] == "youtube"
            assert data["sources"][0]["source_data"] == "zwT6DZCQi9k"
            assert len(data["directors"]) == 1
            assert data["directors"][0]["entity_name"] == "Diane Martel"
            assert data["credits"]["total_credits"] == 21
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)

    def test_get_video_invalid_id(self, test_app: TestClient, mock_imvdb_client):
        """Test get video with invalid ID type."""

        async def override_get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
            yield mock_imvdb_client

        test_app.app.dependency_overrides[get_imvdb_client] = override_get_imvdb_client

        try:
            response = test_app.get("/imvdb/videos/not-a-number")
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)


class TestIMVDbGetEntity:
    """Tests for IMVDb get entity endpoint."""

    @pytest.fixture
    def mock_entity_detail(self):
        """Mock entity detail from IMVDbClient."""
        # Create a mock object that has the structure expected by the route
        mock_entity = MagicMock()
        mock_entity.id = 12345
        mock_entity.name = "Robin Thicke"
        mock_entity.slug = "robin-thicke"
        mock_entity.url = "https://imvdb.com/n/robin-thicke"
        mock_entity.discogs_id = 456789
        mock_entity.byline = "R&B Singer"
        mock_entity.bio = "Robin Alan Thicke is an American singer..."
        mock_entity.image = "https://s3.amazonaws.com/images.imvdb.com/entity/robin-thicke.jpg"
        mock_entity.artist_video_count = 25
        mock_entity.featured_video_count = 3

        # Mock artist_videos
        mock_artist_videos = MagicMock()
        mock_artist_videos.total_videos = 25
        mock_video = MagicMock()
        mock_video.id = 121779770452
        mock_video.song_title = "Blurred Lines"
        mock_video.song_slug = "blurred-lines"
        mock_video.url = "https://imvdb.com/video/robin-thicke/blurred-lines"
        mock_video.production_status = "r"
        mock_video.year = 2013
        mock_video.multiple_versions = False
        mock_video.version_name = None
        mock_video.version_number = 1
        mock_video.is_imvdb_pick = False
        mock_video.aspect_ratio = None
        mock_video.verified_credits = False

        mock_artist = MagicMock()
        mock_artist.name = "Robin Thicke"
        mock_artist.slug = "robin-thicke"
        mock_artist.url = "https://imvdb.com/n/robin-thicke"
        mock_video.artists = [mock_artist]
        mock_video.image = {"t": "https://example.com/thumb.jpg"}

        mock_artist_videos.videos = [mock_video]
        mock_entity.artist_videos = mock_artist_videos

        # Mock featured_videos
        mock_featured = MagicMock()
        mock_featured.total_videos = 3
        mock_featured.videos = []
        mock_entity.featured_videos = mock_featured

        return mock_entity

    @pytest.fixture
    def mock_imvdb_client(self, mock_entity_detail):
        """Create a mock IMVDb client."""
        mock_client = MagicMock(spec=IMVDbClient)
        mock_client.get_entity = AsyncMock(return_value=mock_entity_detail)
        mock_client.search_videos = AsyncMock()
        mock_client.search_entities = AsyncMock()
        mock_client.get_video = AsyncMock()
        return mock_client

    def test_get_entity_success(self, test_app: TestClient, mock_imvdb_client, mock_entity_detail):
        """Test successful entity retrieval."""

        async def override_get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
            yield mock_imvdb_client

        test_app.app.dependency_overrides[get_imvdb_client] = override_get_imvdb_client

        try:
            response = test_app.get("/imvdb/entities/12345")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 12345
            assert data["name"] == "Robin Thicke"
            assert data["discogs_id"] == 456789
            assert data["artist_video_count"] == 25
            assert data["featured_video_count"] == 3
            assert data["artist_videos"]["total_videos"] == 25
            assert len(data["artist_videos"]["videos"]) == 1
            assert data["artist_videos"]["videos"][0]["song_title"] == "Blurred Lines"
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)

    def test_get_entity_invalid_id(self, test_app: TestClient, mock_imvdb_client):
        """Test get entity with invalid ID type."""

        async def override_get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
            yield mock_imvdb_client

        test_app.app.dependency_overrides[get_imvdb_client] = override_get_imvdb_client

        try:
            response = test_app.get("/imvdb/entities/not-a-number")
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)


class TestIMVDbServiceUnavailable:
    """Tests for IMVDb service unavailable scenarios."""

    def test_search_videos_service_unavailable(self, test_app: TestClient):
        """Test search when IMVDb is not configured."""
        from fastapi import HTTPException

        async def override_unavailable() -> AsyncGenerator[IMVDbClient, None]:
            raise HTTPException(status_code=503, detail="IMVDb API is not configured")
            yield  # Never reached, but makes it a generator

        test_app.app.dependency_overrides[get_imvdb_client] = override_unavailable

        try:
            response = test_app.get(
                "/imvdb/search/videos",
                params={
                    "artist": "Robin Thicke",
                    "track": "Blurred Lines",
                },
            )

            assert response.status_code == 503
            assert "not configured" in response.json()["detail"]
        finally:
            test_app.app.dependency_overrides.pop(get_imvdb_client, None)
