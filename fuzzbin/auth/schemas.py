"""Pydantic schemas for authentication requests and responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Request schema for user login."""

    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Username for authentication",
        examples=["admin"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Password for authentication",
        examples=["changeme"],
    )


class TokenResponse(BaseModel):
    """Response schema for successful authentication (internal use with both tokens)."""

    access_token: str = Field(
        ...,
        description="JWT access token for API authentication",
    )
    refresh_token: str = Field(
        ...,
        description="JWT refresh token for obtaining new access tokens",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')",
    )
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds",
    )


class AccessTokenResponse(BaseModel):
    """Response schema for authentication (refresh token sent via httpOnly cookie).

    This response is returned by login and refresh endpoints. The refresh token
    is set as an httpOnly cookie for security (not accessible to JavaScript),
    so only the access token is included in the response body.
    """

    access_token: str = Field(
        ...,
        description="JWT access token for API authentication",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')",
    )
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds",
    )


class RefreshRequest(BaseModel):
    """Request schema for token refresh."""

    refresh_token: str = Field(
        ...,
        description="Valid refresh token to exchange for new access token",
    )


class PasswordChangeRequest(BaseModel):
    """Request schema for password change."""

    current_password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Current password for verification",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password (minimum 8 characters)",
    )


class UserInfo(BaseModel):
    """User information returned from token validation."""

    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    is_active: bool = Field(..., description="Whether the user account is active")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")


class UserDB(BaseModel):
    """Internal user model from database."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    password_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
