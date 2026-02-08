"""API-level tests for OIDC authentication endpoints.

Tests the full request lifecycle through FastAPI test client:
  GET  /auth/oidc/config
  POST /auth/oidc/start
  POST /auth/oidc/exchange
"""

from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

import fuzzbin
from fuzzbin.auth import LoginThrottle, get_login_throttle
from fuzzbin.auth.oidc import (
    OIDCProvider,
    reset_oidc_singletons,
)
from fuzzbin.common.config import Config, DatabaseConfig, LoggingConfig, OIDCConfig
from fuzzbin.core.db import VideoRepository
from fuzzbin.core.db.migrator import Migrator
from fuzzbin.web.main import create_app
from fuzzbin.web.dependencies import get_repository, get_api_settings
from fuzzbin.web.settings import APISettings, get_settings


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"
TEST_ISSUER = "https://auth.example.com"
TEST_CLIENT_ID = "fuzzbin-test"
TEST_REDIRECT_URI = "http://localhost:5173/oidc/callback"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def set_jwt_secret_env(monkeypatch):
    monkeypatch.setenv("FUZZBIN_API_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("FUZZBIN_API_AUTH_ENABLED", "true")
    monkeypatch.setenv("FUZZBIN_API_ALLOW_INSECURE_MODE", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def reset_oidc():
    """Reset OIDC singletons between tests."""
    reset_oidc_singletons()
    yield
    reset_oidc_singletons()


@pytest.fixture
def oidc_settings() -> APISettings:
    """APISettings (no OIDC fields — those live in Config now)."""
    return APISettings(
        host="127.0.0.1",
        port=8000,
        debug=True,
        allowed_origins=["*"],
        log_requests=False,
        auth_enabled=True,
        jwt_secret=TEST_JWT_SECRET,
        jwt_expires_minutes=30,
        refresh_token_expires_minutes=1440,
    )


@pytest.fixture
def oidc_config() -> OIDCConfig:
    """OIDCConfig with OIDC enabled."""
    return OIDCConfig(
        enabled=True,
        issuer_url=TEST_ISSUER,
        client_id=TEST_CLIENT_ID,
        redirect_uri=TEST_REDIRECT_URI,
        scopes="openid email profile",
        target_username="admin",
        provider_name="TestIdP",
    )


@pytest.fixture
def oidc_disabled_config() -> OIDCConfig:
    """OIDCConfig with OIDC disabled."""
    return OIDCConfig(enabled=False)


@pytest.fixture
def oidc_config_with_group() -> OIDCConfig:
    """OIDCConfig with OIDC + group gating enabled."""
    return OIDCConfig(
        enabled=True,
        issuer_url=TEST_ISSUER,
        client_id=TEST_CLIENT_ID,
        redirect_uri=TEST_REDIRECT_URI,
        required_group="fuzzbin-users",
        groups_claim="groups",
        target_username="admin",
        provider_name="TestIdP",
    )


@pytest_asyncio.fixture
async def oidc_test_repository(tmp_path) -> AsyncGenerator[VideoRepository, None]:
    db_path = tmp_path / "test_oidc.db"
    migrations_dir = Path(__file__).parent.parent.parent / "fuzzbin" / "core" / "db" / "migrations"

    repo = VideoRepository(db_path=db_path, enable_wal=False, timeout=30)
    await repo.connect()

    migrator = Migrator(db_path, migrations_dir, enable_wal=False)
    await migrator.run_migrations(connection=repo._connection)

    # Clear password_must_change
    await repo._connection.execute(
        "UPDATE users SET password_must_change = 0 WHERE username = 'admin'"
    )
    await repo._connection.commit()

    yield repo
    await repo.close()


def _make_test_app(
    repo: VideoRepository,
    settings: APISettings,
    oidc_cfg: OIDCConfig = OIDCConfig(),
) -> TestClient:
    """Create a test app with the given settings and OIDC config."""
    test_config = Config(
        database=DatabaseConfig(),
        logging=LoggingConfig(level="WARNING", format="text", handlers=["console"]),
        oidc=oidc_cfg,
    )
    fuzzbin._config = test_config
    fuzzbin._repository = repo

    get_settings.cache_clear()
    app = create_app()

    async def override_repo():
        yield repo

    def override_settings():
        return settings

    def override_throttle():
        return LoginThrottle(max_attempts=5, window_seconds=60)

    app.dependency_overrides[get_repository] = override_repo
    app.dependency_overrides[get_settings] = override_settings
    app.dependency_overrides[get_api_settings] = override_settings
    app.dependency_overrides[get_login_throttle] = override_throttle

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /auth/oidc/config
# ---------------------------------------------------------------------------


class TestOIDCConfigEndpoint:
    """Tests for GET /auth/oidc/config."""

    def test_config_when_oidc_enabled(self, oidc_test_repository, oidc_settings, oidc_config):
        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_config)
        resp = client.get("/auth/oidc/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["provider_name"] == "TestIdP"

    def test_config_when_oidc_disabled(
        self, oidc_test_repository, oidc_settings, oidc_disabled_config
    ):
        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_disabled_config)
        resp = client.get("/auth/oidc/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False


# ---------------------------------------------------------------------------
# POST /auth/oidc/start
# ---------------------------------------------------------------------------


class TestOIDCStartEndpoint:
    """Tests for POST /auth/oidc/start."""

    def test_start_returns_404_when_disabled(
        self, oidc_test_repository, oidc_settings, oidc_disabled_config
    ):
        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_disabled_config)
        resp = client.post("/auth/oidc/start")
        assert resp.status_code == 404

    def test_start_returns_auth_url(
        self, oidc_test_repository, oidc_settings, oidc_config, respx_mock
    ):
        """Happy path: returns auth_url and state."""
        discovery = {
            "issuer": TEST_ISSUER,
            "authorization_endpoint": f"{TEST_ISSUER}/authorize",
            "token_endpoint": f"{TEST_ISSUER}/token",
            "jwks_uri": f"{TEST_ISSUER}/.well-known/jwks.json",
        }
        respx_mock.get(f"{TEST_ISSUER}/.well-known/openid-configuration").respond(json=discovery)

        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_config)
        resp = client.post("/auth/oidc/start")
        assert resp.status_code == 200
        data = resp.json()
        assert "auth_url" in data
        assert data["auth_url"].startswith(f"{TEST_ISSUER}/authorize?")
        assert "state" in data
        assert len(data["state"]) > 16


# ---------------------------------------------------------------------------
# POST /auth/oidc/exchange
# ---------------------------------------------------------------------------


class TestOIDCExchangeEndpoint:
    """Tests for POST /auth/oidc/exchange."""

    def test_exchange_returns_404_when_disabled(
        self, oidc_test_repository, oidc_settings, oidc_disabled_config
    ):
        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_disabled_config)
        resp = client.post("/auth/oidc/exchange", json={"code": "x", "state": "y"})
        assert resp.status_code == 404

    def test_exchange_invalid_state(self, oidc_test_repository, oidc_settings, oidc_config):
        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_config)
        resp = client.post("/auth/oidc/exchange", json={"code": "x", "state": "bogus"})
        assert resp.status_code == 400
        assert "Invalid or expired" in resp.json()["detail"]

    def test_exchange_happy_path(
        self, oidc_test_repository, oidc_settings, oidc_config, respx_mock
    ):
        """Full happy path: start → exchange → local JWT issued."""
        # Setup discovery
        discovery = {
            "issuer": TEST_ISSUER,
            "authorization_endpoint": f"{TEST_ISSUER}/authorize",
            "token_endpoint": f"{TEST_ISSUER}/token",
            "jwks_uri": f"{TEST_ISSUER}/.well-known/jwks.json",
        }
        respx_mock.get(f"{TEST_ISSUER}/.well-known/openid-configuration").respond(json=discovery)

        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_config)

        # Step 1: Start → get state
        start_resp = client.post("/auth/oidc/start")
        assert start_resp.status_code == 200
        state = start_resp.json()["state"]

        # Step 2: Mock exchange — we mock the provider methods directly
        fake_claims = {
            "iss": TEST_ISSUER,
            "sub": "oidc-user-123",
            "aud": TEST_CLIENT_ID,
            "nonce": "doesnt-matter",  # validated inside mock
            "email": "user@example.com",
        }

        with (
            patch.object(OIDCProvider, "exchange_code", new_callable=AsyncMock) as mock_exchange,
            patch.object(
                OIDCProvider, "validate_id_token", new_callable=AsyncMock
            ) as mock_validate,
        ):
            mock_exchange.return_value = {"id_token": "fake.jwt.token", "access_token": "at_xxx"}
            mock_validate.return_value = fake_claims

            resp = client.post(
                "/auth/oidc/exchange", json={"code": "auth-code-123", "state": state}
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

        # Refresh cookie should be set
        cookies = resp.cookies
        assert "refresh_token" in cookies

    def test_exchange_binds_identity(
        self, oidc_test_repository, oidc_settings, oidc_config, respx_mock
    ):
        """First exchange binds iss+sub; second exchange with same iss+sub succeeds."""
        discovery = {
            "issuer": TEST_ISSUER,
            "authorization_endpoint": f"{TEST_ISSUER}/authorize",
            "token_endpoint": f"{TEST_ISSUER}/token",
            "jwks_uri": f"{TEST_ISSUER}/.well-known/jwks.json",
        }
        respx_mock.get(f"{TEST_ISSUER}/.well-known/openid-configuration").respond(json=discovery)

        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_config)

        fake_claims = {
            "iss": TEST_ISSUER,
            "sub": "oidc-user-456",
            "aud": TEST_CLIENT_ID,
        }

        # First login — should bind
        start1 = client.post("/auth/oidc/start")
        state1 = start1.json()["state"]
        with (
            patch.object(OIDCProvider, "exchange_code", new_callable=AsyncMock) as m1,
            patch.object(OIDCProvider, "validate_id_token", new_callable=AsyncMock) as m2,
        ):
            m1.return_value = {"id_token": "x", "access_token": "y"}
            m2.return_value = fake_claims
            resp1 = client.post("/auth/oidc/exchange", json={"code": "c1", "state": state1})
        assert resp1.status_code == 200

        # Second login — same iss+sub should still succeed
        start2 = client.post("/auth/oidc/start")
        state2 = start2.json()["state"]
        with (
            patch.object(OIDCProvider, "exchange_code", new_callable=AsyncMock) as m1,
            patch.object(OIDCProvider, "validate_id_token", new_callable=AsyncMock) as m2,
        ):
            m1.return_value = {"id_token": "x", "access_token": "y"}
            m2.return_value = fake_claims
            resp2 = client.post("/auth/oidc/exchange", json={"code": "c2", "state": state2})
        assert resp2.status_code == 200

    def test_exchange_identity_mismatch(
        self, oidc_test_repository, oidc_settings, oidc_config, respx_mock
    ):
        """After binding, a different sub must be rejected."""
        discovery = {
            "issuer": TEST_ISSUER,
            "authorization_endpoint": f"{TEST_ISSUER}/authorize",
            "token_endpoint": f"{TEST_ISSUER}/token",
            "jwks_uri": f"{TEST_ISSUER}/.well-known/jwks.json",
        }
        respx_mock.get(f"{TEST_ISSUER}/.well-known/openid-configuration").respond(json=discovery)

        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_config)

        # Bind with sub=user-A
        start1 = client.post("/auth/oidc/start")
        state1 = start1.json()["state"]
        with (
            patch.object(OIDCProvider, "exchange_code", new_callable=AsyncMock) as m1,
            patch.object(OIDCProvider, "validate_id_token", new_callable=AsyncMock) as m2,
        ):
            m1.return_value = {"id_token": "x", "access_token": "y"}
            m2.return_value = {"iss": TEST_ISSUER, "sub": "user-A", "aud": TEST_CLIENT_ID}
            client.post("/auth/oidc/exchange", json={"code": "c1", "state": state1})

        # Try with sub=user-B → 403
        start2 = client.post("/auth/oidc/start")
        state2 = start2.json()["state"]
        with (
            patch.object(OIDCProvider, "exchange_code", new_callable=AsyncMock) as m1,
            patch.object(OIDCProvider, "validate_id_token", new_callable=AsyncMock) as m2,
        ):
            m1.return_value = {"id_token": "x", "access_token": "y"}
            m2.return_value = {"iss": TEST_ISSUER, "sub": "user-B", "aud": TEST_CLIENT_ID}
            resp = client.post("/auth/oidc/exchange", json={"code": "c2", "state": state2})
        assert resp.status_code == 403
        assert "does not match" in resp.json()["detail"]

    def test_exchange_required_group_missing(
        self, oidc_test_repository, oidc_settings, oidc_config_with_group, respx_mock
    ):
        """Exchange fails when required group is missing from claims."""
        discovery = {
            "issuer": TEST_ISSUER,
            "authorization_endpoint": f"{TEST_ISSUER}/authorize",
            "token_endpoint": f"{TEST_ISSUER}/token",
            "jwks_uri": f"{TEST_ISSUER}/.well-known/jwks.json",
        }
        respx_mock.get(f"{TEST_ISSUER}/.well-known/openid-configuration").respond(json=discovery)

        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_config_with_group)

        start = client.post("/auth/oidc/start")
        state = start.json()["state"]

        # Claims with no groups
        with (
            patch.object(OIDCProvider, "exchange_code", new_callable=AsyncMock) as m1,
            patch.object(OIDCProvider, "validate_id_token", new_callable=AsyncMock) as m2,
        ):
            m1.return_value = {"id_token": "x", "access_token": "y"}
            m2.return_value = {"iss": TEST_ISSUER, "sub": "user-X", "aud": TEST_CLIENT_ID}
            resp = client.post("/auth/oidc/exchange", json={"code": "c1", "state": state})
        assert resp.status_code == 403
        assert "groups" in resp.json()["detail"]

    def test_exchange_required_group_present(
        self, oidc_test_repository, oidc_settings, oidc_config_with_group, respx_mock
    ):
        """Exchange succeeds when the required group IS present."""
        discovery = {
            "issuer": TEST_ISSUER,
            "authorization_endpoint": f"{TEST_ISSUER}/authorize",
            "token_endpoint": f"{TEST_ISSUER}/token",
            "jwks_uri": f"{TEST_ISSUER}/.well-known/jwks.json",
        }
        respx_mock.get(f"{TEST_ISSUER}/.well-known/openid-configuration").respond(json=discovery)

        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_config_with_group)

        start = client.post("/auth/oidc/start")
        state = start.json()["state"]

        with (
            patch.object(OIDCProvider, "exchange_code", new_callable=AsyncMock) as m1,
            patch.object(OIDCProvider, "validate_id_token", new_callable=AsyncMock) as m2,
        ):
            m1.return_value = {"id_token": "x", "access_token": "y"}
            m2.return_value = {
                "iss": TEST_ISSUER,
                "sub": "user-G",
                "aud": TEST_CLIENT_ID,
                "groups": ["fuzzbin-users", "another-group"],
            }
            resp = client.post("/auth/oidc/exchange", json={"code": "c1", "state": state})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Existing local login still works when OIDC is enabled
# ---------------------------------------------------------------------------


class TestLocalLoginWithOIDCEnabled:
    """Verify password-based login is unaffected by OIDC being enabled."""

    def test_password_login_still_works(self, oidc_test_repository, oidc_settings, oidc_config):
        client = _make_test_app(oidc_test_repository, oidc_settings, oidc_config)
        resp = client.post(
            "/auth/login",
            json={"username": "admin", "password": "changeme"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
