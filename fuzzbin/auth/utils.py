"""Utility functions for authentication, including cookie management."""

from fastapi import Response

from fuzzbin.web.settings import APISettings


# Cookie configuration constants
REFRESH_TOKEN_COOKIE_NAME = "refresh_token"
REFRESH_TOKEN_COOKIE_PATH = "/auth"


def set_refresh_cookie(
    response: Response,
    refresh_token: str,
    settings: APISettings,
) -> None:
    """Set the refresh token as an httpOnly cookie.

    The cookie is configured with security best practices:
    - httpOnly: Prevents JavaScript access (XSS protection)
    - secure: Only sent over HTTPS in production (allows HTTP in debug mode)
    - samesite: 'lax' for CSRF protection while allowing same-site navigation
    - path: Restricted to /auth endpoints only

    Args:
        response: FastAPI Response object to set the cookie on.
        refresh_token: The JWT refresh token to store in the cookie.
        settings: API settings containing debug mode and token expiry configuration.
    """
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=not settings.debug,  # Allow HTTP in debug mode for localhost
        samesite="lax",
        path=REFRESH_TOKEN_COOKIE_PATH,
        max_age=settings.refresh_token_expires_minutes * 60,
    )


def clear_refresh_cookie(response: Response, settings: APISettings) -> None:
    """Clear the refresh token cookie.

    Removes the httpOnly refresh token cookie on logout or when
    the refresh token is invalid.

    Args:
        response: FastAPI Response object to clear the cookie from.
        settings: API settings for cookie security configuration.
    """
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        path=REFRESH_TOKEN_COOKIE_PATH,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
    )
