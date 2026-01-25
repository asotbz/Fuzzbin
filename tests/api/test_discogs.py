"""Tests for Discogs API endpoints."""

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from fuzzbin.api.discogs_client import DiscogsClient
from fuzzbin.web.dependencies import get_discogs_client


class TestDiscogsSearch:
    """Tests for Discogs search endpoint."""

    @pytest.fixture
    def mock_search_result(self):
        """Mock search results from DiscogsClient."""
        return {
            "pagination": {
                "page": 1,
                "pages": 2,
                "per_page": 50,
                "items": 75,
                "urls": {
                    "next": "https://api.discogs.com/database/search?page=2",
                },
            },
            "results": [
                {
                    "id": 13814,
                    "type": "master",
                    "master_id": 13814,
                    "master_url": "https://api.discogs.com/masters/13814",
                    "uri": "/master/13814-Nirvana-Nevermind",
                    "title": "Nirvana - Nevermind",
                    "country": "US",
                    "year": "1991",
                    "format": ["CD", "Album"],
                    "label": ["DGC", "Geffen Records"],
                    "genre": ["Rock"],
                    "style": ["Grunge"],
                    "catno": "DGCD-24425",
                    "barcode": ["7 20642-44252-2"],
                    "thumb": "https://i.discogs.com/thumb.jpg",
                    "cover_image": "https://i.discogs.com/cover.jpg",
                    "resource_url": "https://api.discogs.com/masters/13814",
                    "community": {"want": 519634, "have": 383067},
                },
                {
                    "id": 42473,
                    "type": "master",
                    "master_id": 42473,
                    "master_url": "https://api.discogs.com/masters/42473",
                    "uri": "/master/42473-Nirvana-From-The-Muddy-Banks-Of-The-Wishkah",
                    "title": "Nirvana - From The Muddy Banks Of The Wishkah",
                    "country": "US",
                    "year": "1996",
                    "format": ["CD", "Album"],
                    "label": ["DGC"],
                    "genre": ["Rock"],
                    "style": ["Grunge"],
                    "catno": "DGCD-25105",
                    "barcode": [],
                    "thumb": "https://i.discogs.com/thumb2.jpg",
                    "cover_image": "https://i.discogs.com/cover2.jpg",
                    "resource_url": "https://api.discogs.com/masters/42473",
                    "community": {"want": 16014, "have": 31641},
                },
            ],
        }

    @pytest.fixture
    def mock_discogs_client(self, mock_search_result):
        """Create a mock Discogs client."""
        mock_client = MagicMock(spec=DiscogsClient)
        mock_client.search = AsyncMock(return_value=mock_search_result)
        mock_client.get_master = AsyncMock()
        mock_client.get_release = AsyncMock()
        mock_client.get_artist_releases = AsyncMock()
        return mock_client

    def test_search_success(self, test_app: TestClient, mock_discogs_client):
        """Test successful release search."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get(
                "/discogs/search",
                params={
                    "artist": "Nirvana",
                    "track": "Smells Like Teen Spirit",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["pagination"]["page"] == 1
            assert data["pagination"]["pages"] == 2
            assert data["pagination"]["items"] == 75
            assert len(data["results"]) == 2
            assert data["results"][0]["id"] == 13814
            assert data["results"][0]["title"] == "Nirvana - Nevermind"
            assert data["results"][0]["year"] == "1991"
            assert "Grunge" in data["results"][0]["style"]
            assert data["results"][0]["community"]["want"] == 519634
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)

    def test_search_with_query(self, test_app: TestClient, mock_discogs_client):
        """Test search with general query parameter."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get(
                "/discogs/search",
                params={"q": "Nirvana Nevermind"},
            )

            assert response.status_code == 200
            mock_discogs_client.search.assert_called_once()
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)

    def test_search_pagination_params(self, test_app: TestClient, mock_discogs_client):
        """Test search with custom pagination parameters."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get(
                "/discogs/search",
                params={
                    "artist": "Nirvana",
                    "page": 2,
                    "per_page": 25,
                },
            )

            assert response.status_code == 200
            mock_discogs_client.search.assert_called_once_with(
                artist="Nirvana",
                track="",
                page=2,
                per_page=25,
            )
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)

    def test_search_per_page_max(self, test_app: TestClient, mock_discogs_client):
        """Test search validates per_page max value."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get(
                "/discogs/search",
                params={
                    "artist": "Nirvana",
                    "per_page": 101,  # Exceeds max of 100
                },
            )
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)


class TestDiscogsGetMaster:
    """Tests for Discogs get master endpoint."""

    @pytest.fixture
    def mock_master_detail(self):
        """Mock master release detail from DiscogsClient."""
        return {
            "id": 13814,
            "main_release": 367273,
            "most_recent_release": 28793456,
            "resource_url": "https://api.discogs.com/masters/13814",
            "uri": "https://www.discogs.com/master/13814-Nirvana-Nevermind",
            "versions_url": "https://api.discogs.com/masters/13814/versions",
            "main_release_url": "https://api.discogs.com/releases/367273",
            "most_recent_release_url": "https://api.discogs.com/releases/28793456",
            "num_for_sale": 4521,
            "lowest_price": 2.50,
            "images": [
                {
                    "type": "primary",
                    "uri": "https://i.discogs.com/full.jpg",
                    "resource_url": "https://api.discogs.com/images/full.jpg",
                    "uri150": "https://i.discogs.com/150.jpg",
                    "width": 600,
                    "height": 600,
                }
            ],
            "genres": ["Rock"],
            "styles": ["Grunge", "Alternative Rock"],
            "year": 1991,
            "tracklist": [
                {
                    "position": "1",
                    "type_": "track",
                    "title": "Smells Like Teen Spirit",
                    "duration": "5:01",
                    "extraartists": [],
                },
                {
                    "position": "2",
                    "type_": "track",
                    "title": "In Bloom",
                    "duration": "4:14",
                    "extraartists": [],
                },
            ],
            "artists": [
                {
                    "id": 125246,
                    "name": "Nirvana",
                    "resource_url": "https://api.discogs.com/artists/125246",
                    "anv": None,
                    "join": None,
                    "role": None,
                    "tracks": None,
                }
            ],
            "title": "Nevermind",
            "data_quality": "Correct",
            "videos": [
                {
                    "uri": "https://www.youtube.com/watch?v=hTWKbfoikeg",
                    "title": "Nirvana - Smells Like Teen Spirit (Official Music Video)",
                    "description": "Official music video",
                    "duration": 301,
                    "embed": True,
                }
            ],
        }

    @pytest.fixture
    def mock_discogs_client(self, mock_master_detail):
        """Create a mock Discogs client."""
        mock_client = MagicMock(spec=DiscogsClient)
        mock_client.get_master = AsyncMock(return_value=mock_master_detail)
        mock_client.search = AsyncMock()
        mock_client.get_release = AsyncMock()
        mock_client.get_artist_releases = AsyncMock()
        return mock_client

    def test_get_master_success(self, test_app: TestClient, mock_discogs_client):
        """Test successful master release retrieval."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get("/discogs/masters/13814")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 13814
            assert data["title"] == "Nevermind"
            assert data["year"] == 1991
            assert data["main_release"] == 367273
            assert "Grunge" in data["styles"]
            assert len(data["tracklist"]) == 2
            assert data["tracklist"][0]["title"] == "Smells Like Teen Spirit"
            assert len(data["artists"]) == 1
            assert data["artists"][0]["name"] == "Nirvana"
            assert data["num_for_sale"] == 4521
            assert data["lowest_price"] == 2.50
            assert len(data["videos"]) == 1
            assert "youtube.com" in data["videos"][0]["uri"]
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)

    def test_get_master_invalid_id(self, test_app: TestClient, mock_discogs_client):
        """Test get master with invalid ID type."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get("/discogs/masters/not-a-number")
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)


class TestDiscogsGetRelease:
    """Tests for Discogs get release endpoint."""

    @pytest.fixture
    def mock_release_detail(self):
        """Mock release detail from DiscogsClient."""
        return {
            "id": 367273,
            "status": "Accepted",
            "year": 1991,
            "resource_url": "https://api.discogs.com/releases/367273",
            "uri": "https://www.discogs.com/release/367273-Nirvana-Nevermind",
            "artists": [
                {
                    "id": 125246,
                    "name": "Nirvana",
                    "resource_url": "https://api.discogs.com/artists/125246",
                    "anv": None,
                    "join": None,
                    "role": None,
                    "tracks": None,
                }
            ],
            "artists_sort": "Nirvana",
            "labels": [
                {
                    "id": 1866,
                    "name": "DGC",
                    "catno": "DGCD-24425",
                    "entity_type": "1",
                    "entity_type_name": "Label",
                    "resource_url": "https://api.discogs.com/labels/1866",
                }
            ],
            "formats": [
                {
                    "name": "CD",
                    "qty": "1",
                    "text": None,
                    "descriptions": ["Album"],
                }
            ],
            "community": {"want": 5000, "have": 15000},
            "format_quantity": 1,
            "date_added": "2004-04-30T08:10:05-07:00",
            "date_changed": "2023-01-15T12:30:00-07:00",
            "num_for_sale": 500,
            "lowest_price": 5.00,
            "master_id": 13814,
            "master_url": "https://api.discogs.com/masters/13814",
            "title": "Nevermind",
            "country": "US",
            "released": "1991-09-24",
            "released_formatted": "24 Sep 1991",
            "notes": "Recorded at Sound City Studios, Van Nuys, CA.",
            "identifiers": [
                {
                    "type": "Barcode",
                    "value": "7 20642-44252-2",
                    "description": None,
                }
            ],
            "videos": [
                {
                    "uri": "https://www.youtube.com/watch?v=hTWKbfoikeg",
                    "title": "Smells Like Teen Spirit",
                    "description": "Official video",
                    "duration": 301,
                    "embed": True,
                }
            ],
            "genres": ["Rock"],
            "styles": ["Grunge"],
            "tracklist": [
                {
                    "position": "1",
                    "type_": "track",
                    "title": "Smells Like Teen Spirit",
                    "duration": "5:01",
                    "extraartists": [],
                }
            ],
            "extraartists": [
                {
                    "id": 354813,
                    "name": "Butch Vig",
                    "resource_url": "https://api.discogs.com/artists/354813",
                    "anv": None,
                    "join": None,
                    "role": "Producer",
                    "tracks": None,
                }
            ],
            "images": [
                {
                    "type": "primary",
                    "uri": "https://i.discogs.com/cover.jpg",
                    "resource_url": "https://api.discogs.com/images/cover.jpg",
                    "uri150": "https://i.discogs.com/thumb.jpg",
                    "width": 600,
                    "height": 600,
                }
            ],
            "thumb": "https://i.discogs.com/thumb.jpg",
            "estimated_weight": 100,
            "data_quality": "Correct",
        }

    @pytest.fixture
    def mock_discogs_client(self, mock_release_detail):
        """Create a mock Discogs client."""
        mock_client = MagicMock(spec=DiscogsClient)
        mock_client.get_release = AsyncMock(return_value=mock_release_detail)
        mock_client.search = AsyncMock()
        mock_client.get_master = AsyncMock()
        mock_client.get_artist_releases = AsyncMock()
        return mock_client

    def test_get_release_success(self, test_app: TestClient, mock_discogs_client):
        """Test successful release retrieval."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get("/discogs/releases/367273")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 367273
            assert data["title"] == "Nevermind"
            assert data["year"] == 1991
            assert data["country"] == "US"
            assert data["master_id"] == 13814
            assert data["released"] == "1991-09-24"
            assert len(data["labels"]) == 1
            assert data["labels"][0]["name"] == "DGC"
            assert data["labels"][0]["catno"] == "DGCD-24425"
            assert len(data["formats"]) == 1
            assert data["formats"][0]["name"] == "CD"
            assert len(data["extraartists"]) == 1
            assert data["extraartists"][0]["role"] == "Producer"
            assert len(data["identifiers"]) == 1
            assert data["identifiers"][0]["type"] == "Barcode"
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)

    def test_get_release_invalid_id(self, test_app: TestClient, mock_discogs_client):
        """Test get release with invalid ID type."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get("/discogs/releases/not-a-number")
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)


class TestDiscogsGetArtistReleases:
    """Tests for Discogs get artist releases endpoint."""

    @pytest.fixture
    def mock_artist_releases_result(self):
        """Mock artist releases from DiscogsClient."""
        return {
            "pagination": {
                "page": 1,
                "pages": 5,
                "per_page": 50,
                "items": 245,
                "urls": {
                    "next": "https://api.discogs.com/artists/125246/releases?page=2",
                },
            },
            "releases": [
                {
                    "id": 13814,
                    "type": "master",
                    "main_release": 367273,
                    "artist": "Nirvana",
                    "title": "Nevermind",
                    "year": 1991,
                    "resource_url": "https://api.discogs.com/masters/13814",
                    "role": "Main",
                    "thumb": "https://i.discogs.com/thumb1.jpg",
                    "status": None,
                    "format": "Album",
                    "label": "DGC",
                    "stats": {"community": {"in_wantlist": 519634, "in_collection": 383067}},
                },
                {
                    "id": 42473,
                    "type": "master",
                    "main_release": 367274,
                    "artist": "Nirvana",
                    "title": "From The Muddy Banks Of The Wishkah",
                    "year": 1996,
                    "resource_url": "https://api.discogs.com/masters/42473",
                    "role": "Main",
                    "thumb": "https://i.discogs.com/thumb2.jpg",
                    "status": None,
                    "format": "Album",
                    "label": "DGC",
                    "stats": {"community": {"in_wantlist": 16014, "in_collection": 31641}},
                },
                {
                    "id": 95432,
                    "type": "release",
                    "main_release": None,
                    "artist": "Various",
                    "title": "Grunge Compilation",
                    "year": 1994,
                    "resource_url": "https://api.discogs.com/releases/95432",
                    "role": "Appearance",
                    "thumb": "https://i.discogs.com/thumb3.jpg",
                    "status": "Accepted",
                    "format": "Compilation",
                    "label": "Various",
                    "stats": None,
                },
            ],
        }

    @pytest.fixture
    def mock_discogs_client(self, mock_artist_releases_result):
        """Create a mock Discogs client."""
        mock_client = MagicMock(spec=DiscogsClient)
        mock_client.get_artist_releases = AsyncMock(return_value=mock_artist_releases_result)
        mock_client.search = AsyncMock()
        mock_client.get_master = AsyncMock()
        mock_client.get_release = AsyncMock()
        return mock_client

    def test_get_artist_releases_success(self, test_app: TestClient, mock_discogs_client):
        """Test successful artist releases retrieval."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get("/discogs/artists/125246/releases")

            assert response.status_code == 200
            data = response.json()
            assert data["pagination"]["page"] == 1
            assert data["pagination"]["pages"] == 5
            assert data["pagination"]["items"] == 245
            assert len(data["releases"]) == 3
            assert data["releases"][0]["id"] == 13814
            assert data["releases"][0]["title"] == "Nevermind"
            assert data["releases"][0]["role"] == "Main"
            assert data["releases"][0]["type"] == "master"
            assert data["releases"][2]["role"] == "Appearance"
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)

    def test_get_artist_releases_pagination(self, test_app: TestClient, mock_discogs_client):
        """Test artist releases with pagination parameters."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get(
                "/discogs/artists/125246/releases",
                params={
                    "page": 2,
                    "per_page": 25,
                    "sort": "year",
                    "sort_order": "asc",
                },
            )

            assert response.status_code == 200
            mock_discogs_client.get_artist_releases.assert_called_once_with(
                artist_id=125246,
                page=2,
                per_page=25,
            )
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)

    def test_get_artist_releases_invalid_id(self, test_app: TestClient, mock_discogs_client):
        """Test get artist releases with invalid ID type."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get("/discogs/artists/not-a-number/releases")
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)

    def test_get_artist_releases_per_page_max(self, test_app: TestClient, mock_discogs_client):
        """Test artist releases validates per_page max value."""

        async def override_get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
            yield mock_discogs_client

        test_app.app.dependency_overrides[get_discogs_client] = override_get_discogs_client

        try:
            response = test_app.get(
                "/discogs/artists/125246/releases",
                params={"per_page": 101},  # Exceeds max of 100
            )
            assert response.status_code == 422  # Validation error
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)


class TestDiscogsServiceUnavailable:
    """Tests for Discogs service unavailable scenarios."""

    def test_search_service_unavailable(self, test_app: TestClient):
        """Test search when Discogs is not configured."""
        from fastapi import HTTPException

        async def override_unavailable() -> AsyncGenerator[DiscogsClient, None]:
            raise HTTPException(status_code=503, detail="Discogs API is not configured")
            yield  # Never reached, but makes it a generator

        test_app.app.dependency_overrides[get_discogs_client] = override_unavailable

        try:
            response = test_app.get(
                "/discogs/search",
                params={"artist": "Nirvana"},
            )

            assert response.status_code == 503
            assert "not configured" in response.json()["detail"]
        finally:
            test_app.app.dependency_overrides.pop(get_discogs_client, None)
