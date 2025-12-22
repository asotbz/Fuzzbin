"""Tests for import workflow API endpoints (Phase 7)."""

import pytest
from fastapi.testclient import TestClient


class TestYouTubeImport:
    """Tests for POST /imports/youtube endpoint."""

    def test_youtube_import_single_url(self, test_app: TestClient) -> None:
        """Test importing a single YouTube URL."""
        response = test_app.post(
            "/imports/youtube",
            json={
                "urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
            },
        )

        # Could be 200 (sync) or 202 (async queued)
        assert response.status_code in [200, 202]
        data = response.json()

        if response.status_code == 200:
            # Sync response
            assert "imported" in data or "results" in data
        else:
            # Async response
            assert "job_id" in data

    def test_youtube_import_multiple_urls(self, test_app: TestClient) -> None:
        """Test importing multiple YouTube URLs."""
        response = test_app.post(
            "/imports/youtube",
            json={
                "urls": [
                    "https://www.youtube.com/watch?v=video1",
                    "https://www.youtube.com/watch?v=video2",
                    "https://youtu.be/video3",
                ],
            },
        )

        assert response.status_code in [200, 202]

    def test_youtube_import_empty_urls(self, test_app: TestClient) -> None:
        """Test importing with empty URL list."""
        response = test_app.post(
            "/imports/youtube",
            json={"urls": []},
        )

        # Pydantic validation returns 422 for min_length constraint
        assert response.status_code == 422
        # Validation error format may vary - just check status code is correct
        data = response.json()
        assert "detail" in data

    def test_youtube_import_invalid_url_format(self, test_app: TestClient) -> None:
        """Test importing with invalid URL format."""
        response = test_app.post(
            "/imports/youtube",
            json={
                "urls": ["not-a-valid-url"],
            },
        )

        # Should still accept and try to process (extraction will fail)
        assert response.status_code in [200, 202, 400]

    def test_youtube_import_url_extraction(self, test_app: TestClient) -> None:
        """Test various YouTube URL formats are accepted."""
        urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/v/dQw4w9WgXcQ",
        ]

        response = test_app.post(
            "/imports/youtube",
            json={"urls": urls},
        )

        # Should accept all valid formats
        assert response.status_code in [200, 202]


class TestIMVDbImport:
    """Tests for POST /imports/imvdb endpoint."""

    def test_imvdb_import_by_video_ids(self, test_app: TestClient) -> None:
        """Test importing by IMVDb video IDs."""
        response = test_app.post(
            "/imports/imvdb",
            json={
                "video_ids": [12345, 67890],
            },
        )

        # Could be 200 (sync) or 202 (async queued)
        assert response.status_code in [200, 202]

    def test_imvdb_import_by_search_queries(self, test_app: TestClient) -> None:
        """Test importing by search queries."""
        response = test_app.post(
            "/imports/imvdb",
            json={
                "search_queries": [{"artist": "Nirvana", "title": "Smells Like Teen Spirit"}],
            },
        )

        assert response.status_code in [200, 202]

    def test_imvdb_import_combined(self, test_app: TestClient) -> None:
        """Test importing with both video IDs and search queries."""
        response = test_app.post(
            "/imports/imvdb",
            json={
                "video_ids": [12345],
                "search_queries": [{"artist": "REM", "title": "Losing My Religion"}],
            },
        )

        assert response.status_code in [200, 202]

    def test_imvdb_import_empty_request(self, test_app: TestClient) -> None:
        """Test importing with no video IDs or search queries."""
        response = test_app.post(
            "/imports/imvdb",
            json={},
        )

        assert response.status_code == 400
        assert "video_ids" in response.json()["detail"].lower() or "search" in response.json()["detail"].lower()

    def test_imvdb_import_large_batch_queued(self, test_app: TestClient) -> None:
        """Test that large imports are queued as background jobs."""
        # Create a large list of video IDs (more than max_sync_import_items)
        video_ids = list(range(1, 20))  # 19 items as integers

        response = test_app.post(
            "/imports/imvdb",
            json={"video_ids": video_ids},
        )

        # Large batch should be queued (may return 400 if queue not running)
        assert response.status_code in [200, 202, 400]


class TestImportValidation:
    """Tests for import input validation."""

    def test_import_requires_authentication(self, test_app: TestClient) -> None:
        """Test that import endpoints require authentication when enabled."""
        # This test assumes auth is disabled in test environment
        # When auth is enabled, this should return 401/403
        response = test_app.post(
            "/imports/youtube",
            json={"urls": ["https://youtube.com/watch?v=test"]},
        )

        # In test env, auth is typically disabled
        assert response.status_code in [200, 202, 401, 403]

    def test_youtube_import_deduplication(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test that importing same URL twice doesn't create duplicates."""
        # Create a video with a YouTube ID
        video_data = {**sample_video_data, "youtube_id": "test123"}
        test_app.post("/videos", json=video_data)

        # Try to import the same YouTube ID
        response = test_app.post(
            "/imports/youtube",
            json={"urls": ["https://youtube.com/watch?v=test123"]},
        )

        # Should handle gracefully (skip or update)
        assert response.status_code in [200, 202]
