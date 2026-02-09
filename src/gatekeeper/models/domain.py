"""Approved domain model for internal user identification."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gatekeeper.database import Base


class ApprovedDomain(Base):
    """Represents an approved email domain for internal users.

    Users with email addresses from approved domains are considered "internal"
    and have automatic access to all apps with the "user" role.
    """

    __tablename__ = "approved_domains"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<ApprovedDomain {self.domain}>"
