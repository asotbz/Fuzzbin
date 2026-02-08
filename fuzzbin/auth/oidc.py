"""OpenID Connect (OIDC) provider integration.

Implements Authorization Code + PKCE flow for single-user identity binding.
Handles discovery, JWKS caching, code exchange, and ID token validation.
"""

import hashlib
import secrets
import time
from base64 import urlsafe_b64encode
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit, quote

import httpx
import structlog
from authlib.jose import JsonWebKey, jwt as authlib_jwt
from authlib.jose.errors import (
    BadSignatureError,
    DecodeError,
    ExpiredTokenError,
    InvalidClaimError,
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class OIDCError(Exception):
    """Base OIDC error."""


class OIDCConfigError(OIDCError):
    """OIDC configuration or discovery error."""


class OIDCValidationError(OIDCError):
    """ID token or claim validation failed."""


# ---------------------------------------------------------------------------
# Transaction store (state ↔ nonce / code_verifier)
# ---------------------------------------------------------------------------

_TRANSACTION_TTL_SECONDS = 300  # 5 minutes


@dataclass
class _OIDCTransaction:
    nonce: str
    code_verifier: str
    created_at: float


class OIDCTransactionStore:
    """In-memory store for OIDC authorization transactions.

    Maps ``state`` → ``(nonce, code_verifier, created_at)`` with a short TTL.
    Transactions are consumed on first use to prevent replay.
    """

    def __init__(self, ttl: int = _TRANSACTION_TTL_SECONDS) -> None:
        self._store: Dict[str, _OIDCTransaction] = {}
        self._ttl = ttl

    def create(self) -> tuple[str, str, str]:
        """Create a new transaction.

        Returns:
            ``(state, nonce, code_verifier)`` tuple.
        """
        self._cleanup()
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        self._store[state] = _OIDCTransaction(
            nonce=nonce,
            code_verifier=code_verifier,
            created_at=time.monotonic(),
        )
        return state, nonce, code_verifier

    def consume(self, state: str) -> Optional[tuple[str, str]]:
        """Consume a transaction by its *state*.

        Returns:
            ``(nonce, code_verifier)`` if valid and not expired, else ``None``.
        """
        self._cleanup()
        txn = self._store.pop(state, None)
        if txn is None:
            return None
        if time.monotonic() - txn.created_at > self._ttl:
            return None
        return txn.nonce, txn.code_verifier

    def _cleanup(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now - v.created_at > self._ttl]
        for k in expired:
            del self._store[k]


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------


def _make_code_challenge(code_verifier: str) -> str:
    """Derive S256 ``code_challenge`` from *code_verifier*."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# OIDC Provider
# ---------------------------------------------------------------------------


@dataclass
class OIDCProvider:
    """Manages OIDC discovery, auth URL construction, code exchange and ID-token validation."""

    issuer_url: str
    client_id: str
    redirect_uri: str
    scopes: str = "openid email profile"
    client_secret: Optional[str] = None

    # Cached discovery & JWKS (populated lazily)
    _discovery: Optional[Dict[str, Any]] = field(default=None, repr=False)
    _jwks: Optional[Dict[str, Any]] = field(default=None, repr=False)
    _jwks_fetched_at: float = field(default=0.0, repr=False)

    # JWKS cache TTL (1 hour)
    _JWKS_TTL: int = 3600

    # -----------------------------------------------------------------------
    # Discovery
    # -----------------------------------------------------------------------

    async def _fetch_discovery(self) -> Dict[str, Any]:
        """Fetch and cache the OpenID Provider Configuration document."""
        # Validate base configuration before network calls.
        if not isinstance(self.issuer_url, str) or not self.issuer_url.strip():
            raise OIDCConfigError(
                "OIDC issuer URL is not configured. Set oidc.issuer_url and restart."
            )

        if self._discovery is not None:
            return self._discovery

        url = self.issuer_url.rstrip("/") + "/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise OIDCConfigError(
                    f"Failed to fetch OIDC discovery from {url}: HTTP {resp.status_code}"
                )
            self._discovery = resp.json()

        required_keys = [
            "authorization_endpoint",
            "token_endpoint",
            "jwks_uri",
            "issuer",
        ]
        for key in required_keys:
            if key not in self._discovery:
                raise OIDCConfigError(f"OIDC discovery missing required key: {key}")

        # Verify issuer matches
        if self._discovery["issuer"].rstrip("/") != self.issuer_url.rstrip("/"):
            raise OIDCConfigError(
                f"OIDC issuer mismatch: expected {self.issuer_url}, got {self._discovery['issuer']}"
            )

        return self._discovery

    async def _fetch_jwks(self, force: bool = False) -> Dict[str, Any]:
        """Fetch and cache the JSON Web Key Set."""
        now = time.monotonic()
        if not force and self._jwks is not None and (now - self._jwks_fetched_at) < self._JWKS_TTL:
            return self._jwks

        discovery = await self._fetch_discovery()
        jwks_uri = discovery["jwks_uri"]

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(jwks_uri)
            if resp.status_code != 200:
                raise OIDCConfigError(
                    f"Failed to fetch JWKS from {jwks_uri}: HTTP {resp.status_code}"
                )
            self._jwks = resp.json()
            self._jwks_fetched_at = now

        return self._jwks

    # -----------------------------------------------------------------------
    # Authorization request
    # -----------------------------------------------------------------------

    async def build_auth_url(self, state: str, nonce: str, code_verifier: str) -> str:
        """Construct the authorization URL for the code+PKCE flow.

        Args:
            state: Opaque CSRF token.
            nonce: Replay-protection value embedded in the ID token.
            code_verifier: PKCE verifier (used to derive code_challenge).

        Returns:
            Full authorization URL to redirect the user to.
        """
        self._assert_runtime_config()
        discovery = await self._fetch_discovery()
        auth_endpoint = discovery["authorization_endpoint"]
        code_challenge = _make_code_challenge(code_verifier)

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        # Build URL with robust encoding. This safely handles values containing
        # spaces/special chars (for scopes, redirect_uri query params, etc.) and
        # preserves pre-existing authorization endpoint query parameters.
        split = urlsplit(auth_endpoint)
        existing_pairs = parse_qsl(split.query, keep_blank_values=True)
        auth_pairs = list(params.items())
        query = urlencode(existing_pairs + auth_pairs, doseq=True, quote_via=quote)
        return urlunsplit((split.scheme, split.netloc, split.path, query, split.fragment))

    async def build_logout_url(
        self, post_logout_redirect_uri: Optional[str] = None
    ) -> Optional[str]:
        """Construct the IdP logout URL when the provider supports it.

        Args:
            post_logout_redirect_uri: Optional URL for the IdP to redirect to after logout.

        Returns:
            Full end-session URL, or ``None`` when the provider does not expose
            ``end_session_endpoint`` in discovery metadata.
        """
        self._assert_runtime_config()
        discovery = await self._fetch_discovery()
        logout_endpoint = discovery.get("end_session_endpoint")
        if not isinstance(logout_endpoint, str) or not logout_endpoint.strip():
            return None

        params: dict[str, str] = {}
        if isinstance(post_logout_redirect_uri, str) and post_logout_redirect_uri.strip():
            params["post_logout_redirect_uri"] = post_logout_redirect_uri.strip()
            # Some providers require client_id when post_logout_redirect_uri is present.
            params["client_id"] = self.client_id

        split = urlsplit(logout_endpoint)
        existing_pairs = parse_qsl(split.query, keep_blank_values=True)
        logout_pairs = list(params.items())
        query = urlencode(existing_pairs + logout_pairs, doseq=True, quote_via=quote)
        return urlunsplit((split.scheme, split.netloc, split.path, query, split.fragment))

    # -----------------------------------------------------------------------
    # Code exchange
    # -----------------------------------------------------------------------

    async def exchange_code(self, code: str, code_verifier: str) -> Dict[str, Any]:
        """Exchange an authorization code for tokens.

        Args:
            code: Authorization code from the IdP callback.
            code_verifier: Original PKCE verifier.

        Returns:
            Token response dict (contains ``id_token``, ``access_token``, etc.).
        """
        self._assert_runtime_config()
        discovery = await self._fetch_discovery()
        token_endpoint = discovery["token_endpoint"]

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": code_verifier,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                token_endpoint,
                data=data,
                headers={"Accept": "application/json"},
            )

        if resp.status_code != 200:
            body = resp.text
            logger.warning(
                "oidc_code_exchange_failed",
                status=resp.status_code,
                body=body[:500],
            )
            raise OIDCError(f"Token exchange failed: HTTP {resp.status_code}")

        return resp.json()

    # -----------------------------------------------------------------------
    # ID token validation
    # -----------------------------------------------------------------------

    async def validate_id_token(self, id_token: str, nonce: str) -> Dict[str, Any]:
        """Validate an ID token's signature and standard claims.

        Args:
            id_token: Raw JWT string from the token response.
            nonce: Expected nonce value.

        Returns:
            Decoded claims dict.

        Raises:
            OIDCValidationError: On any validation failure.
        """
        jwks_data = await self._fetch_jwks()

        try:
            claims = self._decode_and_validate(id_token, jwks_data, nonce)
        except (BadSignatureError, KeyError):
            # Key may have rotated — refetch JWKS once and retry
            logger.info("oidc_jwks_key_not_found_retrying")
            jwks_data = await self._fetch_jwks(force=True)
            try:
                claims = self._decode_and_validate(id_token, jwks_data, nonce)
            except Exception as exc:
                raise OIDCValidationError(
                    f"ID token validation failed after JWKS refresh: {exc}"
                ) from exc

        return claims

    def _decode_and_validate(
        self, id_token: str, jwks_data: Dict[str, Any], nonce: str
    ) -> Dict[str, Any]:
        """Decode the JWT and validate standard OIDC claims."""
        keyset = JsonWebKey.import_key_set(jwks_data)

        try:
            claims = authlib_jwt.decode(id_token, keyset)
        except (DecodeError, BadSignatureError) as exc:
            raise OIDCValidationError(f"ID token decode/signature error: {exc}") from exc

        # Validate standard claims
        try:
            claims.validate()
        except ExpiredTokenError as exc:
            raise OIDCValidationError(f"ID token expired: {exc}") from exc
        except InvalidClaimError as exc:
            raise OIDCValidationError(f"ID token claim invalid: {exc}") from exc

        # Verify issuer
        iss = claims.get("iss", "")
        if iss.rstrip("/") != self.issuer_url.rstrip("/"):
            raise OIDCValidationError(f"Issuer mismatch: expected {self.issuer_url}, got {iss}")

        # Verify audience
        aud = claims.get("aud")
        if isinstance(aud, list):
            if self.client_id not in aud:
                raise OIDCValidationError(f"Audience mismatch: {self.client_id} not in {aud}")
        elif aud != self.client_id:
            raise OIDCValidationError(f"Audience mismatch: expected {self.client_id}, got {aud}")

        # Verify nonce
        if claims.get("nonce") != nonce:
            raise OIDCValidationError("Nonce mismatch — possible replay attack")

        # sub is required per OIDC Core
        if not claims.get("sub"):
            raise OIDCValidationError("ID token missing required 'sub' claim")

        return dict(claims)

    # -----------------------------------------------------------------------
    # Group claim check
    # -----------------------------------------------------------------------

    @staticmethod
    def check_group_claim(
        claims: Dict[str, Any],
        required_group: Optional[str],
        groups_claim: str = "groups",
    ) -> None:
        """Verify the ID token contains a required group value.

        Args:
            claims: Decoded ID token claims.
            required_group: Group value that must be present (``None`` to skip).
            groups_claim: Name of the claim containing group memberships.

        Raises:
            OIDCValidationError: If group is required but not present.
        """
        if required_group is None:
            return

        groups = claims.get(groups_claim)
        if groups is None:
            raise OIDCValidationError(
                f"ID token missing '{groups_claim}' claim; "
                f"required group '{required_group}' cannot be verified"
            )

        if isinstance(groups, str):
            groups = [groups]

        if not isinstance(groups, list):
            raise OIDCValidationError(
                f"'{groups_claim}' claim is not a list: {type(groups).__name__}"
            )

        if required_group not in groups:
            raise OIDCValidationError(f"User is not a member of required group '{required_group}'")

    # -----------------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------------

    def _assert_runtime_config(self) -> None:
        """Validate required provider attributes at runtime.

        This is a defensive check to produce actionable errors if configuration
        is malformed despite model-level validation (for example, in tests or
        manually-constructed configs).
        """
        missing: list[str] = []
        if not isinstance(self.issuer_url, str) or not self.issuer_url.strip():
            missing.append("oidc.issuer_url")
        if not isinstance(self.client_id, str) or not self.client_id.strip():
            missing.append("oidc.client_id")
        if not isinstance(self.redirect_uri, str) or not self.redirect_uri.strip():
            missing.append("oidc.redirect_uri")
        if missing:
            raise OIDCConfigError(
                "Missing required OIDC settings: "
                f"{', '.join(missing)}. "
                "Set these fields under config.oidc and restart."
            )

    def clear_cache(self) -> None:
        """Clear cached discovery and JWKS data."""
        self._discovery = None
        self._jwks = None
        self._jwks_fetched_at = 0.0


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_provider_instance: Optional[OIDCProvider] = None
_transaction_store_instance: Optional[OIDCTransactionStore] = None


def _oidc_config_debug(oidc_config: Any) -> Dict[str, Any]:
    """Return a sanitized OIDC config snapshot for logs/debugging."""
    return {
        "enabled": bool(getattr(oidc_config, "enabled", False)),
        "issuer_url": getattr(oidc_config, "issuer_url", None),
        "client_id": getattr(oidc_config, "client_id", None),
        "redirect_uri": getattr(oidc_config, "redirect_uri", None),
        "scopes": getattr(oidc_config, "scopes", None),
        "target_username": getattr(oidc_config, "target_username", None),
        "client_secret_set": bool(getattr(oidc_config, "client_secret", None)),
    }


def _validate_oidc_runtime_config(oidc_config: Any) -> None:
    """Defensively validate required OIDC config fields."""
    missing: list[str] = []

    issuer_url = getattr(oidc_config, "issuer_url", None)
    if not isinstance(issuer_url, str) or not issuer_url.strip():
        missing.append("oidc.issuer_url")

    client_id = getattr(oidc_config, "client_id", None)
    if not isinstance(client_id, str) or not client_id.strip():
        missing.append("oidc.client_id")

    redirect_uri = getattr(oidc_config, "redirect_uri", None)
    if not isinstance(redirect_uri, str) or not redirect_uri.strip():
        missing.append("oidc.redirect_uri")

    if missing:
        raise OIDCConfigError(
            "Missing required OIDC settings: "
            f"{', '.join(missing)}. "
            "Set these fields under config.oidc and restart."
        )


def get_oidc_provider(oidc_config: Any) -> OIDCProvider:
    """Get or create the singleton :class:`OIDCProvider`.

    Args:
        oidc_config: ``OIDCConfig`` instance (must have ``enabled=True``).

    Returns:
        Configured ``OIDCProvider``.

    Raises:
        OIDCConfigError: If OIDC is not enabled or required settings are missing.
    """
    global _provider_instance  # noqa: PLW0603
    if _provider_instance is not None:
        # If config changed while the singleton is live, highlight the mismatch.
        if bool(getattr(oidc_config, "enabled", False)):
            requested = _oidc_config_debug(oidc_config)
            if (
                requested.get("issuer_url") != _provider_instance.issuer_url
                or requested.get("client_id") != _provider_instance.client_id
                or requested.get("redirect_uri") != _provider_instance.redirect_uri
            ):
                logger.warning(
                    "oidc_provider_cached_config_mismatch",
                    active_issuer=_provider_instance.issuer_url,
                    active_client_id=_provider_instance.client_id,
                    active_redirect_uri=_provider_instance.redirect_uri,
                    requested_issuer=requested.get("issuer_url"),
                    requested_client_id=requested.get("client_id"),
                    requested_redirect_uri=requested.get("redirect_uri"),
                    hint=(
                        "OIDC provider is cached; restart the application to apply config changes."
                    ),
                )
        return _provider_instance

    if not oidc_config.enabled:
        raise OIDCConfigError("OIDC is not enabled")

    try:
        _validate_oidc_runtime_config(oidc_config)
    except OIDCConfigError:
        logger.error(
            "oidc_provider_config_invalid",
            oidc=_oidc_config_debug(oidc_config),
            hint="Check config.oidc required fields and restart.",
        )
        raise

    _provider_instance = OIDCProvider(
        issuer_url=oidc_config.issuer_url,
        client_id=oidc_config.client_id,
        redirect_uri=oidc_config.redirect_uri,
        scopes=oidc_config.scopes,
        client_secret=oidc_config.client_secret,
    )
    logger.info(
        "oidc_provider_initialized",
        issuer_url=oidc_config.issuer_url,
        client_id=oidc_config.client_id,
        redirect_uri=oidc_config.redirect_uri,
        client_secret_set=bool(oidc_config.client_secret),
    )
    return _provider_instance


def get_oidc_transaction_store() -> OIDCTransactionStore:
    """Get or create the singleton :class:`OIDCTransactionStore`."""
    global _transaction_store_instance  # noqa: PLW0603
    if _transaction_store_instance is None:
        _transaction_store_instance = OIDCTransactionStore()
    return _transaction_store_instance


def reset_oidc_singletons() -> None:
    """Reset singletons — for testing only."""
    global _provider_instance, _transaction_store_instance  # noqa: PLW0603
    _provider_instance = None
    _transaction_store_instance = None
