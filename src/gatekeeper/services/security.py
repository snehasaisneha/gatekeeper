"""Security service for IP and email ban checking."""

from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.models.security import BannedEmail, BannedIP


class SecurityService:
    """Service for checking IP and email bans."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def is_ip_banned(self, ip_address: str) -> bool:
        """Check if an IP address is banned."""
        now = datetime.utcnow()

        stmt = select(BannedIP).where(
            and_(
                BannedIP.ip_address == ip_address,
                BannedIP.is_active == True,  # noqa: E712
                or_(BannedIP.expires_at.is_(None), BannedIP.expires_at > now),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def is_email_banned(self, email: str) -> bool:
        """Check if an email is banned (exact match or pattern)."""
        now = datetime.utcnow()
        email_lower = email.lower()

        # First check exact matches
        stmt = select(BannedEmail).where(
            and_(
                BannedEmail.email == email_lower,
                BannedEmail.is_pattern == False,  # noqa: E712
                BannedEmail.is_active == True,  # noqa: E712
                or_(BannedEmail.expires_at.is_(None), BannedEmail.expires_at > now),
            )
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            return True

        # Then check patterns
        stmt = select(BannedEmail).where(
            and_(
                BannedEmail.is_pattern == True,  # noqa: E712
                BannedEmail.is_active == True,  # noqa: E712
                or_(BannedEmail.expires_at.is_(None), BannedEmail.expires_at > now),
            )
        )
        result = await self.db.execute(stmt)
        patterns = result.scalars().all()

        return any(pattern.matches(email_lower) for pattern in patterns)


def get_client_ip(request_headers: dict, default: str = "unknown") -> str:
    """Extract client IP from request headers.

    Checks X-Forwarded-For and X-Real-IP headers for proxied requests.
    """
    # Check X-Forwarded-For header (comma-separated list, first is client)
    forwarded_for = request_headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request_headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    return default
