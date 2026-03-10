from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from gatekeeper.models.user import UserStatus
from gatekeeper.schemas.audit import AuditLogRead
from gatekeeper.schemas.security import BannedEmailRead, BannedIPRead
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
    notify_new_registrations: bool | None = Field(
        default=None,
        description="Email notifications for new pending registrations (admin only)",
    )
    notify_all_registrations: bool | None = Field(
        default=None,
        description="Email notifications for all new sign-ups (admin only)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {"status": "approved", "is_admin": False, "notify_new_registrations": True}
        }
    }


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


class UserLookupResponse(BaseModel):
    """Lookup result for an email address in the admin UI."""

    exists: bool = Field(..., description="Whether a user with this email already exists")
    user: UserRead | None = Field(
        default=None,
        description="Existing user details when found",
    )


class DeploymentConfig(BaseModel):
    """Deployment configuration for Nginx setup instructions."""

    cookie_domain: str | None = Field(None, description="Root cookie domain (e.g., .example.com)")
    app_url: str = Field(..., description="Backend API URL (e.g., https://auth.example.com)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "cookie_domain": ".example.com",
                "app_url": "https://auth.example.com",
            }
        }
    }


class UserInvestigationAppAccess(BaseModel):
    """Expanded app access information for a user."""

    app_slug: str = Field(..., description="App slug")
    app_name: str = Field(..., description="App name")
    app_description: str | None = Field(None, description="App description")
    app_url: str | None = Field(None, description="App URL")
    role: str | None = Field(None, description="Granted role")
    granted_at: datetime = Field(..., description="When access was granted")
    granted_by: str | None = Field(None, description="Who granted access")


class UserSessionRead(BaseModel):
    """Active session metadata for admin investigation."""

    id: UUID = Field(..., description="Session identifier")
    auth_method: str | None = Field(None, description="Method used to create the session")
    ip_address: str | None = Field(None, description="Session creation IP")
    user_agent: str | None = Field(None, description="Original user agent")
    created_at: datetime = Field(..., description="When the session was created")
    last_seen_at: datetime = Field(..., description="Most recent activity timestamp")
    expires_at: datetime = Field(..., description="When the session expires")


class UserInvestigationRead(BaseModel):
    """Investigation view for a user."""

    user: UserRead = Field(..., description="User summary")
    app_access: list[UserInvestigationAppAccess] = Field(
        default_factory=list, description="Explicit app access grants"
    )
    active_sessions: list[UserSessionRead] = Field(
        default_factory=list, description="Active sessions for the user"
    )
    recent_audit_logs: list[AuditLogRead] = Field(
        default_factory=list, description="Recent audit logs involving the user"
    )
    active_ip_bans: list[BannedIPRead] = Field(
        default_factory=list, description="Active IP bans associated with the user"
    )
    active_email_bans: list[BannedEmailRead] = Field(
        default_factory=list, description="Active email bans associated with the user"
    )
    recent_ip_addresses: list[str] = Field(
        default_factory=list, description="Most recent distinct IP addresses seen for the user"
    )
    last_auth_method: str | None = Field(None, description="Most recent successful auth method")
    last_seen_at: datetime | None = Field(None, description="Most recent authenticated activity")
