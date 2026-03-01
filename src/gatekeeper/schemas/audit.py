"""Schemas for audit log API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuditLogRead(BaseModel):
    """Audit log entry response."""

    id: UUID = Field(..., description="Unique audit log ID")
    timestamp: datetime = Field(..., description="When the event occurred")
    actor_id: UUID | None = Field(None, description="User ID who performed the action")
    actor_email: str | None = Field(None, description="Email of actor")
    event_type: str = Field(..., description="Event type (e.g., auth.signin.google)")
    target_type: str | None = Field(None, description="Type of target (user, app, etc.)")
    target_id: str | None = Field(None, description="ID of target")
    ip_address: str | None = Field(None, description="Client IP address")
    user_agent: str | None = Field(None, description="Client user agent")
    details: dict[str, Any] | None = Field(None, description="Additional event details")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2024-01-15T10:30:00Z",
                "actor_id": "123e4567-e89b-12d3-a456-426614174001",
                "actor_email": "user@example.com",
                "event_type": "auth.signin.google",
                "target_type": None,
                "target_id": None,
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0...",
                "details": {"method": "google", "device": {"browser": "Chrome", "os": "macOS"}},
            }
        },
    }


class AuditLogList(BaseModel):
    """Paginated audit log list response."""

    logs: list[AuditLogRead] = Field(..., description="List of audit logs")
    total: int = Field(..., description="Total number of matching logs")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")

    model_config = {
        "json_schema_extra": {
            "example": {
                "logs": [],
                "total": 100,
                "page": 1,
                "page_size": 50,
            }
        }
    }
