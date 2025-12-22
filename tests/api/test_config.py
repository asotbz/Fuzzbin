"""Tests for configuration management API endpoints."""

from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

import fuzzbin
from fuzzbin.common.config import Config, ConfigSafetyLevel
from fuzzbin.common.config_manager import ConfigManager


class TestGetConfig:
    """Tests for GET /config endpoint."""

    def test_get_config_returns_full_config(self, test_app: TestClient) -> None:
        """GET /config returns complete configuration."""
        response = test_app.get("/config")
        assert response.status_code == 200

        data = response.json()
        assert "config" in data
        assert "http" in data["config"]
        assert "logging" in data["config"]
        assert "database" in data["config"]

    def test_get_config_includes_path(self, test_app: TestClient) -> None:
        """GET /config includes config_path if set."""
        response = test_app.get("/config")
        assert response.status_code == 200

        data = response.json()
        # config_path may be None in tests (no YAML file)
        assert "config_path" in data


class TestGetConfigField:
    """Tests for GET /config/field/{path} endpoint."""

    def test_get_field_http_timeout(self, test_app: TestClient) -> None:
        """GET /config/field/http.timeout returns timeout value."""
        response = test_app.get("/config/field/http.timeout")
        assert response.status_code == 200

        data = response.json()
        assert data["path"] == "http.timeout"
        assert isinstance(data["value"], int)
        assert data["safety_level"] == "safe"

    def test_get_field_nested_path(self, test_app: TestClient) -> None:
        """GET /config/field with nested path returns correct value."""
        response = test_app.get("/config/field/logging.level")
        assert response.status_code == 200

        data = response.json()
        assert data["path"] == "logging.level"
        assert isinstance(data["value"], str)

    def test_get_field_not_found(self, test_app: TestClient) -> None:
        """GET /config/field with invalid path returns 404."""
        response = test_app.get("/config/field/nonexistent.path")
        assert response.status_code == 404

    def test_get_field_returns_safety_level(self, test_app: TestClient) -> None:
        """GET /config/field includes safety level."""
        # Test a field that requires reload
        response = test_app.get("/config/field/http.max_connections")
        assert response.status_code == 200

        data = response.json()
        assert data["safety_level"] == "requires_reload"


class TestUpdateConfig:
    """Tests for PATCH /config endpoint."""

    def test_update_safe_field(self, test_app: TestClient) -> None:
        """PATCH /config with safe field succeeds."""
        # Get original value
        original_response = test_app.get("/config/field/http.timeout")
        original_value = original_response.json()["value"]

        # Update to new value
        new_value = 45
        response = test_app.patch(
            "/config",
            json={"updates": {"http.timeout": new_value}},
        )
        assert response.status_code == 200

        data = response.json()
        assert "http.timeout" in data["updated_fields"]
        assert data["safety_level"] == "safe"
        assert data["required_actions"] == []

        # Verify change applied
        verify_response = test_app.get("/config/field/http.timeout")
        assert verify_response.json()["value"] == new_value

        # Restore original
        test_app.patch("/config", json={"updates": {"http.timeout": original_value}})

    def test_update_requires_reload_without_force_returns_409(
        self, test_app: TestClient
    ) -> None:
        """PATCH /config with requires_reload field returns 409 without force."""
        response = test_app.patch(
            "/config",
            json={"updates": {"http.max_connections": 200}},
        )
        assert response.status_code == 409

        data = response.json()["detail"]
        assert "affected_fields" in data
        assert len(data["affected_fields"]) == 1
        assert data["affected_fields"][0]["safety_level"] == "requires_reload"
        assert "required_actions" in data

    def test_update_requires_reload_with_force_succeeds(
        self, test_app: TestClient
    ) -> None:
        """PATCH /config with requires_reload field succeeds with force=true."""
        # Get original
        original_response = test_app.get("/config/field/http.max_connections")
        original_value = original_response.json()["value"]

        response = test_app.patch(
            "/config",
            json={"updates": {"http.max_connections": 150}, "force": True},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["safety_level"] == "requires_reload"
        assert len(data["required_actions"]) > 0

        # Restore
        test_app.patch(
            "/config",
            json={"updates": {"http.max_connections": original_value}, "force": True},
        )

    def test_update_multiple_fields(self, test_app: TestClient) -> None:
        """PATCH /config with multiple safe fields updates all."""
        # Get originals
        orig_timeout = test_app.get("/config/field/http.timeout").json()["value"]
        orig_redirects = test_app.get("/config/field/http.max_redirects").json()["value"]

        response = test_app.patch(
            "/config",
            json={
                "updates": {
                    "http.timeout": 50,
                    "http.max_redirects": 8,
                },
                "description": "Test batch update",
            },
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["updated_fields"]) == 2
        assert "http.timeout" in data["updated_fields"]
        assert "http.max_redirects" in data["updated_fields"]

        # Restore
        test_app.patch(
            "/config",
            json={
                "updates": {
                    "http.timeout": orig_timeout,
                    "http.max_redirects": orig_redirects,
                }
            },
        )

    def test_update_invalid_value_returns_400(self, test_app: TestClient) -> None:
        """PATCH /config with invalid value returns 400."""
        response = test_app.patch(
            "/config",
            json={"updates": {"http.timeout": -5}},  # Negative timeout invalid
        )
        assert response.status_code == 400

    def test_update_with_description_recorded(self, test_app: TestClient) -> None:
        """PATCH /config with description records it in history."""
        orig_timeout = test_app.get("/config/field/http.timeout").json()["value"]

        response = test_app.patch(
            "/config",
            json={
                "updates": {"http.timeout": 55},
                "description": "Custom description for test",
            },
        )
        assert response.status_code == 200

        # Check history includes description
        history_response = test_app.get("/config/history")
        history = history_response.json()

        # Restore first
        test_app.patch("/config", json={"updates": {"http.timeout": orig_timeout}})


class TestConfigHistory:
    """Tests for GET /config/history endpoint."""

    def test_get_history_returns_entries(self, test_app: TestClient) -> None:
        """GET /config/history returns history entries."""
        response = test_app.get("/config/history")
        assert response.status_code == 200

        data = response.json()
        assert "entries" in data
        assert "current_index" in data
        assert "can_undo" in data
        assert "can_redo" in data
        assert isinstance(data["entries"], list)

    def test_get_history_with_limit(self, test_app: TestClient) -> None:
        """GET /config/history respects limit parameter."""
        response = test_app.get("/config/history?limit=5")
        assert response.status_code == 200

        data = response.json()
        assert len(data["entries"]) <= 5


class TestUndoRedo:
    """Tests for POST /config/undo and POST /config/redo endpoints."""

    def test_undo_after_change(self, test_app: TestClient) -> None:
        """POST /config/undo reverts a change."""
        # Get original
        orig_response = test_app.get("/config/field/http.timeout")
        orig_value = orig_response.json()["value"]

        # Make change
        new_value = orig_value + 10
        test_app.patch("/config", json={"updates": {"http.timeout": new_value}})

        # Verify change
        changed_response = test_app.get("/config/field/http.timeout")
        assert changed_response.json()["value"] == new_value

        # Undo
        undo_response = test_app.post("/config/undo")
        assert undo_response.status_code == 200
        assert undo_response.json()["success"] is True

        # Verify undone
        verify_response = test_app.get("/config/field/http.timeout")
        assert verify_response.json()["value"] == orig_value

    def test_undo_with_no_history_returns_400(self, test_app: TestClient) -> None:
        """POST /config/undo with empty history returns 400."""
        # Keep undoing until we run out of history
        for _ in range(100):  # Safety limit
            response = test_app.post("/config/undo")
            if response.status_code == 400:
                break

        # Now verify we get 400
        response = test_app.post("/config/undo")
        assert response.status_code == 400

    def test_redo_after_undo(self, test_app: TestClient) -> None:
        """POST /config/redo restores an undone change."""
        # Get original
        orig_response = test_app.get("/config/field/http.timeout")
        orig_value = orig_response.json()["value"]

        # Make change
        new_value = orig_value + 15
        test_app.patch("/config", json={"updates": {"http.timeout": new_value}})

        # Undo
        test_app.post("/config/undo")

        # Redo
        redo_response = test_app.post("/config/redo")
        assert redo_response.status_code == 200
        assert redo_response.json()["success"] is True

        # Verify redone
        verify_response = test_app.get("/config/field/http.timeout")
        assert verify_response.json()["value"] == new_value

        # Restore original
        test_app.patch("/config", json={"updates": {"http.timeout": orig_value}})


class TestSafetyLevel:
    """Tests for GET /config/safety/{path} endpoint."""

    def test_get_safety_safe_field(self, test_app: TestClient) -> None:
        """GET /config/safety for safe field returns correct level."""
        response = test_app.get("/config/safety/http.timeout")
        assert response.status_code == 200

        data = response.json()
        assert data["path"] == "http.timeout"
        assert data["safety_level"] == "safe"
        assert "description" in data

    def test_get_safety_requires_reload_field(self, test_app: TestClient) -> None:
        """GET /config/safety for requires_reload field returns correct level."""
        response = test_app.get("/config/safety/http.max_connections")
        assert response.status_code == 200

        data = response.json()
        assert data["safety_level"] == "requires_reload"

    def test_get_safety_affects_state_field(self, test_app: TestClient) -> None:
        """GET /config/safety for affects_state field returns correct level."""
        response = test_app.get("/config/safety/database.database_path")
        assert response.status_code == 200

        data = response.json()
        assert data["safety_level"] == "affects_state"


class TestClientList:
    """Tests for GET /config/clients endpoint."""

    def test_list_clients_returns_list(self, test_app: TestClient) -> None:
        """GET /config/clients returns list of registered clients."""
        response = test_app.get("/config/clients")
        assert response.status_code == 200

        data = response.json()
        assert "clients" in data
        assert "total" in data
        assert isinstance(data["clients"], list)
        assert data["total"] == len(data["clients"])


class TestClientStats:
    """Tests for GET /config/clients/{name}/stats endpoint."""

    def test_get_stats_not_found(self, test_app: TestClient) -> None:
        """GET /config/clients/{name}/stats with unknown client returns 404."""
        response = test_app.get("/config/clients/unknown_client/stats")
        assert response.status_code == 404


class TestConflictResponse:
    """Tests for 409 Conflict response structure."""

    def test_conflict_response_structure(self, test_app: TestClient) -> None:
        """409 response includes all required fields."""
        response = test_app.patch(
            "/config",
            json={"updates": {"database.database_path": "/new/path/db.sqlite"}},
        )
        assert response.status_code == 409

        data = response.json()["detail"]

        # Verify structure
        assert "detail" in data
        assert "error_type" in data
        assert data["error_type"] == "config_conflict"
        assert "affected_fields" in data
        assert "required_actions" in data
        assert "message" in data

        # Verify affected field details
        affected = data["affected_fields"][0]
        assert "path" in affected
        assert "safety_level" in affected
        assert "current_value" in affected
        assert "requested_value" in affected

    def test_conflict_response_required_actions(self, test_app: TestClient) -> None:
        """409 response includes appropriate required_actions."""
        response = test_app.patch(
            "/config",
            json={"updates": {"database.database_path": "/new/path/db.sqlite"}},
        )
        assert response.status_code == 409

        data = response.json()["detail"]

        # Should have database-related action
        action_types = [a["action_type"] for a in data["required_actions"]]
        assert any("database" in at for at in action_types)
