import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from gatekeeper.database import Base


MAX_OTP_ATTEMPTS = 5


class OTPPurpose(str, enum.Enum):
    SIGNIN = "signin"
    REGISTER = "register"


class OTP(Base):
    __tablename__ = "otps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    purpose: Mapped[OTPPurpose] = mapped_column(
        Enum(OTPPurpose, values_callable=lambda x: [e.value for e in x]), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    used: Mapped[bool] = mapped_column(default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<OTP {self.code} for {self.email} ({self.purpose.value})>"

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.used and not self.is_expired and self.attempts < MAX_OTP_ATTEMPTS

    @property
    def has_attempts_remaining(self) -> bool:
        return self.attempts < MAX_OTP_ATTEMPTS
