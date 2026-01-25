"""Tests for file management endpoints."""

from pathlib import Path
from fastapi.testclient import TestClient


class TestOrganizeVideo:
    """Tests for POST /files/videos/{video_id}/organize endpoint."""

    def test_organize_video_not_found(self, test_app: TestClient) -> None:
        """Test organizing a non-existent video."""
        response = test_app.post("/files/videos/99999/organize")
        assert response.status_code == 404

    def test_organize_dry_run(self, test_app: TestClient, video_with_file: dict) -> None:
        """Test organize dry run returns target paths without moving."""
        video_id = video_with_file["id"]
        original_path = video_with_file["video_file_path"]

        response = test_app.post(
            f"/files/videos/{video_id}/organize",
            json={"dry_run": True},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["video_id"] == video_id
        assert data["dry_run"] is True
        assert data["status"] == "dry_run"
        assert data["target_video_path"] is not None

        # File should still be at original location
        assert Path(original_path).exists()


class TestDeleteVideoFiles:
    """Tests for DELETE /files/videos/{video_id} endpoint."""

    def test_delete_video_not_found(self, test_app: TestClient) -> None:
        """Test deleting files for non-existent video."""
        response = test_app.delete("/files/videos/99999")
        assert response.status_code == 404

    def test_soft_delete_success(self, test_app: TestClient, video_with_file: dict) -> None:
        """Test soft delete moves file to trash."""
        video_id = video_with_file["id"]
        original_path = Path(video_with_file["video_file_path"])

        response = test_app.delete(f"/files/videos/{video_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["video_id"] == video_id
        assert data["deleted"] is True
        assert data["hard_delete"] is False
        assert data["trash_path"] is not None

        # Original file should be gone
        assert not original_path.exists()

        # Trash file should exist
        assert Path(data["trash_path"]).exists()

    def test_hard_delete_success(self, test_app: TestClient, video_with_file: dict) -> None:
        """Test hard delete permanently removes file."""
        video_id = video_with_file["id"]
        original_path = Path(video_with_file["video_file_path"])

        response = test_app.delete(
            f"/files/videos/{video_id}",
            params={"hard_delete": True},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["video_id"] == video_id
        assert data["deleted"] is True
        assert data["hard_delete"] is True
        assert data["trash_path"] is None

        # File should be completely gone
        assert not original_path.exists()


class TestRestoreVideo:
    """Tests for POST /files/videos/{video_id}/restore endpoint."""

    def test_restore_not_deleted(self, test_app: TestClient, video_with_file: dict) -> None:
        """Test restoring a video that's not deleted."""
        video_id = video_with_file["id"]

        response = test_app.post(f"/files/videos/{video_id}/restore")

        # Should fail because video isn't deleted
        assert response.status_code == 400
        assert "not deleted" in response.json()["detail"]

    def test_restore_success(self, test_app: TestClient, video_with_file: dict) -> None:
        """Test successful restore from trash."""
        video_id = video_with_file["id"]
        _original_path = Path(video_with_file["video_file_path"])

        # First soft delete
        delete_response = test_app.delete(f"/files/videos/{video_id}")
        assert delete_response.status_code == 200
        trash_path = Path(delete_response.json()["trash_path"])

        # Then restore
        response = test_app.post(f"/files/videos/{video_id}/restore")

        assert response.status_code == 200
        data = response.json()

        assert data["video_id"] == video_id
        assert data["restored"] is True
        assert data["restored_path"] is not None

        # Trash file should be gone
        assert not trash_path.exists()

        # Restored file should exist
        assert Path(data["restored_path"]).exists()


class TestFindDuplicates:
    """Tests for GET /files/videos/{video_id}/duplicates endpoint."""

    def test_duplicates_video_not_found(self, test_app: TestClient) -> None:
        """Test finding duplicates for non-existent video."""
        response = test_app.get("/files/videos/99999/duplicates")
        assert response.status_code == 404

    def test_duplicates_none_found(self, test_app: TestClient, video_with_file: dict) -> None:
        """Test no duplicates found."""
        video_id = video_with_file["id"]

        response = test_app.get(f"/files/videos/{video_id}/duplicates")

        assert response.status_code == 200
        data = response.json()

        assert data["video_id"] == video_id
        assert data["duplicates"] == []
        assert data["total"] == 0

    def test_duplicates_by_metadata(self, test_app: TestClient, sample_video_data: dict) -> None:
        """Test finding duplicates by metadata."""
        # Create two videos with same title/artist
        video1 = test_app.post("/videos", json=sample_video_data)
        assert video1.status_code == 201
        video1_id = video1.json()["id"]

        video2 = test_app.post("/videos", json=sample_video_data)
        assert video2.status_code == 201
        video2_id = video2.json()["id"]

        # Search for duplicates of video1
        response = test_app.get(
            f"/files/videos/{video1_id}/duplicates",
            params={"method": "metadata"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["video_id"] == video1_id
        assert data["total"] >= 1

        # Should find video2 as duplicate
        dupe_ids = [d["video_id"] for d in data["duplicates"]]
        assert video2_id in dupe_ids


class TestResolveDuplicates:
    """Tests for POST /files/duplicates/resolve endpoint."""

    def test_resolve_keep_video_not_found(self, test_app: TestClient) -> None:
        """Test resolving with non-existent keep video."""
        response = test_app.post(
            "/files/duplicates/resolve",
            json={
                "keep_video_id": 99999,
                "remove_video_ids": [1, 2],
            },
        )
        assert response.status_code == 404

    def test_resolve_removes_duplicates(
        self, test_app: TestClient, sample_video_data: dict
    ) -> None:
        """Test resolving duplicates removes specified videos."""
        # Create duplicates
        video1 = test_app.post("/videos", json=sample_video_data)
        video1_id = video1.json()["id"]

        video2 = test_app.post("/videos", json=sample_video_data)
        video2_id = video2.json()["id"]

        # Resolve - keep video1, remove video2
        response = test_app.post(
            "/files/duplicates/resolve",
            json={
                "keep_video_id": video1_id,
                "remove_video_ids": [video2_id],
                "hard_delete": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["kept_video_id"] == video1_id
        assert data["removed_count"] == 1
        assert video2_id in data["removed_video_ids"]


class TestVerifyLibrary:
    """Tests for GET /files/library/verify endpoint."""

    def test_verify_empty_library(self, test_app: TestClient) -> None:
        """Test verifying empty library."""
        response = test_app.get(
            "/files/library/verify",
            params={"scan_orphans": False},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["videos_checked"] == 0
        assert data["total_issues"] == 0

    def test_verify_finds_missing_files(
        self, test_app: TestClient, video_with_missing_file: dict
    ) -> None:
        """Test verification finds videos with missing files."""
        response = test_app.get(
            "/files/library/verify",
            params={"scan_orphans": False},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["missing_files"] >= 1

        # Should have an issue for the missing file
        missing_issues = [i for i in data["issues"] if i["issue_type"] == "missing_file"]
        assert len(missing_issues) >= 1

    def test_verify_finds_orphans(self, test_app: TestClient, orphan_file: Path) -> None:
        """Test verification finds orphaned files."""
        response = test_app.get(
            "/files/library/verify",
            params={"scan_orphans": True},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["orphaned_files"] >= 1


class TestRepairLibrary:
    """Tests for POST /files/library/repair endpoint."""

    def test_repair_empty_library(self, test_app: TestClient) -> None:
        """Test repairing empty library."""
        response = test_app.post("/files/library/repair")

        assert response.status_code == 200
        data = response.json()

        assert data["total_repaired"] == 0

    def test_repair_missing_files(
        self, test_app: TestClient, video_with_missing_file: dict
    ) -> None:
        """Test repairing updates status for missing files."""
        # Repair
        response = test_app.post(
            "/files/library/repair",
            json={
                "repair_missing_files": True,
                "repair_broken_nfos": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["repaired_missing_files"] >= 1

        # Verify video status is now 'missing'
        video_id = video_with_missing_file["id"]
        video_response = test_app.get(f"/videos/{video_id}")
        assert video_response.json()["status"] == "missing"
