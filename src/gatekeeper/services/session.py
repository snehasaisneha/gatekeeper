import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.config import Settings, get_settings
from gatekeeper.models.session import Session
from gatekeeper.models.user import User
from gatekeeper.services.security import get_client_ip


def utcnow() -> datetime:
    """Return current UTC time as naive datetime (for SQLite compatibility)."""
    return datetime.utcnow()


class SessionService:
    def __init__(self, db: AsyncSession, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()

    def _generate_token(self) -> str:
        return secrets.token_urlsafe(32)

    async def create(
        self,
        user: User,
        *,
        request: Request | None = None,
        auth_method: str | None = None,
    ) -> Session:
        token = self._generate_token()
        now = utcnow()
        expires_at = now + timedelta(days=self.settings.session_expiry_days)

        session = Session(
            user_id=user.id,
            token=token,
            auth_method=auth_method,
            ip_address=get_client_ip(request) if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            expires_at=expires_at,
            last_seen_at=now,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_by_token(self, token: str) -> Session | None:
        stmt = select(Session).where(
            Session.token == token,
            Session.expires_at > utcnow(),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def touch(self, session: Session) -> None:
        now = utcnow()
        if session.last_seen_at and now - session.last_seen_at < timedelta(minutes=5):
            return
        session.last_seen_at = now
        await self.db.flush()

    async def get_session_and_user_by_token(self, token: str) -> tuple[Session, User] | None:
        session = await self.get_by_token(token)
        if not session:
            return None

        stmt = select(User).where(User.id == session.user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return None

        await self.touch(session)
        return session, user

    async def get_user_by_token(self, token: str) -> User | None:
        session_and_user = await self.get_session_and_user_by_token(token)
        if not session_and_user:
            return None
        _, user = session_and_user
        return user

    async def delete(self, token: str) -> bool:
        stmt = delete(Session).where(Session.token == token)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_session(
        self, session_id: uuid.UUID, *, user_id: uuid.UUID | None = None
    ) -> bool:
        stmt = delete(Session).where(Session.id == session_id)
        if user_id is not None:
            stmt = stmt.where(Session.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_all_for_user(self, user_id: uuid.UUID) -> int:
        stmt = delete(Session).where(Session.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.rowcount

    async def list_for_user(self, user_id: uuid.UUID) -> list[Session]:
        stmt = (
            select(Session)
            .where(Session.user_id == user_id, Session.expires_at > utcnow())
            .order_by(Session.last_seen_at.desc(), Session.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def cleanup_expired(self) -> int:
        stmt = delete(Session).where(Session.expires_at <= utcnow())
        result = await self.db.execute(stmt)
        return result.rowcount
