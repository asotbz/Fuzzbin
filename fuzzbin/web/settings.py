"""API-specific settings using Pydantic BaseSettings."""

import warnings
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class APISettings(BaseSettings):
    """
    FastAPI application settings.

    Settings can be configured via environment variables with the prefix FUZZBIN_API_.
    For example: FUZZBIN_API_HOST=0.0.0.0, FUZZBIN_API_DEBUG=true

    Attributes:
        host: Server bind address (forced to 127.0.0.1 in insecure mode)
        port: Server bind port
        debug: Enable debug mode (auto-reload, verbose errors)
        allowed_origins: List of allowed CORS origins
        log_requests: Log all requests and responses
        openapi_url: OpenAPI schema URL (set to None to disable)
        auth_enabled: Enable JWT authentication (default: True)
        allow_insecure_mode: Allow running without auth (binds to localhost only)
        jwt_secret: Secret key for JWT signing (always required)
        jwt_algorithm: JWT signing algorithm (default: HS256)
        jwt_expires_minutes: Access token expiry in minutes (default: 30)
        refresh_token_expires_minutes: Refresh token expiry in minutes (default: 1440 = 24h)
        trusted_proxy_count: Number of trusted proxies for X-Forwarded-For parsing (default: 0)
        import_endpoints_enabled: Enable import endpoints (default: True)
        import_allowed_schemes: Allowed URL schemes for imports (default: ["https"])
        import_allowed_hosts: Allowed hostnames for imports (None = allow all)
    """

    model_config = SettingsConfigDict(
        env_prefix="FUZZBIN_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    log_requests: bool = True
    openapi_url: str = "/openapi.json"

    # Authentication settings
    auth_enabled: bool = True
    allow_insecure_mode: bool = False
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 30
    refresh_token_expires_minutes: int = 1440  # 24 hours (reduced from 7 days)

    # Proxy settings for IP extraction
    trusted_proxy_count: int = 0

    # Import endpoint settings
    import_endpoints_enabled: bool = True
    import_allowed_schemes: List[str] = ["https"]
    import_allowed_hosts: Optional[List[str]] = None  # None = allow all hosts

    @model_validator(mode="after")
    def validate_auth_config(self) -> "APISettings":
        """Validate authentication configuration.

        Security requirements:
        - jwt_secret is ALWAYS required (no default)
        - auth_enabled=False requires allow_insecure_mode=True
        - Insecure mode forces binding to localhost only
        """
        # jwt_secret is always required
        if not self.jwt_secret:
            raise ValueError(
                "FUZZBIN_API_JWT_SECRET must be set. "
                'Generate a secure secret with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )

        # If auth is disabled, require explicit insecure mode acknowledgment
        if not self.auth_enabled:
            if not self.allow_insecure_mode:
                raise ValueError(
                    "Authentication is required by default. To run without authentication, "
                    "set both FUZZBIN_API_AUTH_ENABLED=false AND FUZZBIN_API_ALLOW_INSECURE_MODE=true. "
                    "WARNING: Insecure mode should only be used for local development."
                )
            # Force localhost binding in insecure mode
            if self.host not in ("127.0.0.1", "localhost", "::1"):
                warnings.warn(
                    f"SECURITY: Insecure mode detected with non-localhost host '{self.host}'. "
                    "Forcing bind to 127.0.0.1 for safety.",
                    UserWarning,
                    stacklevel=2,
                )
                object.__setattr__(self, "host", "127.0.0.1")

        return self


@lru_cache
def get_settings() -> APISettings:
    """
    Get cached API settings instance.

    Returns:
        APISettings instance (cached)
    """
    return APISettings()
