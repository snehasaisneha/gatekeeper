"""Security models for IP and email banning."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from gatekeeper.database import Base


class BanReason(str, Enum):
    """Reason for banning an IP or email."""

    BRUTE_FORCE = "brute_force"
    SPAM = "spam"
    REJECTED_USER = "rejected_user"
    ASSOCIATED_IP = "associated_ip"
    ASSOCIATED_EMAIL = "associated_email"
    RATE_LIMIT = "rate_limit"
    MANUAL = "manual"
    DISPOSABLE_EMAIL = "disposable_email"


class BannedIP(Base):
    """Represents a banned IP address.

    IPs can be banned manually by admins or automatically by the system
    when certain thresholds are exceeded (e.g., too many failed login attempts).
    """

    __tablename__ = "banned_ips"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ip_address: Mapped[str] = mapped_column(String(45), index=True, nullable=False)  # IPv6 max
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    banned_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), nullable=False
    )
    # Admin email who created the ban, or "SYSTEM" for automated bans
    banned_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Null means permanent ban
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Associated email that was banned together
    associated_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<BannedIP {self.ip_address} reason={self.reason}>"

    @property
    def is_expired(self) -> bool:
        """Check if the ban has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_effective(self) -> bool:
        """Check if the ban is currently in effect."""
        return self.is_active and not self.is_expired


class BannedEmail(Base):
    """Represents a banned email address or pattern.

    Emails can be banned exactly (user@example.com) or as patterns
    (*@tempmail.com) to block entire domains of disposable emails.
    """

    __tablename__ = "banned_emails"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    # If true, email is a wildcard pattern (use LIKE matching)
    is_pattern: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    banned_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), nullable=False
    )
    banned_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Associated IP that was banned together
    associated_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    def __repr__(self) -> str:
        pattern_marker = " (pattern)" if self.is_pattern else ""
        return f"<BannedEmail {self.email}{pattern_marker} reason={self.reason}>"

    @property
    def is_expired(self) -> bool:
        """Check if the ban has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_effective(self) -> bool:
        """Check if the ban is currently in effect."""
        return self.is_active and not self.is_expired

    def matches(self, email: str) -> bool:
        """Check if the given email matches this ban entry."""
        if not self.is_effective:
            return False

        email_lower = email.lower()

        if self.is_pattern:
            # Convert glob pattern to SQL LIKE pattern for comparison
            # *@tempmail.com -> match anything ending with @tempmail.com
            pattern = self.email.lower()
            if pattern.startswith("*"):
                return email_lower.endswith(pattern[1:])
            elif pattern.endswith("*"):
                return email_lower.startswith(pattern[:-1])
            else:
                return email_lower == pattern
        else:
            return email_lower == self.email.lower()
