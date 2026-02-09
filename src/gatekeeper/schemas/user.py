from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from gatekeeper.models.user import UserStatus


class UserCreate(BaseModel):
    """Internal schema for creating a user."""

    email: EmailStr = Field(..., description="User's email address")
    status: UserStatus = Field(default=UserStatus.PENDING, description="Initial user status")
    is_admin: bool = Field(default=False, description="Whether user has admin privileges")


class UserRead(BaseModel):
    """User information."""

    id: UUID = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User's email address")
    name: str | None = Field(None, description="User's display name")
    status: UserStatus = Field(..., description="User account status (pending, approved, rejected)")
    is_admin: bool = Field(..., description="Whether user has admin privileges")
    is_seeded: bool = Field(..., description="Whether user is a seeded admin")
    is_internal: bool = Field(
        default=False, description="Whether user is internal (email domain in approved_domains)"
    )
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
                "is_internal": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        },
    }


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    name: str | None = Field(default=None, description="User's display name")
    status: UserStatus | None = Field(default=None, description="New user status")
    is_admin: bool | None = Field(default=None, description="Set admin privileges")
