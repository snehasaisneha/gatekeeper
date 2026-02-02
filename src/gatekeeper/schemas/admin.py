from pydantic import BaseModel, EmailStr, Field

from gatekeeper.models.user import UserStatus
from gatekeeper.schemas.user import UserRead


class AdminCreateUser(BaseModel):
    """Request to create a new user as admin."""

    email: EmailStr = Field(..., description="Email address for the new user")
    is_admin: bool = Field(default=False, description="Grant admin privileges to user")
    auto_approve: bool = Field(
        default=True,
        description="Automatically approve user (skip pending state)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "newuser@example.com",
                "is_admin": False,
                "auto_approve": True,
            }
        }
    }


class AdminUpdateUser(BaseModel):
    """Request to update a user's status or privileges."""

    status: UserStatus | None = Field(
        default=None,
        description="New user status (pending, approved, rejected)",
    )
    is_admin: bool | None = Field(default=None, description="Set admin privileges")

    model_config = {"json_schema_extra": {"example": {"status": "approved", "is_admin": False}}}


class UserList(BaseModel):
    """Paginated list of users."""

    users: list[UserRead] = Field(..., description="List of users for current page")
    total: int = Field(..., description="Total number of users matching query")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of users per page")

    model_config = {
        "json_schema_extra": {
            "example": {
                "users": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "user@example.com",
                        "status": "approved",
                        "is_admin": False,
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z",
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20,
            }
        }
    }


class PendingUserList(BaseModel):
    """List of users pending approval."""

    users: list[UserRead] = Field(..., description="List of pending users")
    total: int = Field(..., description="Total number of pending users")

    model_config = {
        "json_schema_extra": {
            "example": {
                "users": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "pendinguser@example.com",
                        "status": "pending",
                        "is_admin": False,
                        "created_at": "2024-01-01T00:00:00Z",
                        "updated_at": "2024-01-01T00:00:00Z",
                    }
                ],
                "total": 1,
            }
        }
    }
