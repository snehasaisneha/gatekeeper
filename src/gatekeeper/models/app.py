import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gatekeeper.database import Base


class AccessRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class App(Base):
    __tablename__ = "apps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    app_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    roles: Mapped[str] = mapped_column(Text, default="admin,user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), nullable=False
    )

    user_access: Mapped[list["UserAppAccess"]] = relationship(
        back_populates="app", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<App {self.slug} ({self.name})>"


class UserAppAccess(Base):
    __tablename__ = "user_app_access"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    app_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("apps.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), nullable=False
    )
    granted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship(back_populates="app_access")  # noqa: F821
    app: Mapped["App"] = relationship(back_populates="user_access")

    def __repr__(self) -> str:
        return f"<UserAppAccess {self.user_id} -> {self.app_id} (role={self.role})>"


class AppAccessRequest(Base):
    __tablename__ = "app_access_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    app_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("apps.id", ondelete="CASCADE"), nullable=False
    )
    requested_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AccessRequestStatus] = mapped_column(
        Enum(AccessRequestStatus, values_callable=lambda x: [e.value for e in x]),
        default=AccessRequestStatus.PENDING,
        nullable=False,
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship()  # noqa: F821
    app: Mapped["App"] = relationship()

    def __repr__(self) -> str:
        return f"<AppAccessRequest {self.user_id} -> {self.app_id} ({self.status.value})>"
