"""Tests for video CRUD endpoints."""

from fastapi.testclient import TestClient


class TestVideoList:
    """Tests for GET /videos endpoint."""

    def test_list_videos_empty(self, test_app: TestClient) -> None:
        """Test listing videos when database is empty."""
        response = test_app.get("/videos")

        assert response.status_code == 200
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["total_pages"] == 1

    def test_list_videos_with_data(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test listing videos with existing data."""
        # Create a video first
        create_response = test_app.post("/videos", json=sample_video_data)
        assert create_response.status_code == 201

        # List videos
        response = test_app.get("/videos")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == sample_video_data["title"]

    def test_list_videos_pagination(
        self,
        test_app: TestClient,
        sample_video_data: dict,
        sample_video_data_2: dict,
        sample_video_data_3: dict,
    ) -> None:
        """Test pagination for video list."""
        # Create multiple videos
        test_app.post("/videos", json=sample_video_data)
        test_app.post("/videos", json=sample_video_data_2)
        test_app.post("/videos", json=sample_video_data_3)

        # Get first page with page_size=2
        response = test_app.get("/videos", params={"page": 1, "page_size": 2})

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 2

        # Get second page
        response = test_app.get("/videos", params={"page": 2, "page_size": 2})
        data = response.json()

        assert len(data["items"]) == 1
        assert data["page"] == 2

    def test_list_videos_filter_by_artist(
        self,
        test_app: TestClient,
        sample_video_data: dict,
        sample_video_data_2: dict,
    ) -> None:
        """Test filtering videos by artist."""
        test_app.post("/videos", json=sample_video_data)
        test_app.post("/videos", json=sample_video_data_2)

        response = test_app.get("/videos", params={"artist": "Nirvana"})

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["artist"] == "Nirvana"

    def test_list_videos_filter_by_year(
        self,
        test_app: TestClient,
        sample_video_data: dict,
        sample_video_data_3: dict,
    ) -> None:
        """Test filtering videos by year."""
        test_app.post("/videos", json=sample_video_data)  # 1991
        test_app.post("/videos", json=sample_video_data_3)  # 1992

        response = test_app.get("/videos", params={"year": 1991})

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["year"] == 1991

    def test_list_videos_filter_by_year_range(
        self,
        test_app: TestClient,
        sample_video_data: dict,
        sample_video_data_3: dict,
    ) -> None:
        """Test filtering videos by year range."""
        test_app.post("/videos", json=sample_video_data)  # 1991
        test_app.post("/videos", json=sample_video_data_3)  # 1992

        response = test_app.get("/videos", params={"year_min": 1990, "year_max": 1991})

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["year"] == 1991

    def test_list_videos_filter_by_genre(
        self,
        test_app: TestClient,
        sample_video_data: dict,
        sample_video_data_2: dict,
    ) -> None:
        """Test filtering videos by genre."""
        test_app.post("/videos", json=sample_video_data)  # Grunge
        test_app.post("/videos", json=sample_video_data_2)  # Alternative Rock

        response = test_app.get("/videos", params={"genre": "Grunge"})

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 1
        assert data["items"][0]["genre"] == "Grunge"

    def test_list_videos_sort_by_title(
        self,
        test_app: TestClient,
        sample_video_data: dict,
        sample_video_data_2: dict,
    ) -> None:
        """Test sorting videos by title."""
        test_app.post("/videos", json=sample_video_data)
        test_app.post("/videos", json=sample_video_data_2)

        # Sort ascending
        response = test_app.get("/videos", params={"sort_by": "title", "sort_order": "asc"})

        assert response.status_code == 200
        data = response.json()
        titles = [v["title"] for v in data["items"]]
        assert titles == sorted(titles)

    def test_list_videos_excludes_deleted_by_default(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test that deleted videos are excluded by default."""
        # Create and delete a video
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]
        test_app.delete(f"/videos/{video_id}")

        # List should be empty
        response = test_app.get("/videos")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_list_videos_include_deleted(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test including deleted videos in list."""
        # Create and delete a video
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]
        test_app.delete(f"/videos/{video_id}")

        # List with include_deleted
        response = test_app.get("/videos", params={"include_deleted": True})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["is_deleted"] is True


class TestVideoCreate:
    """Tests for POST /videos endpoint."""

    def test_create_video_success(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test successful video creation."""
        response = test_app.post("/videos", json=sample_video_data)

        assert response.status_code == 201
        data = response.json()

        assert data["id"] is not None
        assert data["title"] == sample_video_data["title"]
        assert data["artist"] == sample_video_data["artist"]
        assert data["album"] == sample_video_data["album"]
        assert data["year"] == sample_video_data["year"]
        assert data["is_deleted"] is False
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_video_minimal(self, test_app: TestClient) -> None:
        """Test creating video with only required fields."""
        response = test_app.post("/videos", json={"title": "Test Video"})

        assert response.status_code == 201
        data = response.json()

        assert data["title"] == "Test Video"
        assert data["artist"] is None
        assert data["album"] is None

    def test_create_video_with_external_ids(self, test_app: TestClient) -> None:
        """Test creating video with external IDs."""
        video_data = {
            "title": "Test Video",
            "imvdb_video_id": "12345",
            "youtube_id": "dQw4w9WgXcQ",
        }
        response = test_app.post("/videos", json=video_data)

        assert response.status_code == 201
        data = response.json()

        assert data["imvdb_video_id"] == "12345"
        assert data["youtube_id"] == "dQw4w9WgXcQ"

    def test_create_video_validation_error(self, test_app: TestClient) -> None:
        """Test validation error when title is missing."""
        response = test_app.post("/videos", json={})

        assert response.status_code == 422
        data = response.json()
        assert "errors" in data or "detail" in data


class TestVideoGet:
    """Tests for GET /videos/{video_id} endpoint."""

    def test_get_video_success(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test getting a video by ID."""
        # Create video
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]

        # Get video
        response = test_app.get(f"/videos/{video_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == video_id
        assert data["title"] == sample_video_data["title"]

    def test_get_video_not_found(self, test_app: TestClient) -> None:
        """Test getting non-existent video returns 404."""
        response = test_app.get("/videos/99999")

        assert response.status_code == 404
        data = response.json()
        assert data["error_type"] == "video_not_found"

    def test_get_deleted_video_without_flag(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test that getting deleted video returns 404 by default."""
        # Create and delete
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]
        test_app.delete(f"/videos/{video_id}")

        # Get without include_deleted flag
        response = test_app.get(f"/videos/{video_id}")

        assert response.status_code == 404

    def test_get_deleted_video_with_flag(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test getting deleted video with include_deleted flag."""
        # Create and delete
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]
        test_app.delete(f"/videos/{video_id}")

        # Get with include_deleted flag
        response = test_app.get(f"/videos/{video_id}", params={"include_deleted": True})

        assert response.status_code == 200
        data = response.json()
        assert data["is_deleted"] is True


class TestVideoUpdate:
    """Tests for PATCH /videos/{video_id} endpoint."""

    def test_update_video_success(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test successful video update."""
        # Create video
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]

        # Update video
        response = test_app.patch(
            f"/videos/{video_id}", json={"title": "Updated Title", "year": 1992}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["title"] == "Updated Title"
        assert data["year"] == 1992
        # Other fields should be preserved
        assert data["artist"] == sample_video_data["artist"]

    def test_update_video_partial(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test partial update (only specified fields change)."""
        # Create video
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]

        # Update only genre
        response = test_app.patch(f"/videos/{video_id}", json={"genre": "Rock"})

        assert response.status_code == 200
        data = response.json()

        assert data["genre"] == "Rock"
        assert data["title"] == sample_video_data["title"]

    def test_update_video_not_found(self, test_app: TestClient) -> None:
        """Test updating non-existent video returns 404."""
        response = test_app.patch("/videos/99999", json={"title": "New Title"})

        assert response.status_code == 404


class TestVideoDelete:
    """Tests for DELETE /videos/{video_id} endpoint."""

    def test_soft_delete_video(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test soft deleting a video."""
        # Create video
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]

        # Delete
        response = test_app.delete(f"/videos/{video_id}")

        assert response.status_code == 204

        # Verify it's soft deleted
        get_response = test_app.get(f"/videos/{video_id}", params={"include_deleted": True})
        assert get_response.status_code == 200
        assert get_response.json()["is_deleted"] is True

    def test_delete_video_not_found(self, test_app: TestClient) -> None:
        """Test deleting non-existent video returns 404."""
        response = test_app.delete("/videos/99999")

        assert response.status_code == 404


class TestVideoRestore:
    """Tests for POST /videos/{video_id}/restore endpoint."""

    def test_restore_video(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test restoring a soft-deleted video."""
        # Create and delete
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]
        test_app.delete(f"/videos/{video_id}")

        # Restore
        response = test_app.post(f"/videos/{video_id}/restore")

        assert response.status_code == 200
        data = response.json()
        assert data["is_deleted"] is False

        # Verify it's accessible without flag
        get_response = test_app.get(f"/videos/{video_id}")
        assert get_response.status_code == 200


class TestVideoHardDelete:
    """Tests for DELETE /videos/{video_id}/permanent endpoint."""

    def test_hard_delete_video(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test permanently deleting a video."""
        # Create video
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]

        # Hard delete
        response = test_app.delete(f"/videos/{video_id}/permanent")

        assert response.status_code == 204

        # Verify it's gone even with include_deleted
        get_response = test_app.get(f"/videos/{video_id}", params={"include_deleted": True})
        assert get_response.status_code == 404


class TestVideoStatusUpdate:
    """Tests for PATCH /videos/{video_id}/status endpoint."""

    def test_update_status(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test updating video status."""
        # Create video
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]

        # Update status
        response = test_app.patch(
            f"/videos/{video_id}/status",
            json={
                "status": "downloaded",
                "reason": "Downloaded from YouTube",
                "changed_by": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "downloaded"

    def test_status_history(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test getting video status history."""
        # Create video
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]

        # Update status
        test_app.patch(
            f"/videos/{video_id}/status",
            json={"status": "downloaded", "reason": "Test"},
        )

        # Get history
        response = test_app.get(f"/videos/{video_id}/status-history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1


class TestVideoStream:
    """Tests for GET /videos/{video_id}/stream endpoint."""

    def test_stream_video_full(self, test_app: TestClient, video_with_file: dict) -> None:
        """Test streaming full video file without Range header."""
        video_id = video_with_file["id"]

        response = test_app.get(f"/videos/{video_id}/stream")

        assert response.status_code == 200
        assert response.headers.get("Accept-Ranges") == "bytes"
        assert "Content-Length" in response.headers
        assert response.content == b"test video content for testing"

    def test_stream_video_with_range(self, test_app: TestClient, video_with_file: dict) -> None:
        """Test streaming video with Range header (206 Partial Content)."""
        video_id = video_with_file["id"]

        # Request first 10 bytes
        response = test_app.get(
            f"/videos/{video_id}/stream",
            headers={"Range": "bytes=0-9"},
        )

        assert response.status_code == 206
        assert response.content == b"test video"
        assert "Content-Range" in response.headers
        assert response.headers.get("Content-Range").startswith("bytes 0-9/")

    def test_stream_video_suffix_range(self, test_app: TestClient, video_with_file: dict) -> None:
        """Test streaming video with suffix Range (last N bytes)."""
        video_id = video_with_file["id"]

        # Request last 7 bytes ("testing")
        response = test_app.get(
            f"/videos/{video_id}/stream",
            headers={"Range": "bytes=-7"},
        )

        assert response.status_code == 206
        assert response.content == b"testing"

    def test_stream_video_open_ended_range(
        self, test_app: TestClient, video_with_file: dict
    ) -> None:
        """Test streaming video with open-ended Range (from byte N to end)."""
        video_id = video_with_file["id"]

        # Request from byte 5 to end
        response = test_app.get(
            f"/videos/{video_id}/stream",
            headers={"Range": "bytes=5-"},
        )

        assert response.status_code == 206
        assert response.content == b"video content for testing"

    def test_stream_video_not_found(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test streaming returns 404 for non-existent video."""
        response = test_app.get("/videos/99999/stream")

        # The repository raises VideoNotFoundError
        assert response.status_code == 404

    def test_stream_video_no_file(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test streaming returns 404 when video has no file path."""
        # Create video without file path
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]

        response = test_app.get(f"/videos/{video_id}/stream")

        assert response.status_code == 404
        assert "No video file" in response.json()["detail"]

    def test_stream_video_missing_file(
        self, test_app: TestClient, video_with_missing_file: dict
    ) -> None:
        """Test streaming returns 404 when file doesn't exist on disk."""
        video_id = video_with_missing_file["id"]

        response = test_app.get(f"/videos/{video_id}/stream")

        assert response.status_code == 404
        assert "not found on disk" in response.json()["detail"]

    def test_stream_invalid_range(self, test_app: TestClient, video_with_file: dict) -> None:
        """Test streaming returns 416 for invalid range."""
        video_id = video_with_file["id"]

        # Request range beyond file size
        response = test_app.get(
            f"/videos/{video_id}/stream",
            headers={"Range": "bytes=10000-20000"},
        )

        assert response.status_code == 416


class TestVideoThumbnail:
    """Tests for GET /videos/{video_id}/thumbnail endpoint."""

    def test_thumbnail_video_not_found(self, test_app: TestClient) -> None:
        """Test thumbnail returns 404 for non-existent video."""
        response = test_app.get("/videos/99999/thumbnail")

        assert response.status_code == 404

    def test_thumbnail_no_file_associated(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test thumbnail returns 404 when video has no file path."""
        # Create video without file path
        create_response = test_app.post("/videos", json=sample_video_data)
        video_id = create_response.json()["id"]

        response = test_app.get(f"/videos/{video_id}/thumbnail")

        assert response.status_code == 404
        assert "No video file" in response.json()["detail"]

    def test_thumbnail_file_missing(
        self, test_app: TestClient, video_with_missing_file: dict
    ) -> None:
        """Test thumbnail returns 404 when video file doesn't exist on disk."""
        video_id = video_with_missing_file["id"]

        response = test_app.get(f"/videos/{video_id}/thumbnail")

        assert response.status_code == 404
        assert "not found on disk" in response.json()["detail"]
