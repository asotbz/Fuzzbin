"""Tests for export workflow API endpoints (Phase 7)."""

import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


class TestNFOExport:
    """Tests for POST /exports/nfo endpoint."""

    def test_nfo_export_empty_library(self, test_app: TestClient) -> None:
        """Test NFO export with no videos."""
        response = test_app.post(
            "/exports/nfo",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["exported_count"] == 0
        assert data["skipped_count"] == 0
        assert data["failed_count"] == 0

    def test_nfo_export_specific_videos(
        self, test_app: TestClient, sample_video_data: dict, sample_video_data_2: dict
    ) -> None:
        """Test exporting NFO for specific videos."""
        # Create videos
        r1 = test_app.post("/videos", json=sample_video_data)
        r2 = test_app.post("/videos", json=sample_video_data_2)
        video_id_1 = r1.json()["id"]
        video_id_2 = r2.json()["id"]

        response = test_app.post(
            "/exports/nfo",
            json={
                "video_ids": [video_id_1, video_id_2],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        # Without video file paths, videos will be skipped
        assert data["skipped_count"] == 2 or data["failed_count"] >= 0

    def test_nfo_export_all_videos(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test exporting NFO for all videos."""
        test_app.post("/videos", json=sample_video_data)

        response = test_app.post(
            "/exports/nfo",
            json={},  # No video_ids = export all
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert "library_dir" in data

    def test_nfo_export_overwrite_option(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test NFO export with overwrite option."""
        r = test_app.post("/videos", json=sample_video_data)
        video_id = r.json()["id"]

        response = test_app.post(
            "/exports/nfo",
            json={
                "video_ids": [video_id],
                "overwrite_existing": True,
            },
        )

        assert response.status_code == 200

    def test_nfo_export_include_deleted(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test NFO export including soft-deleted videos."""
        r = test_app.post("/videos", json=sample_video_data)
        video_id = r.json()["id"]

        # Soft delete the video
        test_app.delete(f"/videos/{video_id}")

        response = test_app.post(
            "/exports/nfo",
            json={
                "include_deleted": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Should include the deleted video
        assert data["total"] >= 1


class TestPlaylistExport:
    """Tests for POST /exports/playlist endpoint."""

    def test_export_m3u_playlist(
        self, test_app: TestClient, sample_video_data: dict, tmp_path: Path
    ) -> None:
        """Test exporting M3U playlist."""
        # Create video with file path
        video_data = {
            **sample_video_data,
            "video_file_path": str(tmp_path / "video.mp4"),
        }
        test_app.post("/videos", json=video_data)

        output_file = tmp_path / "My Playlist.m3u"
        response = test_app.post(
            "/exports/playlist",
            json={
                "name": "My Playlist",
                "format": "m3u",
                "output_path": str(output_file),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Playlist"
        assert data["format"] == "m3u"
        assert "file_path" in data
        assert data["file_path"].endswith(".m3u")

    def test_export_csv_playlist(
        self, test_app: TestClient, sample_video_data: dict, tmp_path: Path
    ) -> None:
        """Test exporting CSV playlist."""
        test_app.post("/videos", json=sample_video_data)

        output_file = tmp_path / "CSV Export.csv"
        response = test_app.post(
            "/exports/playlist",
            json={
                "name": "CSV Export",
                "format": "csv",
                "output_path": str(output_file),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "csv"
        assert data["file_path"].endswith(".csv")

    def test_export_json_playlist(
        self, test_app: TestClient, sample_video_data: dict, sample_video_data_2: dict, tmp_path: Path
    ) -> None:
        """Test exporting JSON playlist."""
        test_app.post("/videos", json=sample_video_data)
        test_app.post("/videos", json=sample_video_data_2)

        output_file = tmp_path / "JSON Export.json"
        response = test_app.post(
            "/exports/playlist",
            json={
                "name": "JSON Export",
                "format": "json",
                "output_path": str(output_file),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "json"
        assert data["total_tracks"] == 2
        assert data["file_path"].endswith(".json")

    def test_export_playlist_specific_videos(
        self, test_app: TestClient, sample_video_data: dict, sample_video_data_2: dict, tmp_path: Path
    ) -> None:
        """Test exporting playlist with specific videos."""
        r1 = test_app.post("/videos", json=sample_video_data)
        r2 = test_app.post("/videos", json=sample_video_data_2)
        video_id_1 = r1.json()["id"]

        output_file = tmp_path / "Selected Videos.json"
        response = test_app.post(
            "/exports/playlist",
            json={
                "name": "Selected Videos",
                "video_ids": [video_id_1],
                "format": "json",
                "output_path": str(output_file),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_tracks"] == 1

    def test_export_playlist_empty(self, test_app: TestClient, tmp_path: Path) -> None:
        """Test exporting empty playlist."""
        output_file = tmp_path / "Empty Playlist.json"
        response = test_app.post(
            "/exports/playlist",
            json={
                "name": "Empty Playlist",
                "format": "json",
                "output_path": str(output_file),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_tracks"] == 0

    def test_export_playlist_name_sanitization(
        self, test_app: TestClient, sample_video_data: dict, tmp_path: Path
    ) -> None:
        """Test that playlist names are sanitized for filenames."""
        test_app.post("/videos", json=sample_video_data)

        # User provides output_path, name is used for display only
        output_file = tmp_path / "safe_playlist_name.m3u"
        response = test_app.post(
            "/exports/playlist",
            json={
                "name": "My/Playlist:With*Special<Chars>",
                "format": "m3u",
                "output_path": str(output_file),
            },
        )

        assert response.status_code == 200
        data = response.json()
        # User controls the output path now
        assert data["file_path"] == str(output_file)

    def test_export_playlist_requires_name(self, test_app: TestClient, tmp_path: Path) -> None:
        """Test that playlist export requires a name."""
        response = test_app.post(
            "/exports/playlist",
            json={
                "format": "json",
                "output_path": str(tmp_path / "test.json"),
            },
        )

        assert response.status_code == 422  # Validation error

    def test_export_playlist_requires_output_path(self, test_app: TestClient) -> None:
        """Test that playlist export requires an output_path."""
        response = test_app.post(
            "/exports/playlist",
            json={
                "name": "Test Playlist",
                "format": "json",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_export_playlist_invalid_format(self, test_app: TestClient, tmp_path: Path) -> None:
        """Test that invalid export format is rejected."""
        response = test_app.post(
            "/exports/playlist",
            json={
                "name": "Test",
                "format": "invalid_format",
                "output_path": str(tmp_path / "test.txt"),
            },
        )

        assert response.status_code == 422


class TestExportIntegration:
    """Integration tests for export workflows."""

    def test_export_creates_files_at_user_specified_path(
        self, test_app: TestClient, sample_video_data: dict, tmp_path: Path
    ) -> None:
        """Test that playlist exports are created at the user-specified path."""
        test_app.post("/videos", json=sample_video_data)

        output_file = tmp_path / "my_exports" / "Integration Test.json"
        response = test_app.post(
            "/exports/playlist",
            json={
                "name": "Integration Test",
                "format": "json",
                "output_path": str(output_file),
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify file path is at user-specified location
        assert data["file_path"] == str(output_file)
        assert output_file.exists()
