"""API-specific settings using Pydantic BaseSettings."""

from functools import lru_cache
from typing import List

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
    """

    model_config = SettingsConfigDict(
        env_prefix="FUZZBIN_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    allowed_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    log_requests: bool = True
    openapi_url: str = "/openapi.json"


@lru_cache
def get_settings() -> APISettings:
    """
    Get cached API settings instance.

    Returns:
        APISettings instance (cached)
    """
    return APISettings()
