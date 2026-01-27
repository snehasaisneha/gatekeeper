import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from staticauth.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="sessions")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Session {self.id} for user {self.user_id}>"

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
