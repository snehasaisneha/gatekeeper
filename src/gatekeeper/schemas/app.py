from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from gatekeeper.models.app import AccessRequestStatus


class AppCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=255)


class AppRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    created_at: datetime


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
    created_at: datetime
    users: list[AppUserAccess]


class GrantAccess(BaseModel):
    email: str = Field(..., description="Email of user to grant access")
    role: str | None = Field(None, max_length=100, description="Optional role for the user")


class RevokeAccess(BaseModel):
    email: str = Field(..., description="Email of user to revoke access")


class AccessRequestCreate(BaseModel):
    message: str | None = Field(
        None, max_length=500, description="Optional message explaining why access is needed"
    )


class AccessRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_email: str
    user_name: str | None
    app_slug: str
    app_name: str
    message: str | None
    status: AccessRequestStatus
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime


class AccessRequestReview(BaseModel):
    role: str | None = Field(None, max_length=100, description="Role to assign if approving")
