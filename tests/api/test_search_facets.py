"""Tests for search facets and saved searches API endpoints (Phase 7)."""

import pytest
from fastapi.testclient import TestClient

from fuzzbin.web.routes.search import clear_facet_cache


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Clear facet cache before each test to ensure test isolation."""
    clear_facet_cache()
    yield
    clear_facet_cache()


class TestSearchFacets:
    """Tests for GET /search/facets endpoint."""

    def test_get_facets_empty(self, test_app: TestClient) -> None:
        """Test facets with no videos."""
        response = test_app.get("/search/facets")

        assert response.status_code == 200
        data = response.json()
        assert "tags" in data
        assert "genres" in data
        assert "years" in data
        assert "directors" in data
        assert data["total_videos"] == 0

    def test_get_facets_with_data(
        self,
        test_app: TestClient,
        sample_video_data: dict,
        sample_video_data_2: dict,
        sample_video_data_3: dict,
    ) -> None:
        """Test facets with video data."""
        # Create videos with different metadata
        test_app.post("/videos", json=sample_video_data)  # Grunge, 1991
        test_app.post("/videos", json=sample_video_data_2)  # Alternative Rock, 1991
        test_app.post("/videos", json=sample_video_data_3)  # Alternative Rock, 1992

        response = test_app.get("/search/facets")

        assert response.status_code == 200
        data = response.json()
        assert data["total_videos"] == 3

        # Check genres
        genres = {g["value"]: g["count"] for g in data["genres"]}
        assert "Alternative Rock" in genres
        assert genres["Alternative Rock"] == 2
        assert "Grunge" in genres
        assert genres["Grunge"] == 1

        # Check years (years are returned as strings)
        years = {y["value"]: y["count"] for y in data["years"]}
        assert "1991" in years
        assert years["1991"] == 2
        assert "1992" in years
        assert years["1992"] == 1

    def test_facets_include_directors(
        self, test_app: TestClient, sample_video_data: dict, sample_video_data_2: dict
    ) -> None:
        """Test that director facets are included."""
        test_app.post("/videos", json=sample_video_data)  # Samuel Bayer
        test_app.post("/videos", json=sample_video_data_2)  # Tarsem Singh

        response = test_app.get("/search/facets")

        assert response.status_code == 200
        data = response.json()

        directors = {d["value"]: d["count"] for d in data["directors"]}
        assert "Samuel Bayer" in directors
        assert "Tarsem Singh" in directors

    def test_facets_include_tags(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test that tag facets include video counts."""
        # Create video
        r = test_app.post("/videos", json=sample_video_data)
        video_id = r.json()["id"]

        # Create and assign tag
        tag_r = test_app.post("/tags", json={"name": "classic"})
        tag_id = tag_r.json()["id"]
        test_app.post(f"/videos/{video_id}/tags/{tag_id}")

        response = test_app.get("/search/facets")

        assert response.status_code == 200
        data = response.json()

        tags = {t["value"]: t["count"] for t in data["tags"]}
        assert "classic" in tags
        assert tags["classic"] == 1

    def test_facets_caching(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test that facets are cached (second call should be fast)."""
        test_app.post("/videos", json=sample_video_data)

        # First call
        r1 = test_app.get("/search/facets")
        assert r1.status_code == 200

        # Second call (should hit cache)
        r2 = test_app.get("/search/facets")
        assert r2.status_code == 200

        # Results should be identical
        assert r1.json() == r2.json()


class TestSavedSearches:
    """Tests for saved search CRUD endpoints."""

    def test_create_saved_search(self, test_app: TestClient) -> None:
        """Test creating a saved search."""
        response = test_app.post(
            "/search/saved",
            json={
                "name": "90s Rock Videos",
                "description": "All rock videos from the 90s",
                "query": {
                    "genre": "Rock",
                    "year_from": 1990,
                    "year_to": 1999,
                },
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "90s Rock Videos"
        assert data["description"] == "All rock videos from the 90s"
        assert "id" in data
        assert "created_at" in data

    def test_list_saved_searches(self, test_app: TestClient) -> None:
        """Test listing saved searches."""
        # Create some searches
        test_app.post(
            "/search/saved",
            json={"name": "Search 1", "query": {"artist": "Nirvana"}},
        )
        test_app.post(
            "/search/saved",
            json={"name": "Search 2", "query": {"year": 1991}},
        )

        response = test_app.get("/search/saved")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["items"]) >= 2

    def test_get_saved_search_by_id(self, test_app: TestClient) -> None:
        """Test getting a specific saved search."""
        # Create search
        create_r = test_app.post(
            "/search/saved",
            json={
                "name": "My Search",
                "query": {"director": "Samuel Bayer"},
            },
        )
        search_id = create_r.json()["id"]

        response = test_app.get(f"/search/saved/{search_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == search_id
        assert data["name"] == "My Search"
        assert data["query"]["director"] == "Samuel Bayer"

    def test_get_saved_search_not_found(self, test_app: TestClient) -> None:
        """Test getting non-existent saved search."""
        response = test_app.get("/search/saved/99999")

        assert response.status_code == 404

    def test_delete_saved_search(self, test_app: TestClient) -> None:
        """Test deleting a saved search."""
        # Create search
        create_r = test_app.post(
            "/search/saved",
            json={"name": "To Delete", "query": {}},
        )
        search_id = create_r.json()["id"]

        # Delete it
        response = test_app.delete(f"/search/saved/{search_id}")
        assert response.status_code == 204

        # Verify deleted
        get_r = test_app.get(f"/search/saved/{search_id}")
        assert get_r.status_code == 404

    def test_delete_saved_search_not_found(self, test_app: TestClient) -> None:
        """Test deleting non-existent saved search."""
        response = test_app.delete("/search/saved/99999")

        assert response.status_code == 404

    def test_saved_search_query_validation(self, test_app: TestClient) -> None:
        """Test that saved search requires name."""
        response = test_app.post(
            "/search/saved",
            json={
                "description": "Missing name",
                "query": {},
            },
        )

        assert response.status_code == 422  # Validation error

    def test_saved_search_preserves_complex_query(self, test_app: TestClient) -> None:
        """Test that complex query parameters are preserved."""
        complex_query = {
            "q": "music video",
            "artist": "Nirvana",
            "genre": "Grunge",
            "year_from": 1990,
            "year_to": 1995,
            "status": "complete",
            "has_file": True,
        }

        create_r = test_app.post(
            "/search/saved",
            json={
                "name": "Complex Search",
                "query": complex_query,
            },
        )
        search_id = create_r.json()["id"]

        # Retrieve and verify
        get_r = test_app.get(f"/search/saved/{search_id}")
        data = get_r.json()

        assert data["query"]["q"] == "music video"
        assert data["query"]["artist"] == "Nirvana"
        assert data["query"]["year_from"] == 1990
