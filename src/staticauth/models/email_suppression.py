import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from staticauth.database import Base


class SuppressionReason(str, enum.Enum):
    BOUNCE = "bounce"
    COMPLAINT = "complaint"


class EmailSuppression(Base):
    __tablename__ = "email_suppressions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    reason: Mapped[SuppressionReason] = mapped_column(
        Enum(SuppressionReason, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<EmailSuppression {self.email} ({self.reason.value})>"
