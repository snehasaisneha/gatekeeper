from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AppCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000, description="App description")
    app_url: str | None = Field(None, max_length=500, description="URL to the app")
    roles: str = Field(
        default="admin,user",
        max_length=500,
        description="Comma-separated list of allowed roles",
    )


class AppRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    description: str | None
    app_url: str | None
    roles: str
    created_at: datetime


class AppPublic(BaseModel):
    """Schema for user-facing app information (discovery)."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    description: str | None
    app_url: str | None


class AppUpdate(BaseModel):
    """Schema for updating app fields."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)
    app_url: str | None = Field(None, max_length=500)
    roles: str | None = Field(None, max_length=500, description="Comma-separated list of roles")


class AppList(BaseModel):
    apps: list[AppRead]
    total: int


class AppUserAccess(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    role: str | None
    granted_at: datetime
    granted_by: str | None


class AppDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    description: str | None
    app_url: str | None
    roles: str
    created_at: datetime
    users: list[AppUserAccess]


class GrantAccess(BaseModel):
    email: str = Field(..., description="Email of user to grant access")
    role: str | None = Field(None, max_length=100, description="Optional role for the user")


class RevokeAccess(BaseModel):
    email: str = Field(..., description="Email of user to revoke access")


class BulkGrantAccess(BaseModel):
    """Schema for granting access to multiple apps at once."""

    emails: list[str] = Field(..., min_length=1, description="List of user emails")
    app_slugs: list[str] = Field(..., min_length=1, description="List of app slugs to grant access")
    role: str | None = Field(None, max_length=100, description="Optional role for all grants")
