"""Tests for yt-dlp API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from fuzzbin.parsers.ytdlp_models import YTDLPSearchResult
from fuzzbin.tasks import JobStatus, JobType


class TestYTDLPEndpoints:
    """Tests for yt-dlp REST API endpoints."""

    @pytest.fixture
    def mock_search_results(self):
        """Mock search results from YTDLPClient."""
        return [
            YTDLPSearchResult(
                id="5WPbqYoz9HA",
                title="Bush - Machinehead",
                url="https://www.youtube.com/watch?v=5WPbqYoz9HA",
                channel="BushVEVO",
                channel_follower_count=411000,
                view_count=28794614,
                duration=257,
            ),
            YTDLPSearchResult(
                id="xyz123",
                title="Bush - Machinehead (Live)",
                url="https://www.youtube.com/watch?v=xyz123",
                channel="BushVEVO",
                channel_follower_count=411000,
                view_count=1000000,
                duration=300,
            ),
        ]

    def test_search_youtube_success(self, test_app: TestClient, mock_search_results):
        """Test successful YouTube search."""
        with patch(
            "fuzzbin.web.routes.ytdlp.YTDLPClient"
        ) as MockClient:
            # Setup mock client
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.search = AsyncMock(return_value=mock_search_results)
            MockClient.from_config.return_value = mock_client_instance

            response = test_app.get(
                "/ytdlp/search",
                params={
                    "artist": "Bush",
                    "track_title": "Machinehead",
                    "max_results": 5,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data
            assert data["total"] == 2
            assert data["query"] == "Bush Machinehead"
            assert len(data["results"]) == 2
            assert data["results"][0]["id"] == "5WPbqYoz9HA"
            assert data["results"][0]["title"] == "Bush - Machinehead"

    def test_search_youtube_validation_missing_param(self, test_app: TestClient):
        """Test search endpoint validates required parameters."""
        # Missing track_title parameter
        response = test_app.get(
            "/ytdlp/search",
            params={"artist": "Bush"},
        )

        assert response.status_code == 422  # Validation error

    def test_search_youtube_validation_max_results(self, test_app: TestClient):
        """Test search endpoint validates max_results range."""
        response = test_app.get(
            "/ytdlp/search",
            params={
                "artist": "Bush",
                "track_title": "Machinehead",
                "max_results": 100,  # Exceeds max of 50
            },
        )

        assert response.status_code == 422  # Validation error

    def test_get_video_info_success(self, test_app: TestClient):
        """Test successful video info retrieval."""
        mock_result = YTDLPSearchResult(
            id="dQw4w9WgXcQ",
            title="Rick Astley - Never Gonna Give You Up",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            channel="RickAstleyVEVO",
            channel_follower_count=10000000,
            view_count=1500000000,
            duration=212,
        )

        with patch(
            "fuzzbin.web.routes.ytdlp.YTDLPClient"
        ) as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.get_video_info = AsyncMock(return_value=mock_result)
            MockClient.from_config.return_value = mock_client_instance

            response = test_app.get("/ytdlp/info/dQw4w9WgXcQ")

            assert response.status_code == 200
            data = response.json()
            assert "video" in data
            assert data["video"]["id"] == "dQw4w9WgXcQ"
            assert data["video"]["title"] == "Rick Astley - Never Gonna Give You Up"
            assert data["video"]["view_count"] == 1500000000

    def test_download_video_submits_job(self, test_app: TestClient, test_library_dir):
        """Test download endpoint submits a job."""
        response = test_app.post(
            "/ytdlp/download",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "output_path": "downloads/test.mp4",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
        assert data["type"] == "download_youtube"
        assert data["metadata"]["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_download_video_validates_path_traversal(self, test_app: TestClient):
        """Test download endpoint rejects path traversal attempts."""
        response = test_app.post(
            "/ytdlp/download",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "output_path": "../../../etc/passwd",
            },
        )

        assert response.status_code == 400
        assert "library directory" in response.json()["detail"].lower()

    def test_download_video_validates_absolute_path(self, test_app: TestClient):
        """Test download endpoint rejects absolute paths outside library."""
        response = test_app.post(
            "/ytdlp/download",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "output_path": "/etc/passwd",
            },
        )

        assert response.status_code == 400
        assert "library directory" in response.json()["detail"].lower()

    def test_download_video_accepts_relative_path(self, test_app: TestClient, test_library_dir):
        """Test download endpoint accepts relative paths within library."""
        response = test_app.post(
            "/ytdlp/download",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "output_path": "Artist/Song.mp4",
            },
        )

        assert response.status_code == 202
        data = response.json()
        # Verify the path was resolved to be within library_dir
        assert str(test_library_dir) in data["metadata"]["output_path"]

    def test_cancel_download_job_not_found(self, test_app: TestClient):
        """Test cancelling a non-existent job returns 404."""
        response = test_app.delete("/ytdlp/download/nonexistent-job-id")

        assert response.status_code == 404

    def test_cancel_download_wrong_job_type(self, test_app: TestClient):
        """Test cancelling a non-YouTube job returns 400."""
        # First, submit an NFO import job (different type)
        submit_response = test_app.post(
            "/jobs",
            json={
                "type": JobType.IMPORT_NFO.value,
                "metadata": {"directory": "/tmp/test"},
            },
        )
        job_id = submit_response.json()["id"]

        # Try to cancel via the ytdlp endpoint
        response = test_app.delete(f"/ytdlp/download/{job_id}")

        assert response.status_code == 400
        assert "not a YouTube download job" in response.json()["detail"]

    def test_cancel_download_success(self, test_app: TestClient, test_library_dir):
        """Test successfully cancelling a download job."""
        # Submit a YouTube download job
        submit_response = test_app.post(
            "/ytdlp/download",
            json={
                "url": "https://www.youtube.com/watch?v=test123",
                "output_path": "test/video.mp4",
            },
        )
        job_id = submit_response.json()["id"]

        # Cancel the job
        response = test_app.delete(f"/ytdlp/download/{job_id}")

        assert response.status_code == 204

    def test_search_with_format_spec(self, test_app: TestClient, test_library_dir):
        """Test download with custom format specification."""
        response = test_app.post(
            "/ytdlp/download",
            json={
                "url": "https://www.youtube.com/watch?v=test123",
                "output_path": "test/video.mp4",
                "format_spec": "bestvideo[height<=1080]+bestaudio/best",
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["metadata"]["format_spec"] == "bestvideo[height<=1080]+bestaudio/best"
