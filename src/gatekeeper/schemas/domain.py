"""Schemas for approved domain management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DomainCreate(BaseModel):
    """Schema for creating an approved domain."""

    domain: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Email domain to approve (e.g., 'example.com')",
    )


class DomainRead(BaseModel):
    """Schema for reading an approved domain."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    domain: str
    created_at: datetime
    created_by: str | None


class DomainList(BaseModel):
    """Schema for listing approved domains."""

    domains: list[DomainRead]
    total: int
