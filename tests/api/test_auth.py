"""Tests for authentication routes and security."""

from pathlib import Path
from typing import AsyncGenerator

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


@pytest.fixture(autouse=True)
def set_jwt_secret_env(monkeypatch):
    """Set JWT secret environment variable for all tests in this module.

    This is required because APISettings now always requires jwt_secret,
    and create_app() calls get_settings() before dependency overrides are set.
    """
    monkeypatch.setenv("FUZZBIN_API_JWT_SECRET", TEST_JWT_SECRET)
    # Also set auth_enabled since it's the new default
    monkeypatch.setenv("FUZZBIN_API_AUTH_ENABLED", "true")
    # Allow insecure mode for tests that disable auth
    monkeypatch.setenv("FUZZBIN_API_ALLOW_INSECURE_MODE", "true")
    # Clear the settings cache to pick up the new env vars
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
        allow_insecure_mode=True,  # Required when auth_enabled=False
        jwt_secret=TEST_JWT_SECRET,  # Still needed for login endpoint to work
    )


@pytest.fixture
def fresh_throttle() -> LoginThrottle:
    """Provide a fresh throttle instance for each test."""
    return LoginThrottle(max_attempts=5, window_seconds=60)


@pytest_asyncio.fixture
async def auth_test_repository(tmp_path) -> AsyncGenerator[VideoRepository, None]:
    """Provide a test database repository with admin user seeded.

    Uses direct VideoRepository instantiation with temp database path.
    """
    from fuzzbin.core.db.migrator import Migrator

    db_path = tmp_path / "test_auth.db"
    migrations_dir = Path(__file__).parent.parent.parent / "fuzzbin" / "core" / "db" / "migrations"

    repo = VideoRepository(
        db_path=db_path,
        enable_wal=False,  # Disable WAL mode in tests to avoid lock issues
        timeout=30,
    )
    await repo.connect()

    # Run migrations
    migrator = Migrator(db_path, migrations_dir, enable_wal=False)
    await migrator.run_migrations(connection=repo._connection)

    # Verify admin user was created by migration
    cursor = await repo._connection.execute(
        "SELECT id, username FROM users WHERE username = 'admin'"
    )
    row = await cursor.fetchone()
    assert row is not None, "Admin user should be created by migration"

    # Clear password_must_change flag for most tests (separate tests cover rotation flow)
    await repo._connection.execute(
        "UPDATE users SET password_must_change = 0 WHERE username = 'admin'"
    )
    await repo._connection.commit()

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
        database=DatabaseConfig(),
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
        # refresh_token is now in httpOnly cookie, not in response body
        assert "refresh_token" not in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert data["expires_in"] == 30 * 60  # 30 minutes in seconds
        # Verify refresh token cookie is set
        assert "refresh_token" in response.cookies

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
        # First, login to get tokens (refresh token is set as cookie)
        login_response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert login_response.status_code == 200

        # Now refresh - the cookie is automatically sent by TestClient
        response = auth_test_app.post("/auth/refresh")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        # refresh_token is rotated via cookie, not in response body
        assert "refresh_token" not in data
        # Verify new refresh token cookie is set
        assert "refresh_token" in response.cookies

    def test_refresh_with_invalid_token(self, auth_test_app: TestClient):
        """Test refresh failure with invalid/missing cookie."""
        # Don't login first, so no cookie exists
        response = auth_test_app.post("/auth/refresh")

        assert response.status_code == 401
        assert "No refresh token provided" in response.json()["detail"]

    def test_refresh_with_access_token_as_cookie(self, auth_test_app: TestClient):
        """Test refresh failure when using access token instead of refresh token in cookie."""
        # Login to get access token
        login_response = auth_test_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        access_token = login_response.json()["access_token"]

        # Manually set the access token as the refresh_token cookie
        auth_test_app.cookies.clear()
        auth_test_app.cookies.set("refresh_token", access_token, path="/auth")

        # Try to refresh with access token in cookie (should fail - wrong token type)
        response = auth_test_app.post("/auth/refresh")

        assert response.status_code == 401


@pytest_asyncio.fixture
async def password_rotation_repository(tmp_path) -> AsyncGenerator[VideoRepository, None]:
    """Repository with password_must_change=true for testing password rotation.

    Uses direct VideoRepository instantiation with temp database path.
    """
    from fuzzbin.core.db.migrator import Migrator

    db_path = tmp_path / "test_rotation.db"
    migrations_dir = Path(__file__).parent.parent.parent / "fuzzbin" / "core" / "db" / "migrations"

    repo = VideoRepository(
        db_path=db_path,
        enable_wal=False,  # Disable WAL mode in tests to avoid lock issues
        timeout=30,
    )
    await repo.connect()

    # Run migrations
    migrator = Migrator(db_path, migrations_dir, enable_wal=False)
    await migrator.run_migrations(connection=repo._connection)

    # Keep password_must_change=true (set by migration 008)
    cursor = await repo._connection.execute(
        "SELECT password_must_change FROM users WHERE username = 'admin'"
    )
    row = await cursor.fetchone()
    assert row[0] == 1, "password_must_change should be true from migration"

    yield repo
    await repo.close()


@pytest_asyncio.fixture
async def password_rotation_app(
    password_rotation_repository: VideoRepository,
    auth_api_settings: APISettings,
    fresh_throttle: LoginThrottle,
) -> AsyncGenerator[TestClient, None]:
    """Provide a FastAPI TestClient with password rotation required."""
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
    fuzzbin._repository = password_rotation_repository

    get_settings.cache_clear()
    app = create_app()

    async def override_get_repository() -> AsyncGenerator[VideoRepository, None]:
        yield password_rotation_repository

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


class TestPasswordRotation:
    """Tests for password rotation (set-initial-password) endpoint."""

    def test_login_blocked_when_password_must_change(self, password_rotation_app: TestClient):
        """Test that login is blocked when password_must_change is true."""
        response = password_rotation_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )

        assert response.status_code == 403
        data = response.json()
        assert "Password change required" in data["detail"]
        assert "/auth/set-initial-password" in data["detail"]
        # The password change requirement is also indicated via header
        assert response.headers.get("X-Password-Change-Required") == "true"

    def test_set_initial_password_success(self, password_rotation_app: TestClient):
        """Test successful initial password change."""
        response = password_rotation_app.post(
            "/auth/set-initial-password",
            json={
                "username": TEST_USERNAME,
                "current_password": TEST_PASSWORD,
                "new_password": TEST_NEW_PASSWORD,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        # refresh_token is now in httpOnly cookie, not in response body
        assert "refresh_token" not in data
        assert data["token_type"] == "bearer"
        # Verify refresh token cookie is set
        assert "refresh_token" in response.cookies

    def test_set_initial_password_then_login_works(self, password_rotation_app: TestClient):
        """Test that login works after setting initial password."""
        # Set initial password
        password_rotation_app.post(
            "/auth/set-initial-password",
            json={
                "username": TEST_USERNAME,
                "current_password": TEST_PASSWORD,
                "new_password": TEST_NEW_PASSWORD,
            },
        )

        # Now login should work
        response = password_rotation_app.post(
            "/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_NEW_PASSWORD},
        )

        assert response.status_code == 200

    def test_set_initial_password_wrong_current(self, password_rotation_app: TestClient):
        """Test set-initial-password failure with wrong current password."""
        response = password_rotation_app.post(
            "/auth/set-initial-password",
            json={
                "username": TEST_USERNAME,
                "current_password": "wrongpassword",
                "new_password": TEST_NEW_PASSWORD,
            },
        )

        assert response.status_code == 401

    def test_set_initial_password_wrong_username(self, password_rotation_app: TestClient):
        """Test set-initial-password failure with non-existent username."""
        response = password_rotation_app.post(
            "/auth/set-initial-password",
            json={
                "username": "nonexistent",
                "current_password": TEST_PASSWORD,
                "new_password": TEST_NEW_PASSWORD,
            },
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

    def test_protected_route_with_expired_token(
        self, auth_test_app: TestClient, auth_api_settings: APISettings
    ):
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
