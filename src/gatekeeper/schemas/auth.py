from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from gatekeeper.models.user import UserStatus


class OTPRequest(BaseModel):
    """Request to send an OTP to an email address."""

    email: EmailStr = Field(..., description="Email address to send OTP to")

    model_config = {"json_schema_extra": {"example": {"email": "user@example.com"}}}


class OTPVerifyRequest(BaseModel):
    """Request to verify an OTP code."""

    email: EmailStr = Field(..., description="Email address used for OTP")
    code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6-digit OTP code",
    )

    model_config = {
        "json_schema_extra": {"example": {"email": "user@example.com", "code": "123456"}}
    }


class PasskeyOptionsRequest(BaseModel):
    """Request to get WebAuthn authentication options."""

    email: EmailStr | None = Field(
        default=None,
        description="Optional email to filter allowed credentials for this user",
    )

    model_config = {"json_schema_extra": {"example": {"email": "user@example.com"}}}


class WebAuthnCredentialResponse(BaseModel):
    """WebAuthn credential response from the browser authenticator."""

    id: str = Field(..., description="Base64URL encoded credential ID")
    rawId: str = Field(..., description="Base64URL encoded raw credential ID")
    type: str = Field(default="public-key", description="Credential type")
    response: dict[str, Any] = Field(
        ...,
        description="Authenticator response containing clientDataJSON and authenticatorData",
    )
    authenticatorAttachment: str | None = Field(
        default=None,
        description="Authenticator attachment type (platform or cross-platform)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "abc123...",
                "rawId": "abc123...",
                "type": "public-key",
                "response": {
                    "clientDataJSON": "eyJ0eXBlIjoi...",
                    "authenticatorData": "SZYN5Y...",
                },
            }
        }
    }


class PasskeyVerifyRequest(BaseModel):
    """Request to verify a WebAuthn credential."""

    credential: WebAuthnCredentialResponse = Field(
        ...,
        description="WebAuthn credential response from browser",
    )
    name: str | None = Field(
        default=None,
        max_length=50,
        description="Optional user-friendly name for the passkey",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "credential": {
                    "id": "abc123...",
                    "rawId": "abc123...",
                    "type": "public-key",
                    "response": {
                        "clientDataJSON": "eyJ0eXBlIjoi...",
                        "authenticatorData": "SZYN5Y...",
                    },
                },
                "name": "My MacBook",
            }
        }
    }


class UserResponse(BaseModel):
    """User information response."""

    id: UUID = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User's email address")
    name: str | None = Field(None, description="User's display name")
    status: UserStatus = Field(..., description="User account status")
    is_admin: bool = Field(..., description="Whether user has admin privileges")
    is_seeded: bool = Field(..., description="Whether user is a seeded admin")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "name": "John Doe",
                "status": "approved",
                "is_admin": False,
                "is_seeded": False,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        },
    }


class ProfileUpdateRequest(BaseModel):
    """Request to update user profile."""

    name: str | None = Field(None, max_length=255, description="User's display name")

    model_config = {"json_schema_extra": {"example": {"name": "John Doe"}}}


class AuthResponse(BaseModel):
    """Authentication response with optional user data."""

    message: str = Field(..., description="Status message")
    user: UserResponse | None = Field(
        default=None,
        description="User details (present if authenticated and approved)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Successfully signed in",
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "user@example.com",
                    "status": "approved",
                    "is_admin": False,
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-01T00:00:00Z",
                },
            }
        }
    }


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str = Field(..., description="Status message")
    detail: str | None = Field(default=None, description="Additional details")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "OTP sent successfully",
                "detail": "Check your email for the 6-digit code",
            }
        }
    }


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str = Field(..., description="Error message describing what went wrong")

    model_config = {"json_schema_extra": {"example": {"detail": "Invalid or expired OTP"}}}


class PasskeyInfo(BaseModel):
    """Registered passkey information."""

    id: str = Field(..., description="Unique passkey identifier")
    name: str = Field(..., description="User-friendly name for the passkey")
    created_at: str = Field(..., description="When the passkey was registered (ISO 8601)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Passkey",
                "created_at": "2024-01-01T00:00:00Z",
            }
        }
    }


class UserAppAccessInfo(BaseModel):
    """App access information for a user."""

    app_slug: str = Field(..., description="App slug identifier")
    app_name: str = Field(..., description="App display name")
    role: str | None = Field(None, description="User's role in this app")
    granted_at: datetime = Field(..., description="When access was granted")

    model_config = {
        "json_schema_extra": {
            "example": {
                "app_slug": "eng-docs",
                "app_name": "Engineering Docs",
                "role": "admin",
                "granted_at": "2024-01-01T00:00:00Z",
            }
        }
    }
