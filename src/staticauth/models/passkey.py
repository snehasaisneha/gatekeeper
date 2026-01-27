import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from staticauth.database import Base


class PasskeyCredential(Base):
    __tablename__ = "passkey_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    credential_id: Mapped[bytes] = mapped_column(LargeBinary, index=True, nullable=False)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transports: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), default="Passkey", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="passkeys")  # noqa: F821

    def __repr__(self) -> str:
        return f"<PasskeyCredential {self.name} for user {self.user_id}>"

    @property
    def transports_list(self) -> list[str]:
        if not self.transports:
            return []
        return self.transports.split(",")

    @transports_list.setter
    def transports_list(self, value: list[str]) -> None:
        self.transports = ",".join(value) if value else None
