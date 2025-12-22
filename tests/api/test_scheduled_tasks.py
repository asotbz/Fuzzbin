"""Tests for scheduled task API endpoints (Phase 7)."""

import pytest
from fastapi.testclient import TestClient

from fuzzbin.tasks import JobType


class TestScheduledTaskCreate:
    """Tests for POST /jobs/scheduled endpoint."""

    def test_create_scheduled_task(self, test_app: TestClient) -> None:
        """Test creating a scheduled task."""
        response = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Daily Library Scan",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "0 0 * * *",
                "enabled": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Daily Library Scan"
        assert data["job_type"] == JobType.LIBRARY_SCAN.value
        assert data["cron_expression"] == "0 0 * * *"
        assert data["enabled"] is True
        assert "id" in data
        assert "next_run_at" in data
        assert data["run_count"] == 0

    def test_create_scheduled_task_with_metadata(self, test_app: TestClient) -> None:
        """Test creating a scheduled task with metadata."""
        response = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Metadata Refresh",
                "job_type": JobType.METADATA_REFRESH.value,
                "cron_expression": "0 2 * * *",
                "metadata": {
                    "max_age_days": 30,
                    "sources": ["imvdb", "discogs"],
                },
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["metadata"]["max_age_days"] == 30
        assert "imvdb" in data["metadata"]["sources"]

    def test_create_scheduled_task_disabled(self, test_app: TestClient) -> None:
        """Test creating a disabled scheduled task."""
        response = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Disabled Task",
                "job_type": JobType.IMPORT_NFO.value,
                "cron_expression": "0 0 * * 0",
                "enabled": False,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["enabled"] is False

    def test_create_scheduled_task_invalid_cron(self, test_app: TestClient) -> None:
        """Test creating a task with invalid cron expression."""
        response = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Invalid Cron",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "invalid cron",
            },
        )

        assert response.status_code == 400
        assert "cron" in response.json()["detail"].lower()

    def test_create_scheduled_task_invalid_job_type(self, test_app: TestClient) -> None:
        """Test creating a task with invalid job type."""
        response = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Invalid Type",
                "job_type": "not_a_valid_type",
                "cron_expression": "0 0 * * *",
            },
        )

        assert response.status_code == 422  # Validation error


class TestScheduledTaskList:
    """Tests for GET /jobs/scheduled endpoint."""

    def test_list_scheduled_tasks_empty(self, test_app: TestClient) -> None:
        """Test listing scheduled tasks when none exist."""
        response = test_app.get("/jobs/scheduled")

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert isinstance(data["tasks"], list)

    def test_list_scheduled_tasks(self, test_app: TestClient) -> None:
        """Test listing scheduled tasks."""
        # Create some tasks
        test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Task 1",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "0 0 * * *",
            },
        )
        test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Task 2",
                "job_type": JobType.METADATA_REFRESH.value,
                "cron_expression": "0 2 * * *",
            },
        )

        response = test_app.get("/jobs/scheduled")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["tasks"]) >= 2

    def test_list_scheduled_tasks_enabled_only(self, test_app: TestClient) -> None:
        """Test filtering to only enabled tasks."""
        # Create enabled task
        test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Enabled",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "0 0 * * *",
                "enabled": True,
            },
        )
        # Create disabled task
        test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Disabled",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "0 0 * * *",
                "enabled": False,
            },
        )

        response = test_app.get("/jobs/scheduled", params={"enabled_only": True})

        assert response.status_code == 200
        data = response.json()
        for task in data["tasks"]:
            assert task["enabled"] is True


class TestScheduledTaskGet:
    """Tests for GET /jobs/scheduled/{task_id} endpoint."""

    def test_get_scheduled_task(self, test_app: TestClient) -> None:
        """Test getting a specific scheduled task."""
        # Create task
        create_r = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Test Task",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "*/30 * * * *",
            },
        )
        task_id = create_r.json()["id"]

        response = test_app.get(f"/jobs/scheduled/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["name"] == "Test Task"
        assert data["cron_expression"] == "*/30 * * * *"

    def test_get_scheduled_task_not_found(self, test_app: TestClient) -> None:
        """Test getting non-existent scheduled task."""
        response = test_app.get("/jobs/scheduled/99999")

        assert response.status_code == 404


class TestScheduledTaskUpdate:
    """Tests for PATCH /jobs/scheduled/{task_id} endpoint."""

    def test_update_scheduled_task_name(self, test_app: TestClient) -> None:
        """Test updating a scheduled task's name."""
        # Create task
        create_r = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Original Name",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "0 0 * * *",
            },
        )
        task_id = create_r.json()["id"]

        response = test_app.patch(
            f"/jobs/scheduled/{task_id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_update_scheduled_task_cron(self, test_app: TestClient) -> None:
        """Test updating a scheduled task's cron expression."""
        create_r = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Test",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "0 0 * * *",
            },
        )
        task_id = create_r.json()["id"]

        response = test_app.patch(
            f"/jobs/scheduled/{task_id}",
            json={"cron_expression": "0 */2 * * *"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cron_expression"] == "0 */2 * * *"
        # next_run_at should be updated
        assert data["next_run_at"] is not None

    def test_update_scheduled_task_enable_disable(self, test_app: TestClient) -> None:
        """Test enabling/disabling a scheduled task."""
        create_r = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Test",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "0 0 * * *",
                "enabled": True,
            },
        )
        task_id = create_r.json()["id"]

        # Disable
        response = test_app.patch(
            f"/jobs/scheduled/{task_id}",
            json={"enabled": False},
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is False

        # Re-enable
        response = test_app.patch(
            f"/jobs/scheduled/{task_id}",
            json={"enabled": True},
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is True

    def test_update_scheduled_task_invalid_cron(self, test_app: TestClient) -> None:
        """Test updating with invalid cron expression."""
        create_r = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Test",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "0 0 * * *",
            },
        )
        task_id = create_r.json()["id"]

        response = test_app.patch(
            f"/jobs/scheduled/{task_id}",
            json={"cron_expression": "bad cron"},
        )

        assert response.status_code == 400

    def test_update_scheduled_task_not_found(self, test_app: TestClient) -> None:
        """Test updating non-existent task."""
        response = test_app.patch(
            "/jobs/scheduled/99999",
            json={"name": "New Name"},
        )

        assert response.status_code == 404


class TestScheduledTaskDelete:
    """Tests for DELETE /jobs/scheduled/{task_id} endpoint."""

    def test_delete_scheduled_task(self, test_app: TestClient) -> None:
        """Test deleting a scheduled task."""
        # Create task
        create_r = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "To Delete",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "0 0 * * *",
            },
        )
        task_id = create_r.json()["id"]

        # Delete
        response = test_app.delete(f"/jobs/scheduled/{task_id}")
        assert response.status_code == 204

        # Verify deleted
        get_r = test_app.get(f"/jobs/scheduled/{task_id}")
        assert get_r.status_code == 404

    def test_delete_scheduled_task_not_found(self, test_app: TestClient) -> None:
        """Test deleting non-existent task."""
        response = test_app.delete("/jobs/scheduled/99999")

        assert response.status_code == 404


class TestScheduledTaskRun:
    """Tests for POST /jobs/scheduled/{task_id}/run endpoint."""

    def test_run_scheduled_task_now(self, test_app: TestClient) -> None:
        """Test manually triggering a scheduled task."""
        # Create task
        create_r = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Manual Run Test",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": "0 0 * * *",
                "metadata": {"directory": "/tmp/test"},
            },
        )
        task_id = create_r.json()["id"]

        # Trigger manual run
        response = test_app.post(f"/jobs/scheduled/{task_id}/run")

        assert response.status_code == 202
        data = response.json()
        assert "id" in data  # Job ID
        assert data["type"] == JobType.LIBRARY_SCAN.value
        assert data["status"] == "pending"

    def test_run_scheduled_task_not_found(self, test_app: TestClient) -> None:
        """Test running non-existent task."""
        response = test_app.post("/jobs/scheduled/99999/run")

        assert response.status_code == 404


class TestCronExpressionFormats:
    """Tests for various cron expression formats."""

    @pytest.mark.parametrize(
        "cron_expr,description",
        [
            ("0 * * * *", "Every hour"),
            ("0 0 * * *", "Daily at midnight"),
            ("0 0 * * 0", "Weekly on Sunday"),
            ("*/15 * * * *", "Every 15 minutes"),
            ("0 0 1 * *", "Monthly on 1st"),
            ("30 4 * * *", "Daily at 4:30 AM"),
        ],
    )
    def test_valid_cron_expressions(
        self, test_app: TestClient, cron_expr: str, description: str
    ) -> None:
        """Test various valid cron expression formats."""
        response = test_app.post(
            "/jobs/scheduled",
            json={
                "name": description,
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": cron_expr,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["cron_expression"] == cron_expr
        assert data["next_run_at"] is not None

    @pytest.mark.parametrize(
        "cron_expr",
        [
            "invalid",
            "* * *",  # Too few fields
            "* * * * * *",  # Too many fields
            "60 * * * *",  # Invalid minute
            "* 25 * * *",  # Invalid hour
        ],
    )
    def test_invalid_cron_expressions(
        self, test_app: TestClient, cron_expr: str
    ) -> None:
        """Test that invalid cron expressions are rejected."""
        response = test_app.post(
            "/jobs/scheduled",
            json={
                "name": "Invalid Cron Test",
                "job_type": JobType.LIBRARY_SCAN.value,
                "cron_expression": cron_expr,
            },
        )

        assert response.status_code == 400
