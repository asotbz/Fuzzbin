"""Tests for bulk operations API endpoints (Phase 7)."""

import pytest
from fastapi.testclient import TestClient


class TestBulkUpdate:
    """Tests for POST /videos/bulk/update endpoint."""

    def test_bulk_update_videos(
        self, test_app: TestClient, sample_video_data: dict, sample_video_data_2: dict
    ) -> None:
        """Test bulk updating multiple videos."""
        # Create videos
        r1 = test_app.post("/videos", json=sample_video_data)
        r2 = test_app.post("/videos", json=sample_video_data_2)
        video_id_1 = r1.json()["id"]
        video_id_2 = r2.json()["id"]

        # Bulk update
        response = test_app.post(
            "/videos/bulk/update",
            json={
                "video_ids": [video_id_1, video_id_2],
                "updates": {"studio": "Universal Music"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["success_ids"]) == 2
        assert len(data["failed_ids"]) == 0

        # Verify updates applied
        v1 = test_app.get(f"/videos/{video_id_1}").json()
        v2 = test_app.get(f"/videos/{video_id_2}").json()
        assert v1["studio"] == "Universal Music"
        assert v2["studio"] == "Universal Music"

    def test_bulk_update_partial_failure(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test bulk update with some invalid IDs."""
        r = test_app.post("/videos", json=sample_video_data)
        video_id = r.json()["id"]

        response = test_app.post(
            "/videos/bulk/update",
            json={
                "video_ids": [video_id, 99999],
                "updates": {"studio": "Sony Music"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert video_id in data["success_ids"]
        assert 99999 in data["failed_ids"]

    def test_bulk_update_empty_list(self, test_app: TestClient) -> None:
        """Test bulk update with empty video list returns validation error."""
        response = test_app.post(
            "/videos/bulk/update",
            json={
                "video_ids": [],
                "updates": {"studio": "Test"},
            },
        )

        # Empty list is rejected by validation (min_length=1)
        assert response.status_code == 422

    def test_bulk_update_exceeds_limit(self, test_app: TestClient) -> None:
        """Test bulk update exceeding max_bulk_items limit."""
        # Try to update more than 500 items
        response = test_app.post(
            "/videos/bulk/update",
            json={
                "video_ids": list(range(1, 502)),  # 501 items
                "updates": {"studio": "Test"},
            },
        )

        assert response.status_code == 400
        assert "exceeds limit" in response.json()["detail"].lower()


class TestBulkDelete:
    """Tests for POST /videos/bulk/delete endpoint."""

    def test_bulk_delete_videos(
        self, test_app: TestClient, sample_video_data: dict, sample_video_data_2: dict
    ) -> None:
        """Test bulk deleting multiple videos."""
        r1 = test_app.post("/videos", json=sample_video_data)
        r2 = test_app.post("/videos", json=sample_video_data_2)
        video_id_1 = r1.json()["id"]
        video_id_2 = r2.json()["id"]

        response = test_app.post(
            "/videos/bulk/delete",
            json={
                "video_ids": [video_id_1, video_id_2],
                "hard_delete": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["success_ids"]) == 2

        # Verify soft deleted
        r1 = test_app.get(f"/videos/{video_id_1}")
        assert r1.status_code == 404  # Default excludes deleted

    def test_bulk_hard_delete(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test bulk hard delete."""
        r = test_app.post("/videos", json=sample_video_data)
        video_id = r.json()["id"]

        response = test_app.post(
            "/videos/bulk/delete",
            json={
                "video_ids": [video_id],
                "hard_delete": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert video_id in data["success_ids"]


class TestBulkStatus:
    """Tests for POST /videos/bulk/status endpoint."""

    def test_bulk_update_status(
        self, test_app: TestClient, sample_video_data: dict, sample_video_data_2: dict
    ) -> None:
        """Test bulk status update."""
        r1 = test_app.post("/videos", json=sample_video_data)
        r2 = test_app.post("/videos", json=sample_video_data_2)
        video_id_1 = r1.json()["id"]
        video_id_2 = r2.json()["id"]

        response = test_app.post(
            "/videos/bulk/status",
            json={
                "video_ids": [video_id_1, video_id_2],
                "status": "organized",  # Valid status value
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["success_ids"]) == 2

        # Verify status changed
        v1 = test_app.get(f"/videos/{video_id_1}").json()
        assert v1["status"] == "organized"


class TestBulkTags:
    """Tests for POST /videos/bulk/tags endpoint."""

    def test_bulk_apply_tags(
        self, test_app: TestClient, sample_video_data: dict, sample_video_data_2: dict
    ) -> None:
        """Test bulk applying tags to videos."""
        r1 = test_app.post("/videos", json=sample_video_data)
        r2 = test_app.post("/videos", json=sample_video_data_2)
        video_id_1 = r1.json()["id"]
        video_id_2 = r2.json()["id"]

        response = test_app.post(
            "/videos/bulk/tags",
            json={
                "video_ids": [video_id_1, video_id_2],
                "tag_names": ["favorites", "90s"],
                "replace": False,  # Add to existing tags
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["success_ids"]) == 2

    def test_bulk_replace_tags(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test bulk replacing tags on videos."""
        r = test_app.post("/videos", json=sample_video_data)
        video_id = r.json()["id"]

        # First add a tag
        test_app.post(
            "/videos/bulk/tags",
            json={
                "video_ids": [video_id],
                "tag_names": ["old-tag"],
                "replace": False,
            },
        )

        # Replace with new tags
        response = test_app.post(
            "/videos/bulk/tags",
            json={
                "video_ids": [video_id],
                "tag_names": ["new-tag"],
                "replace": True,  # Replace existing tags
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert video_id in data["success_ids"]


class TestBulkCollections:
    """Tests for POST /videos/bulk/collections endpoint."""

    def test_bulk_add_to_collection(
        self, test_app: TestClient, sample_video_data: dict, sample_video_data_2: dict
    ) -> None:
        """Test bulk adding videos to collection."""
        # Create collection
        col_response = test_app.post(
            "/collections", json={"name": "My Playlist", "description": "Test"}
        )
        collection_id = col_response.json()["id"]

        r1 = test_app.post("/videos", json=sample_video_data)
        r2 = test_app.post("/videos", json=sample_video_data_2)
        video_id_1 = r1.json()["id"]
        video_id_2 = r2.json()["id"]

        response = test_app.post(
            "/videos/bulk/collections",
            json={
                "video_ids": [video_id_1, video_id_2],
                "collection_id": collection_id,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["success_ids"]) == 2

        # Verify videos in collection
        col = test_app.get(f"/collections/{collection_id}").json()
        assert col["video_count"] == 2


class TestBulkOrganize:
    """Tests for POST /videos/bulk/organize endpoint."""

    def test_bulk_organize_updates_paths(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test that bulk organize updates video file paths."""
        # Create video
        r = test_app.post("/videos", json=sample_video_data)
        video_id = r.json()["id"]

        response = test_app.post(
            "/videos/bulk/organize",
            json={
                "items": [
                    {
                        "video_id": video_id,
                        "video_file_path": "/new/path/video.mp4",
                        "nfo_file_path": "/new/path/video.nfo",
                    }
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert video_id in data["success_ids"]
