"""API-specific settings using Pydantic BaseSettings."""

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
        host: Server bind address
        port: Server bind port
        debug: Enable debug mode (auto-reload, verbose errors)
        allowed_origins: List of allowed CORS origins
        log_requests: Log all requests and responses
        openapi_url: OpenAPI schema URL (set to None to disable)
        auth_enabled: Enable JWT authentication (default: False for local dev)
        jwt_secret: Secret key for JWT signing (required when auth_enabled=True)
        jwt_algorithm: JWT signing algorithm (default: HS256)
        jwt_expires_minutes: Access token expiry in minutes (default: 30)
        refresh_token_expires_minutes: Refresh token expiry in minutes (default: 10080 = 7 days)
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
    allowed_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    log_requests: bool = True
    openapi_url: str = "/openapi.json"

    # Authentication settings
    auth_enabled: bool = False
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 30
    refresh_token_expires_minutes: int = 10080  # 7 days

    @model_validator(mode="after")
    def validate_auth_config(self) -> "APISettings":
        """Validate that jwt_secret is provided when auth is enabled."""
        if self.auth_enabled and not self.jwt_secret:
            raise ValueError(
                "FUZZBIN_API_JWT_SECRET must be set when FUZZBIN_API_AUTH_ENABLED=true. "
                'Generate a secure secret with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return self


@lru_cache
def get_settings() -> APISettings:
    """
    Get cached API settings instance.

    Returns:
        APISettings instance (cached)
    """
    return APISettings()
