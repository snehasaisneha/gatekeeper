"""Security schemas for IP and email banning."""

import ipaddress
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from gatekeeper.models.security import BanReason

# Domain validation regex (simplified, allows subdomains)
DOMAIN_REGEX = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")


class BannedIPRead(BaseModel):
    """Banned IP information."""

    id: UUID = Field(..., description="Unique ban identifier")
    ip_address: str = Field(..., description="Banned IP address")
    reason: str = Field(..., description="Reason for ban")
    details: str | None = Field(None, description="Additional details")
    banned_at: datetime = Field(..., description="When the ban was created")
    banned_by: str | None = Field(None, description="Admin who created the ban or SYSTEM")
    expires_at: datetime | None = Field(None, description="When the ban expires (null = permanent)")
    is_active: bool = Field(..., description="Whether the ban is currently active")
    associated_email: str | None = Field(None, description="Associated email")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "ip_address": "192.168.1.100",
                "reason": "brute_force",
                "details": "15 failed login attempts in 1 hour",
                "banned_at": "2024-01-01T00:00:00Z",
                "banned_by": "admin@example.com",
                "expires_at": "2024-01-02T00:00:00Z",
                "is_active": True,
                "associated_email": "attacker@spam.net",
            }
        },
    }


class BannedIPCreate(BaseModel):
    """Request to ban an IP address."""

    ip_address: str = Field(..., description="IP address to ban")
    reason: BanReason = Field(default=BanReason.MANUAL, description="Reason for ban")
    details: str | None = Field(None, description="Additional details")
    expires_at: datetime | None = Field(None, description="When the ban expires (null = permanent)")
    associated_email: str | None = Field(None, description="Associated email to ban together")

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, v: str) -> str:
        """Validate that the IP address is a valid IPv4 or IPv6 address."""
        try:
            ipaddress.ip_address(v.strip())
            return v.strip()
        except ValueError:
            raise ValueError(
                "Invalid IP address format. Must be a valid IPv4 or IPv6 address."
            ) from None

    model_config = {
        "json_schema_extra": {
            "example": {
                "ip_address": "192.168.1.100",
                "reason": "manual",
                "details": "Suspicious activity detected",
                "expires_at": None,
            }
        }
    }


class BannedIPList(BaseModel):
    """List of banned IPs."""

    banned_ips: list[BannedIPRead] = Field(..., description="List of banned IPs")
    total: int = Field(..., description="Total number of banned IPs")

    model_config = {
        "json_schema_extra": {
            "example": {
                "banned_ips": [],
                "total": 0,
            }
        }
    }


class BannedEmailRead(BaseModel):
    """Banned email information."""

    id: UUID = Field(..., description="Unique ban identifier")
    email: str = Field(..., description="Banned email or pattern")
    is_pattern: bool = Field(..., description="Whether this is a pattern (e.g., *@tempmail.com)")
    reason: str = Field(..., description="Reason for ban")
    details: str | None = Field(None, description="Additional details")
    banned_at: datetime = Field(..., description="When the ban was created")
    banned_by: str | None = Field(None, description="Admin who created the ban or SYSTEM")
    expires_at: datetime | None = Field(None, description="When the ban expires (null = permanent)")
    is_active: bool = Field(..., description="Whether the ban is currently active")
    associated_ip: str | None = Field(None, description="Associated IP that was banned together")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "*@tempmail.com",
                "is_pattern": True,
                "reason": "disposable_email",
                "details": "Disposable email domain",
                "banned_at": "2024-01-01T00:00:00Z",
                "banned_by": "admin@example.com",
                "expires_at": None,
                "is_active": True,
                "associated_ip": None,
            }
        },
    }


class BannedEmailCreate(BaseModel):
    """Request to ban an email address or pattern."""

    email: str = Field(..., description="Email address or pattern to ban")
    is_pattern: bool = Field(default=False, description="Whether this is a pattern")
    reason: BanReason = Field(default=BanReason.MANUAL, description="Reason for ban")
    details: str | None = Field(None, description="Additional details")
    expires_at: datetime | None = Field(None, description="When the ban expires (null = permanent)")
    associated_ip: str | None = Field(None, description="Associated IP to ban together")

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "*@tempmail.com",
                "is_pattern": True,
                "reason": "disposable_email",
                "details": "Disposable email domain",
            }
        }
    }


class BannedEmailList(BaseModel):
    """List of banned emails."""

    banned_emails: list[BannedEmailRead] = Field(..., description="List of banned emails")
    total: int = Field(..., description="Total number of banned emails")

    model_config = {
        "json_schema_extra": {
            "example": {
                "banned_emails": [],
                "total": 0,
            }
        }
    }


class SecurityStats(BaseModel):
    """Security dashboard statistics."""

    blocked_today: int = Field(..., description="Number of blocked requests today")
    banned_ips: int = Field(..., description="Number of active IP bans")
    banned_emails: int = Field(..., description="Number of active email bans")
    failed_logins_today: int = Field(..., description="Number of failed logins today")

    model_config = {
        "json_schema_extra": {
            "example": {
                "blocked_today": 12,
                "banned_ips": 3,
                "banned_emails": 5,
                "failed_logins_today": 47,
            }
        }
    }


class SecurityEvent(BaseModel):
    """A security event from the audit log."""

    id: UUID = Field(..., description="Event identifier")
    event_type: str = Field(..., description="Type of security event")
    ip_address: str | None = Field(None, description="IP address involved")
    email: str | None = Field(None, description="Email involved")
    details: str | None = Field(None, description="Event details")
    created_at: datetime = Field(..., description="When the event occurred")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "event_type": "security.ip.banned.auto",
                "ip_address": "192.168.1.100",
                "email": None,
                "details": "15 failed login attempts",
                "created_at": "2024-01-01T00:00:00Z",
            }
        }
    }


class SecurityEventList(BaseModel):
    """List of security events."""

    events: list[SecurityEvent] = Field(..., description="List of security events")
    total: int = Field(..., description="Total number of events")

    model_config = {
        "json_schema_extra": {
            "example": {
                "events": [],
                "total": 0,
            }
        }
    }
