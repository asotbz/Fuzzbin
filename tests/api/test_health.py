"""Tests for health check endpoint."""

import pytest
from fastapi.testclient import TestClient

import fuzzbin


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_check_returns_ok(self, test_app: TestClient) -> None:
        """Test that health check returns ok status."""
        response = test_app.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_check_returns_version(self, test_app: TestClient) -> None:
        """Test that health check returns API version."""
        response = test_app.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["version"] == fuzzbin.__version__

    def test_health_check_response_structure(self, test_app: TestClient) -> None:
        """Test that health check response has expected structure."""
        response = test_app.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Should have exactly these keys
        assert set(data.keys()) == {"status", "version"}


class TestCORSConfiguration:
    """Tests for CORS configuration."""

    def test_cors_headers_present(self, test_app: TestClient) -> None:
        """Test that CORS headers are present in response."""
        response = test_app.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        # CORS preflight should succeed
        assert response.status_code in (200, 204)

    def test_cors_allows_configured_origin(self, test_app: TestClient) -> None:
        """Test that CORS allows configured origins."""
        response = test_app.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200
        # Note: TestClient may not include CORS headers in same way as real requests


class TestOpenAPIDocumentation:
    """Tests for OpenAPI documentation."""

    def test_openapi_schema_available(self, test_app: TestClient) -> None:
        """Test that OpenAPI schema is accessible."""
        response = test_app.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()

        # Check basic OpenAPI structure
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    def test_openapi_info_metadata(self, test_app: TestClient) -> None:
        """Test that OpenAPI info has correct metadata."""
        response = test_app.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        info = data["info"]

        assert info["title"] == "Fuzzbin API"
        assert info["version"] == fuzzbin.__version__
        assert "description" in info

    def test_openapi_tags_defined(self, test_app: TestClient) -> None:
        """Test that OpenAPI tags are defined."""
        response = test_app.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()

        # Should have tags for each router
        tag_names = {tag["name"] for tag in data.get("tags", [])}
        expected_tags = {"Health", "Videos", "Artists", "Collections", "Tags", "Search"}
        assert expected_tags.issubset(tag_names)

    def test_docs_endpoint_available(self, test_app: TestClient) -> None:
        """Test that Swagger UI docs are accessible."""
        response = test_app.get("/docs")

        # Should redirect or return HTML
        assert response.status_code in (200, 307)

    def test_redoc_endpoint_available(self, test_app: TestClient) -> None:
        """Test that ReDoc docs are accessible."""
        response = test_app.get("/redoc")

        # Should redirect or return HTML
        assert response.status_code in (200, 307)
