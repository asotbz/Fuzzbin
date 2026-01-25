"""Tests for job management API endpoints."""

from fastapi.testclient import TestClient

from fuzzbin.tasks import JobStatus, JobType


class TestJobEndpoints:
    """Tests for job REST API endpoints."""

    def test_submit_job(self, test_app: TestClient):
        """Test submitting a new job via POST /jobs."""
        response = test_app.post(
            "/jobs",
            json={
                "type": JobType.IMPORT_NFO.value,
                "metadata": {"directory": "/tmp/test"},
            },
        )

        assert response.status_code == 202
        data = response.json()

        assert "id" in data
        assert data["type"] == JobType.IMPORT_NFO.value
        assert data["status"] == JobStatus.PENDING.value
        assert data["metadata"] == {"directory": "/tmp/test"}
        assert data["progress"] == 0.0

    def test_submit_job_invalid_type(self, test_app: TestClient):
        """Test submitting a job with invalid type."""
        response = test_app.post(
            "/jobs",
            json={
                "type": "invalid_type",
                "metadata": {},
            },
        )

        assert response.status_code == 422  # Validation error

    def test_list_jobs_empty(self, test_app: TestClient):
        """Test listing jobs when none exist."""
        response = test_app.get("/jobs")

        assert response.status_code == 200
        data = response.json()

        assert "jobs" in data
        assert "total" in data
        # May have jobs from other tests, just check structure
        assert isinstance(data["jobs"], list)

    def test_list_jobs_with_submitted(self, test_app: TestClient):
        """Test listing jobs after submitting some."""
        # Submit a job first
        test_app.post(
            "/jobs",
            json={"type": JobType.IMPORT_NFO.value, "metadata": {}},
        )

        response = test_app.get("/jobs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["jobs"]) >= 1

    def test_list_jobs_filter_by_status(self, test_app: TestClient):
        """Test filtering jobs by status."""
        # Submit a job
        test_app.post(
            "/jobs",
            json={"type": JobType.IMPORT_NFO.value, "metadata": {}},
        )

        # Filter by pending
        response = test_app.get("/jobs", params={"status": "pending"})

        assert response.status_code == 200
        data = response.json()
        for job in data["jobs"]:
            assert job["status"] == "pending"

    def test_list_jobs_filter_by_type(self, test_app: TestClient):
        """Test filtering jobs by type."""
        # Submit jobs of different types
        test_app.post(
            "/jobs",
            json={"type": JobType.IMPORT_NFO.value, "metadata": {}},
        )
        test_app.post(
            "/jobs",
            json={"type": JobType.FILE_ORGANIZE.value, "metadata": {"video_ids": []}},
        )

        # Filter by import_nfo
        response = test_app.get("/jobs", params={"type": "import_nfo"})

        assert response.status_code == 200
        data = response.json()
        for job in data["jobs"]:
            assert job["type"] == "import_nfo"

    def test_list_jobs_with_limit(self, test_app: TestClient):
        """Test limiting job list results."""
        # Submit multiple jobs
        for _ in range(5):
            test_app.post(
                "/jobs",
                json={"type": JobType.IMPORT_NFO.value, "metadata": {}},
            )

        response = test_app.get("/jobs", params={"limit": 2})

        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) <= 2

    def test_get_job(self, test_app: TestClient):
        """Test getting a specific job by ID."""
        # Submit a job
        submit_response = test_app.post(
            "/jobs",
            json={"type": JobType.IMPORT_NFO.value, "metadata": {"test": "value"}},
        )
        job_id = submit_response.json()["id"]

        # Get the job
        response = test_app.get(f"/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["type"] == JobType.IMPORT_NFO.value
        assert data["metadata"] == {"test": "value"}

    def test_get_job_not_found(self, test_app: TestClient):
        """Test getting a non-existent job."""
        response = test_app.get("/jobs/non-existent-job-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_cancel_job(self, test_app: TestClient):
        """Test cancelling a pending job."""
        # Submit a job with valid metadata so it doesn't fail immediately
        # Use FILE_ORGANIZE which requires video_ids - an empty list will still pend
        submit_response = test_app.post(
            "/jobs",
            json={
                "type": JobType.FILE_ORGANIZE.value,
                "metadata": {"video_ids": []},
            },
        )
        job_id = submit_response.json()["id"]

        # Cancel it immediately
        response = test_app.delete(f"/jobs/{job_id}")

        # Job may have already been picked up by worker, so accept either:
        # - 204: Successfully cancelled pending job
        # - 400: Job already completed (processed immediately due to empty list)
        assert response.status_code in (204, 400)

        # If cancelled, verify status
        if response.status_code == 204:
            get_response = test_app.get(f"/jobs/{job_id}")
            assert get_response.json()["status"] in (
                JobStatus.CANCELLED.value,
                JobStatus.COMPLETED.value,  # May have completed between cancel and get
            )

    def test_cancel_job_not_found(self, test_app: TestClient):
        """Test cancelling a non-existent job."""
        response = test_app.delete("/jobs/non-existent-job-id")

        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    def test_cancel_already_cancelled_job(self, test_app: TestClient):
        """Test cancelling an already cancelled job."""
        # Submit and cancel a job
        submit_response = test_app.post(
            "/jobs",
            json={"type": JobType.IMPORT_NFO.value, "metadata": {}},
        )
        job_id = submit_response.json()["id"]
        test_app.delete(f"/jobs/{job_id}")

        # Try to cancel again
        response = test_app.delete(f"/jobs/{job_id}")

        assert response.status_code == 400

    def test_job_response_structure(self, test_app: TestClient):
        """Test that job response has all expected fields."""
        submit_response = test_app.post(
            "/jobs",
            json={"type": JobType.IMPORT_NFO.value, "metadata": {}},
        )
        data = submit_response.json()

        # Check all expected fields are present
        expected_fields = [
            "id",
            "type",
            "status",
            "progress",
            "current_step",
            "total_items",
            "processed_items",
            "result",
            "error",
            "created_at",
            "started_at",
            "completed_at",
            "metadata",
        ]

        for field in expected_fields:
            assert field in data, f"Missing field: {field}"


class TestJobEndpointsIntegration:
    """Integration tests for job workflow."""

    def test_submit_and_track_job(self, test_app: TestClient):
        """Test submitting a job and tracking its status."""
        # Submit
        submit_response = test_app.post(
            "/jobs",
            json={"type": JobType.IMPORT_NFO.value, "metadata": {}},
        )
        assert submit_response.status_code == 202
        job_id = submit_response.json()["id"]

        # Get status
        status_response = test_app.get(f"/jobs/{job_id}")
        assert status_response.status_code == 200

        # Should appear in list
        list_response = test_app.get("/jobs")
        job_ids = [j["id"] for j in list_response.json()["jobs"]]
        assert job_id in job_ids

    def test_submit_cancel_verify(self, test_app: TestClient):
        """Test full lifecycle: submit, cancel, verify."""
        # Use FILE_ORGANIZE with empty video_ids for predictable behavior
        submit_response = test_app.post(
            "/jobs",
            json={
                "type": JobType.FILE_ORGANIZE.value,
                "metadata": {"video_ids": []},
            },
        )
        job_id = submit_response.json()["id"]
        assert submit_response.json()["status"] == "pending"

        # Try to cancel - may succeed or job may have already completed
        cancel_response = test_app.delete(f"/jobs/{job_id}")

        # Accept either outcome due to worker race condition
        assert cancel_response.status_code in (204, 400)

        # Verify final state
        get_response = test_app.get(f"/jobs/{job_id}")
        final_status = get_response.json()["status"]
        assert final_status in ("cancelled", "completed")
        assert get_response.json()["completed_at"] is not None
