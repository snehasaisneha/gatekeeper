"""Security service for IP and email ban checking."""

from collections.abc import Mapping
from datetime import datetime
from ipaddress import ip_address, ip_network

from fastapi import Request
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.config import get_settings
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

def _normalize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


def _parse_forwarded_ip(value: str | None) -> str | None:
    if not value:
        return None

    candidate = value.split(",")[0].strip()
    if not candidate:
        return None

    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


def is_trusted_proxy(peer_ip: str | None) -> bool:
    if not peer_ip:
        return False

    try:
        parsed_peer_ip = ip_address(peer_ip)
    except ValueError:
        return False

    settings = get_settings()
    for trusted_proxy in settings.trusted_proxy_ips_list:
        try:
            if "/" in trusted_proxy:
                if parsed_peer_ip in ip_network(trusted_proxy, strict=False):
                    return True
            elif parsed_peer_ip == ip_address(trusted_proxy):
                return True
        except ValueError:
            continue

    return False


def get_client_ip_from_headers(
    request_headers: Mapping[str, str],
    *,
    peer_ip: str | None = None,
    default: str | None = None,
) -> str | None:
    """Extract client IP, trusting forwarded headers only from configured proxies."""
    normalized_headers = _normalize_headers(request_headers)

    if is_trusted_proxy(peer_ip):
        forwarded_ip = _parse_forwarded_ip(normalized_headers.get("x-forwarded-for"))
        if forwarded_ip:
            return forwarded_ip

        real_ip = _parse_forwarded_ip(normalized_headers.get("x-real-ip"))
        if real_ip:
            return real_ip

    return peer_ip or default


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from a FastAPI request."""
    peer_ip = request.client.host if request.client else None
    return get_client_ip_from_headers(request.headers, peer_ip=peer_ip)
