import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from gatekeeper.database import Base


class AuditLog(Base):
    """Audit log entry for tracking auth and admin events."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), nullable=False
    )

    # Who performed the action
    actor_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # What happened
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # What was affected (optional)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Request context
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Flexible details (JSON string)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog {self.event_type} by {self.actor_email} at {self.timestamp}>"
