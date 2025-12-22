"""Tests for authentication routes and security."""

from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

import fuzzbin
from fuzzbin.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    is_default_password,
    DEFAULT_PASSWORD_HASH,
    LoginThrottle,
)
from fuzzbin.common.config import Config, DatabaseConfig, LoggingConfig
from fuzzbin.core.db import VideoRepository
from fuzzbin.web.main import create_app
from fuzzbin.web.dependencies import get_repository, get_api_settings
from fuzzbin.web.settings import APISettings, get_settings


# Test constants
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"
TEST_USERNAME = "admin"
TEST_PASSWORD = "changeme"
TEST_NEW_PASSWORD = "newpassword123"


class TestPasswordHashing:
    """Tests for password hashing utilities."""

    def test_hash_password_returns_bcrypt_hash(self):
        """Test that hash_password returns a bcrypt hash."""
        hashed = hash_password("testpassword")
        assert hashed.startswith("$2b$")
        assert len(hashed) == 60

    def test_verify_password_correct(self):
        """Test that verify_password returns True for correct password."""
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_password_incorrect(self):
        """Test that verify_password returns False for wrong password."""
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_empty_string(self):
        """Test that verify_password handles empty strings."""
        hashed = hash_password("mypassword")
        assert verify_password("", hashed) is False

    def test_is_default_password_with_default(self):
        """Test is_default_password returns True for default password."""
        # Use the actual default hash from the migration
        assert is_default_password(DEFAULT_PASSWORD_HASH) is True

    def test_is_default_password_with_custom(self):
        """Test is_default_password returns False for custom password."""
        custom_hash = hash_password("custompassword")
        assert is_default_password(custom_hash) is False


class TestJWTTokens:
    """Tests for JWT token creation and validation."""

    def test_create_access_token(self):
        """Test that create_access_token returns valid JWT."""
        data = {"sub": "testuser", "user_id": 1}
        token = create_access_token(
            data=data,
            secret_key=TEST_JWT_SECRET,
            expires_minutes=30,
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_access_token(self):
        """Test that decode_token correctly decodes access token."""
        data = {"sub": "testuser", "user_id": 1}
        token = create_access_token(
            data=data,
            secret_key=TEST_JWT_SECRET,
            expires_minutes=30,
        )
        
        payload = decode_token(
            token=token,
            secret_key=TEST_JWT_SECRET,
            expected_type="access",
        )
        
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["user_id"] == 1
        assert payload["type"] == "access"

    def test_decode_token_with_wrong_secret(self):
        """Test that decode_token returns None for wrong secret."""
        data = {"sub": "testuser", "user_id": 1}
        token = create_access_token(
            data=data,
            secret_key=TEST_JWT_SECRET,
            expires_minutes=30,
        )
        
        payload = decode_token(
            token=token,
            secret_key="wrong-secret",
        )
        
        assert payload is None

    def test_decode_token_with_wrong_type(self):
        """Test that decode_token returns None for wrong token type."""
        data = {"sub": "testuser", "user_id": 1}
        token = create_access_token(
            data=data,
            secret_key=TEST_JWT_SECRET,
            expires_minutes=30,
        )
        
        payload = decode_token(
            token=token,
            secret_key=TEST_JWT_SECRET,
            expected_type="refresh",  # Wrong type
        )
        
        assert payload is None

    def test_create_refresh_token(self):
        """Test that create_refresh_token returns valid JWT with refresh type."""
        data = {"sub": "testuser", "user_id": 1}
        token = create_refresh_token(
            data=data,
            secret_key=TEST_JWT_SECRET,
            expires_minutes=10080,
        )
        
        payload = decode_token(
            token=token,
            secret_key=TEST_JWT_SECRET,
            expected_type="refresh",
        )
        
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_expired_token(self):
        """Test that decode_token returns None for expired token."""
        data = {"sub": "testuser", "user_id": 1}
        # Create token that expires immediately
        token = create_access_token(
            data=data,
            secret_key=TEST_JWT_SECRET,
            expires_minutes=-1,  # Expired
        )
        
        payload = decode_token(
            token=token,
            secret_key=TEST_JWT_SECRET,
        )
        
        assert payload is None


class TestLoginThrottle:
    """Tests for brute-force login throttling."""

    def test_not_blocked_initially(self):
        """Test that IP is not blocked initially."""
        throttle = LoginThrottle(max_attempts=5, window_seconds=60)
        assert throttle.is_blocked("192.168.1.1") is False

    def test_blocked_after_max_attempts(self):
        """Test that IP is blocked after max failed attempts."""
        throttle = LoginThrottle(max_attempts=3, window_seconds=60)
        
        for _ in range(3):
            throttle.record_failure("192.168.1.1")
        
        assert throttle.is_blocked("192.168.1.1") is True

    def test_not_blocked_below_max_attempts(self):
        """Test that IP is not blocked below max attempts."""
        throttle = LoginThrottle(max_attempts=5, window_seconds=60)
        
        for _ in range(4):
            throttle.record_failure("192.168.1.1")
        
        assert throttle.is_blocked("192.168.1.1") is False

    def test_clear_resets_attempts(self):
        """Test that clear() resets failed attempts for an IP."""
        throttle = LoginThrottle(max_attempts=3, window_seconds=60)
        
        for _ in range(3):
            throttle.record_failure("192.168.1.1")
        
        assert throttle.is_blocked("192.168.1.1") is True
        
        throttle.clear("192.168.1.1")
        assert throttle.is_blocked("192.168.1.1") is False

    def test_remaining_attempts(self):
        """Test get_remaining_attempts returns correct value."""
        throttle = LoginThrottle(max_attempts=5, window_seconds=60)
        
        assert throttle.get_remaining_attempts("192.168.1.1") == 5
        
        throttle.record_failure("192.168.1.1")
        assert throttle.get_remaining_attempts("192.168.1.1") == 4

    def test_separate_ips(self):
        """Test that different IPs are tracked separately."""
        throttle = LoginThrottle(max_attempts=2, window_seconds=60)
        
        for _ in range(2):
            throttle.record_failure("192.168.1.1")
        
        assert throttle.is_blocked("192.168.1.1") is True
        assert throttle.is_blocked("192.168.1.2") is False


# Fixtures for auth-enabled API tests
@pytest.fixture
def auth_api_settings() -> APISettings:
    """Provide test API settings with auth enabled."""
    return APISettings(
        host="127.0.0.1",
        port=8000,
        debug=True,
        allowed_origins=["*"],
        log_requests=False,
        auth_enabled=True,
        jwt_secret=TEST_JWT_SECRET,
        jwt_algorithm="HS256",
        jwt_expires_minutes=30,
        refresh_token_expires_minutes=10080,
    )


@pytest.fixture
def auth_disabled_settings() -> APISettings:
    """Provide test API settings with auth disabled."""
    return APISettings(
        host="127.0.0.1",
        port=8000,
        debug=True,
        allowed_origins=["*"],
        log_requests=False,
        auth_enabled=False,
        jwt_secret=TEST_JWT_SECRET,  # Still needed for login endpoint to work
    )


@pytest.fixture
def fresh_throttle() -> LoginThrottle:
    """Provide a fresh throttle instance for each test."""
    return LoginThrottle(max_attempts=5, window_seconds=60)


@pytest_asyncio.fixture
async def auth_test_repository(tmp_path) -> AsyncGenerator[VideoRepository, None]:
    """Provide a test database repository with admin user seeded."""
    db_config = DatabaseConfig(
        database_path=str(tmp_path / "test_auth.db"),
        enable_wal_mode=False,
        connection_timeout=30,
        backup_dir=str(tmp_path / "backups"),
    )
    repo = await VideoRepository.from_config(db_config)
    
    # Verify admin user was created by migration
    cursor = await repo._connection.execute(
        "SELECT id, username FROM users WHERE username = 'admin'"
    )
    row = await cursor.fetchone()
    assert row is not None, "Admin user should be created by migration"
    
    yield repo
    await repo.close()


@pytest_asyncio.fixture
async def auth_test_app(
    auth_test_repository: VideoRepository,
    auth_api_settings: APISettings,
    fresh_throttle: LoginThrottle,
) -> AsyncGenerator[TestClient, None]:
    """Provide a FastAPI TestClient with auth enabled."""
    from fuzzbin.auth import get_login_throttle
    
    test_config = Config(
        database=DatabaseConfig(
            database_path=":memory:",  # Not used, but required
        ),
        logging=LoggingConfig(
            level="WARNING",
            format="text",
            handlers=["console"],
        ),
    )
    
    fuzzbin._config = test_config
    fuzzbin._repository = auth_test_repository

    # Clear cached settings and override
    get_settings.cache_clear()
    
    app = create_app()

    async def override_get_repository() -> AsyncGenerator[VideoRepository, None]:
        yield auth_test_repository

    def override_get_settings() -> APISettings:
        return auth_api_settings

    def override_get_throttle() -> LoginThrottle:
        return fresh_throttle

    app.dependency_overrides[get_repository] = override_get_repository
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_api_settings] = override_get_settings
    app.dependency_overrides[get_login_throttle] = override_get_throttle

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def auth_disabled_test_app(
    auth_test_repository: VideoRepository,
    auth_disabled_settings: APISettings,
    fresh_throttle: LoginThrottle,
) -> AsyncGenerator[TestClient, None]:
    """Provide a FastAPI TestClient with auth disabled."""
    from fuzzbin.auth import get_login_throttle
    
    test_config = Config(
        database=DatabaseConfig(
            database_path=":memory:",
        ),
        logging=LoggingConfig(
            level="WARNING",
            format="text",
            handlers=["console"],
        ),
    )
    
    fuzzbin._config = test_config
    fuzzbin._repository = auth_test_repository

    get_settings.cache_clear()
    
    app = create_app()

    async def override_get_repository() -> AsyncGenerator[VideoRepository, None]:
        yield auth_test_repository

    def override_get_settings() -> APISettings:
        return auth_disabled_settings

    def override_get_throttle() -> LoginThrottle:
        return fresh_throttle

    app.dependency_overrides[get_repository] = override_get_repository
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_api_settings] = override_get_settings
    app.dependency_overrides[get_login_throttle] = override_get_throttle

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def get_auth_header(access_token: str) -> dict:
    """Helper to create Authorization header."""
    return {"Authorization": f"Bearer {access_token}"}


class TestLoginEndpoint:
    """Tests for POST /auth/login endpoint."""

    def test_login_success(self, auth_test_app: TestClient):
        """Test successful login with valid credentials."""
        response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert data["expires_in"] == 30 * 60  # 30 minutes in seconds

    def test_login_wrong_password(self, auth_test_app: TestClient):
        """Test login failure with wrong password."""
        response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": "wrongpassword"},
        )
        
        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    def test_login_wrong_username(self, auth_test_app: TestClient):
        """Test login failure with non-existent username."""
        response = auth_test_app.post(
            "/auth/login",
            json={"username": "nonexistent", "password": TEST_PASSWORD},
        )
        
        assert response.status_code == 401
        assert "Invalid username or password" in response.json()["detail"]

    def test_login_empty_credentials(self, auth_test_app: TestClient):
        """Test login failure with empty credentials."""
        response = auth_test_app.post(
            "/auth/login",
            json={"username": "", "password": ""},
        )
        
        assert response.status_code == 422  # Validation error

    def test_login_throttling(self, auth_test_app: TestClient):
        """Test that login is throttled after multiple failures."""
        # Make 5 failed login attempts
        for _ in range(5):
            auth_test_app.post(
                "/auth/login",
                json={"username": TEST_USERNAME, "password": "wrongpassword"},
            )
        
        # 6th attempt should be throttled
        response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": "wrongpassword"},
        )
        
        assert response.status_code == 429
        assert "Too many failed login attempts" in response.json()["detail"]
        assert "Retry-After" in response.headers


class TestRefreshEndpoint:
    """Tests for POST /auth/refresh endpoint."""

    def test_refresh_token_success(self, auth_test_app: TestClient):
        """Test successful token refresh."""
        # First, login to get tokens
        login_response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]
        
        # Now refresh
        response = auth_test_app.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_with_invalid_token(self, auth_test_app: TestClient):
        """Test refresh failure with invalid token."""
        response = auth_test_app.post(
            "/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        
        assert response.status_code == 401
        assert "Invalid or expired refresh token" in response.json()["detail"]

    def test_refresh_with_access_token(self, auth_test_app: TestClient):
        """Test refresh failure when using access token instead of refresh token."""
        # Login to get access token
        login_response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        access_token = login_response.json()["access_token"]
        
        # Try to use access token as refresh token
        response = auth_test_app.post(
            "/auth/refresh",
            json={"refresh_token": access_token},
        )
        
        assert response.status_code == 401


class TestPasswordChangeEndpoint:
    """Tests for POST /auth/password endpoint."""

    def test_change_password_success(self, auth_test_app: TestClient):
        """Test successful password change."""
        # Login to get access token
        login_response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        access_token = login_response.json()["access_token"]
        
        # Change password
        response = auth_test_app.post(
            "/auth/password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": TEST_NEW_PASSWORD,
            },
            headers=get_auth_header(access_token),
        )
        
        assert response.status_code == 204
        
        # Verify new password works
        login_response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_NEW_PASSWORD},
        )
        assert login_response.status_code == 200

    def test_change_password_wrong_current(self, auth_test_app: TestClient):
        """Test password change failure with wrong current password."""
        # Login first
        login_response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        access_token = login_response.json()["access_token"]
        
        # Try to change with wrong current password
        response = auth_test_app.post(
            "/auth/password",
            json={
                "current_password": "wrongcurrent",
                "new_password": TEST_NEW_PASSWORD,
            },
            headers=get_auth_header(access_token),
        )
        
        assert response.status_code == 400
        assert "Current password is incorrect" in response.json()["detail"]

    def test_change_password_without_auth(self, auth_test_app: TestClient):
        """Test password change failure without authentication."""
        response = auth_test_app.post(
            "/auth/password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": TEST_NEW_PASSWORD,
            },
        )
        
        assert response.status_code == 401

    def test_change_password_short_new_password(self, auth_test_app: TestClient):
        """Test password change failure with too short new password."""
        # Login first
        login_response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        access_token = login_response.json()["access_token"]
        
        # Try short password
        response = auth_test_app.post(
            "/auth/password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "short",
            },
            headers=get_auth_header(access_token),
        )
        
        assert response.status_code == 422  # Validation error


class TestProtectedRoutes:
    """Tests for route protection when auth is enabled."""

    def test_protected_route_without_token(self, auth_test_app: TestClient):
        """Test that protected routes return 401 without token."""
        response = auth_test_app.get("/videos")
        assert response.status_code == 401

    def test_protected_route_with_valid_token(self, auth_test_app: TestClient):
        """Test that protected routes work with valid token."""
        # Login first
        login_response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        access_token = login_response.json()["access_token"]
        
        # Access protected route
        response = auth_test_app.get(
            "/videos",
            headers=get_auth_header(access_token),
        )
        
        assert response.status_code == 200

    def test_protected_route_with_invalid_token(self, auth_test_app: TestClient):
        """Test that protected routes return 401 with invalid token."""
        response = auth_test_app.get(
            "/videos",
            headers=get_auth_header("invalid.token.here"),
        )
        
        assert response.status_code == 401

    def test_protected_route_with_expired_token(self, auth_test_app: TestClient, auth_api_settings: APISettings):
        """Test that protected routes return 401 with expired token."""
        # Create an expired token directly
        expired_token = create_access_token(
            data={"sub": TEST_USERNAME, "user_id": 1},
            secret_key=auth_api_settings.jwt_secret,
            expires_minutes=-1,  # Expired
        )
        
        response = auth_test_app.get(
            "/videos",
            headers=get_auth_header(expired_token),
        )
        
        assert response.status_code == 401

    def test_health_endpoint_public(self, auth_test_app: TestClient):
        """Test that health endpoint is accessible without authentication."""
        response = auth_test_app.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["auth_enabled"] is True


class TestAuthDisabled:
    """Tests for API behavior when auth is disabled."""

    def test_routes_accessible_without_auth(self, auth_disabled_test_app: TestClient):
        """Test that routes are accessible without authentication when auth disabled."""
        response = auth_disabled_test_app.get("/videos")
        assert response.status_code == 200

    def test_login_still_works(self, auth_disabled_test_app: TestClient):
        """Test that login endpoint still works when auth disabled."""
        response = auth_disabled_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        # Should work - login doesn't require auth_enabled
        assert response.status_code == 200

    def test_health_shows_auth_disabled(self, auth_disabled_test_app: TestClient):
        """Test that health endpoint shows auth_enabled=false."""
        response = auth_disabled_test_app.get("/health")
        assert response.status_code == 200
        assert response.json()["auth_enabled"] is False


class TestLogoutEndpoint:
    """Tests for POST /auth/logout endpoint."""

    def test_logout_returns_204(self, auth_test_app: TestClient):
        """Test that logout returns 204 (no-op for stateless JWT)."""
        response = auth_test_app.post("/auth/logout")
        assert response.status_code == 204
