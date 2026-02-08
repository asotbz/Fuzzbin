"""Unit tests for the OIDC auth module (fuzzbin/auth/oidc.py)."""

import hashlib
import time
from base64 import urlsafe_b64encode
from urllib.parse import parse_qs, urlparse

import pytest

from fuzzbin.auth.oidc import (
    OIDCConfigError,
    OIDCProvider,
    OIDCTransactionStore,
    OIDCValidationError,
    _make_code_challenge,
    get_oidc_provider,
    reset_oidc_singletons,
)


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------


class TestPKCE:
    """Tests for PKCE code_challenge derivation."""

    def test_code_challenge_is_s256(self):
        """code_challenge = BASE64URL(SHA256(code_verifier))."""
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        expected_digest = hashlib.sha256(verifier.encode("ascii")).digest()
        expected = urlsafe_b64encode(expected_digest).rstrip(b"=").decode("ascii")
        assert _make_code_challenge(verifier) == expected

    def test_code_challenge_no_padding(self):
        """code_challenge must have no base64 padding ('=')."""
        result = _make_code_challenge("any-verifier-value")
        assert "=" not in result


# ---------------------------------------------------------------------------
# Transaction store
# ---------------------------------------------------------------------------


class TestOIDCTransactionStore:
    """Tests for the in-memory OIDC transaction store."""

    def test_create_returns_three_values(self):
        store = OIDCTransactionStore()
        state, nonce, verifier = store.create()
        assert isinstance(state, str) and len(state) > 16
        assert isinstance(nonce, str) and len(nonce) > 16
        assert isinstance(verifier, str) and len(verifier) > 16

    def test_consume_valid_state(self):
        store = OIDCTransactionStore()
        state, nonce, verifier = store.create()
        result = store.consume(state)
        assert result is not None
        consumed_nonce, consumed_verifier = result
        assert consumed_nonce == nonce
        assert consumed_verifier == verifier

    def test_consume_removes_state(self):
        """Consuming a state makes it unavailable for reuse (replay protection)."""
        store = OIDCTransactionStore()
        state, _, _ = store.create()
        assert store.consume(state) is not None
        assert store.consume(state) is None

    def test_consume_unknown_state_returns_none(self):
        store = OIDCTransactionStore()
        assert store.consume("nonexistent") is None

    def test_consume_expired_state_returns_none(self):
        store = OIDCTransactionStore(ttl=0)  # 0-second TTL → immediately expired
        state, _, _ = store.create()
        # Force expiry by sleeping a tiny amount (monotonic clock)
        time.sleep(0.01)
        assert store.consume(state) is None

    def test_cleanup_removes_expired(self):
        store = OIDCTransactionStore(ttl=0)
        store.create()
        store.create()
        assert len(store._store) > 0
        time.sleep(0.01)
        store._cleanup()
        assert len(store._store) == 0


# ---------------------------------------------------------------------------
# OIDCProvider — group claim check
# ---------------------------------------------------------------------------


class TestGroupClaimCheck:
    """Tests for OIDCProvider.check_group_claim()."""

    def test_no_required_group_passes(self):
        """When required_group is None, any claims pass."""
        OIDCProvider.check_group_claim({"sub": "user1"}, required_group=None)

    def test_group_present_and_matching(self):
        claims = {"sub": "user1", "groups": ["admins", "users"]}
        OIDCProvider.check_group_claim(claims, required_group="admins")

    def test_group_present_but_not_matching(self):
        claims = {"sub": "user1", "groups": ["users"]}
        with pytest.raises(OIDCValidationError, match="not a member"):
            OIDCProvider.check_group_claim(claims, required_group="admins")

    def test_group_claim_missing(self):
        claims = {"sub": "user1"}
        with pytest.raises(OIDCValidationError, match="missing.*groups"):
            OIDCProvider.check_group_claim(claims, required_group="admins")

    def test_group_claim_is_string(self):
        """When the claim is a plain string (not list), it should still work."""
        claims = {"sub": "user1", "roles": "admin"}
        OIDCProvider.check_group_claim(claims, required_group="admin", groups_claim="roles")

    def test_group_claim_not_a_list(self):
        claims = {"sub": "user1", "groups": 42}
        with pytest.raises(OIDCValidationError, match="not a list"):
            OIDCProvider.check_group_claim(claims, required_group="admins")

    def test_custom_groups_claim_name(self):
        claims = {"sub": "user1", "roles": ["editor", "viewer"]}
        OIDCProvider.check_group_claim(claims, required_group="editor", groups_claim="roles")


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


class TestGetOIDCProvider:
    """Tests for the get_oidc_provider factory."""

    def setup_method(self):
        reset_oidc_singletons()

    def teardown_method(self):
        reset_oidc_singletons()

    def test_raises_when_oidc_disabled(self):
        class FakeConfig:
            enabled = False

        with pytest.raises(OIDCConfigError, match="not enabled"):
            get_oidc_provider(FakeConfig())

    def test_creates_provider_when_enabled(self):
        class FakeConfig:
            enabled = True
            issuer_url = "https://auth.example.com"
            client_id = "fuzzbin"
            redirect_uri = "http://localhost/callback"
            scopes = "openid"
            client_secret = None

        provider = get_oidc_provider(FakeConfig())
        assert isinstance(provider, OIDCProvider)
        assert provider.issuer_url == "https://auth.example.com"

    def test_raises_when_required_settings_missing(self):
        class FakeConfig:
            enabled = True
            issuer_url = None
            client_id = "fuzzbin"
            redirect_uri = None
            scopes = "openid"
            client_secret = None
            target_username = "admin"

        with pytest.raises(OIDCConfigError, match="Missing required OIDC settings"):
            get_oidc_provider(FakeConfig())

    def test_returns_same_instance(self):
        class FakeConfig:
            enabled = True
            issuer_url = "https://auth.example.com"
            client_id = "fuzzbin"
            redirect_uri = "http://localhost/callback"
            scopes = "openid"
            client_secret = None

        provider1 = get_oidc_provider(FakeConfig())
        provider2 = get_oidc_provider(FakeConfig())
        assert provider1 is provider2


# ---------------------------------------------------------------------------
# OIDCProvider — discovery and auth URL (with mocked HTTP)
# ---------------------------------------------------------------------------


class TestOIDCProviderDiscovery:
    """Tests for OIDCProvider discovery and auth URL construction."""

    @pytest.fixture
    def provider(self):
        return OIDCProvider(
            issuer_url="https://auth.example.com",
            client_id="fuzzbin",
            redirect_uri="http://localhost:5173/oidc/callback",
            scopes="openid email profile",
        )

    @pytest.fixture
    def discovery_doc(self):
        return {
            "issuer": "https://auth.example.com",
            "authorization_endpoint": "https://auth.example.com/authorize",
            "token_endpoint": "https://auth.example.com/token",
            "jwks_uri": "https://auth.example.com/.well-known/jwks.json",
            "response_types_supported": ["code"],
        }

    async def test_fetch_discovery_success(self, provider, discovery_doc, respx_mock):
        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )

        result = await provider._fetch_discovery()
        assert result["issuer"] == "https://auth.example.com"

    async def test_fetch_discovery_caches(self, provider, discovery_doc, respx_mock):
        route = respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )

        await provider._fetch_discovery()
        await provider._fetch_discovery()
        assert route.call_count == 1

    async def test_fetch_discovery_missing_keys(self, provider, respx_mock):
        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json={"issuer": "https://auth.example.com"}
        )

        with pytest.raises(OIDCConfigError, match="missing required key"):
            await provider._fetch_discovery()

    async def test_fetch_discovery_issuer_mismatch(self, provider, discovery_doc, respx_mock):
        discovery_doc["issuer"] = "https://wrong.example.com"
        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )

        with pytest.raises(OIDCConfigError, match="issuer mismatch"):
            await provider._fetch_discovery()

    async def test_fetch_discovery_http_error(self, provider, respx_mock):
        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            status_code=500
        )

        with pytest.raises(OIDCConfigError, match="Failed to fetch OIDC discovery"):
            await provider._fetch_discovery()

    async def test_build_auth_url(self, provider, discovery_doc, respx_mock):
        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )

        url = await provider.build_auth_url(
            state="test-state",
            nonce="test-nonce",
            code_verifier="test-verifier",
        )
        assert url.startswith("https://auth.example.com/authorize?")
        assert "response_type=code" in url
        assert "client_id=fuzzbin" in url
        assert "state=test-state" in url
        assert "nonce=test-nonce" in url
        assert "code_challenge_method=S256" in url

    async def test_build_auth_url_encodes_scope_and_redirect_uri(
        self, provider, discovery_doc, respx_mock
    ):
        provider.scopes = "openid email profile custom:read"
        provider.redirect_uri = (
            "https://fuzzbin.example.com/oidc/callback?next=/library&label=hello world"
        )
        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )

        url = await provider.build_auth_url(
            state="test-state",
            nonce="test-nonce",
            code_verifier="test-verifier",
        )

        # No raw spaces should leak into the URL.
        assert " " not in url

        parsed = urlparse(url)
        qs = parse_qs(parsed.query, strict_parsing=True)
        assert qs["scope"] == [provider.scopes]
        assert qs["redirect_uri"] == [provider.redirect_uri]

    async def test_build_auth_url_preserves_existing_endpoint_query(
        self, provider, discovery_doc, respx_mock
    ):
        discovery_doc["authorization_endpoint"] = (
            "https://auth.example.com/authorize?kc_idp_hint=google"
        )
        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )

        url = await provider.build_auth_url(
            state="test-state",
            nonce="test-nonce",
            code_verifier="test-verifier",
        )

        parsed = urlparse(url)
        qs = parse_qs(parsed.query, strict_parsing=True)
        assert qs["kc_idp_hint"] == ["google"]
        assert qs["client_id"] == ["fuzzbin"]
        assert qs["response_type"] == ["code"]

    async def test_build_logout_url_with_post_logout_redirect(
        self, provider, discovery_doc, respx_mock
    ):
        discovery_doc["end_session_endpoint"] = "https://auth.example.com/logout?foo=bar"
        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )

        post_logout_redirect_uri = "https://fuzzbin.example.com/login?local=1"
        url = await provider.build_logout_url(post_logout_redirect_uri=post_logout_redirect_uri)
        assert url is not None

        parsed = urlparse(url)
        qs = parse_qs(parsed.query, strict_parsing=True)
        assert qs["foo"] == ["bar"]
        assert qs["post_logout_redirect_uri"] == [post_logout_redirect_uri]
        assert qs["client_id"] == ["fuzzbin"]

    async def test_build_logout_url_returns_none_without_end_session_endpoint(
        self, provider, discovery_doc, respx_mock
    ):
        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )

        assert await provider.build_logout_url() is None

    async def test_clear_cache(self, provider, discovery_doc, respx_mock):
        route = respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )

        await provider._fetch_discovery()
        provider.clear_cache()
        await provider._fetch_discovery()
        assert route.call_count == 2


# ---------------------------------------------------------------------------
# OIDCProvider — code exchange (mocked HTTP)
# ---------------------------------------------------------------------------


class TestOIDCProviderCodeExchange:
    """Tests for code exchange with mocked HTTP."""

    @pytest.fixture
    def provider(self):
        return OIDCProvider(
            issuer_url="https://auth.example.com",
            client_id="fuzzbin",
            redirect_uri="http://localhost:5173/oidc/callback",
            scopes="openid email profile",
            client_secret="secret123",
        )

    @pytest.fixture
    def discovery_doc(self):
        return {
            "issuer": "https://auth.example.com",
            "authorization_endpoint": "https://auth.example.com/authorize",
            "token_endpoint": "https://auth.example.com/token",
            "jwks_uri": "https://auth.example.com/.well-known/jwks.json",
        }

    async def test_exchange_code_success(self, provider, discovery_doc, respx_mock):
        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )

        token_response = {
            "access_token": "at_xxx",
            "id_token": "eyJ...",
            "token_type": "Bearer",
        }
        respx_mock.post("https://auth.example.com/token").respond(json=token_response)

        result = await provider.exchange_code("auth-code", "verifier")
        assert result["access_token"] == "at_xxx"

    async def test_exchange_code_includes_client_secret(self, provider, discovery_doc, respx_mock):
        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )

        route = respx_mock.post("https://auth.example.com/token").respond(
            json={"access_token": "x", "id_token": "y"}
        )

        await provider.exchange_code("code", "verifier")
        request = route.calls[0].request
        body = request.content.decode()
        assert "client_secret=secret123" in body

    async def test_exchange_code_failure(self, provider, discovery_doc, respx_mock):
        from fuzzbin.auth.oidc import OIDCError

        respx_mock.get("https://auth.example.com/.well-known/openid-configuration").respond(
            json=discovery_doc
        )
        respx_mock.post("https://auth.example.com/token").respond(status_code=400)

        with pytest.raises(OIDCError, match="Token exchange failed"):
            await provider.exchange_code("bad-code", "verifier")
