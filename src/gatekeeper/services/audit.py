"""Audit logging service for tracking auth and admin events."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.models.audit import AuditLog
from gatekeeper.models.user import User
from gatekeeper.services.security import get_client_ip

logger = logging.getLogger(__name__)


class EventType:
    """Audit event type constants."""

    # Auth events
    AUTH_SIGNIN_OTP_SENT = "auth.signin.otp_sent"
    AUTH_SIGNIN_OTP_SUCCESS = "auth.signin.otp_success"
    AUTH_SIGNIN_OTP_FAILED = "auth.signin.otp_failed"
    AUTH_SIGNIN_GOOGLE = "auth.signin.google"
    AUTH_SIGNIN_GITHUB = "auth.signin.github"
    AUTH_SIGNIN_PASSKEY = "auth.signin.passkey"
    AUTH_SIGNIN_FAILED = "auth.signin.failed"
    AUTH_SIGNOUT = "auth.signout"
    AUTH_SESSION_EXPIRED = "auth.session.expired"
    AUTH_SESSION_REVOKED = "auth.session.revoked"

    # Admin events
    ADMIN_USER_CREATED = "admin.user.created"
    ADMIN_USER_APPROVED = "admin.user.approved"
    ADMIN_USER_REJECTED = "admin.user.rejected"
    ADMIN_USER_DELETED = "admin.user.deleted"
    ADMIN_USER_UPDATED = "admin.user.updated"
    ADMIN_APP_CREATED = "admin.app.created"
    ADMIN_APP_UPDATED = "admin.app.updated"
    ADMIN_APP_DELETED = "admin.app.deleted"
    ADMIN_ACCESS_GRANTED = "admin.access.granted"
    ADMIN_ACCESS_REVOKED = "admin.access.revoked"
    ADMIN_DOMAIN_ADDED = "admin.domain.added"
    ADMIN_DOMAIN_REMOVED = "admin.domain.removed"


def parse_user_agent(user_agent: str | None) -> dict[str, str]:
    """Parse user agent string into device info."""
    if not user_agent:
        return {}

    device_info: dict[str, str] = {}

    # Simple browser detection
    ua_lower = user_agent.lower()
    if "chrome" in ua_lower and "edg" not in ua_lower:
        device_info["browser"] = "Chrome"
    elif "firefox" in ua_lower:
        device_info["browser"] = "Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        device_info["browser"] = "Safari"
    elif "edg" in ua_lower:
        device_info["browser"] = "Edge"
    else:
        device_info["browser"] = "Other"

    # Simple OS detection (check mobile OS first since they contain desktop OS strings)
    if "iphone" in ua_lower or "ipad" in ua_lower:
        device_info["os"] = "iOS"
    elif "android" in ua_lower:
        device_info["os"] = "Android"
    elif "windows" in ua_lower:
        device_info["os"] = "Windows"
    elif "mac os" in ua_lower or "macos" in ua_lower:
        device_info["os"] = "macOS"
    elif "linux" in ua_lower:
        device_info["os"] = "Linux"
    else:
        device_info["os"] = "Other"

    # Device type
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        device_info["type"] = "mobile"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        device_info["type"] = "tablet"
    else:
        device_info["type"] = "desktop"

    return device_info


class AuditService:
    """Service for logging audit events."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        event_type: str,
        *,
        actor: User | None = None,
        actor_id: uuid.UUID | None = None,
        actor_email: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        request: Request | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """
        Log an audit event.

        Args:
            event_type: Event type constant (use EventType.*)
            actor: User who performed the action (optional)
            actor_id: UUID of actor (alternative to actor)
            actor_email: Email of actor (alternative to actor)
            target_type: Type of target ('user', 'app', 'session', 'domain')
            target_id: ID of target
            request: FastAPI request (for extracting IP/user-agent)
            ip_address: Override IP address
            user_agent: Override user agent
            details: Additional event details (will be JSON serialized)
        """
        # Resolve actor info
        resolved_actor_id = actor_id
        resolved_actor_email = actor_email
        if actor:
            resolved_actor_id = actor.id
            resolved_actor_email = actor.email

        # Extract request context
        resolved_ip = ip_address
        resolved_ua = user_agent
        if request:
            resolved_ip = resolved_ip or get_client_ip(request)
            resolved_ua = resolved_ua or request.headers.get("user-agent")

        # Add device info to details for auth events
        if details is None:
            details = {}
        if resolved_ua and event_type.startswith("auth.signin"):
            details["device"] = parse_user_agent(resolved_ua)

        # Serialize details
        details_json = json.dumps(details) if details else None

        # Create audit log entry
        audit_log = AuditLog(
            id=uuid.uuid4(),
            timestamp=datetime.utcnow(),
            actor_id=resolved_actor_id,
            actor_email=resolved_actor_email,
            event_type=event_type,
            target_type=target_type,
            target_id=target_id,
            ip_address=resolved_ip,
            user_agent=resolved_ua,
            details=details_json,
        )

        self.db.add(audit_log)
        await self.db.flush()

        logger.debug(f"Audit: {event_type} by {resolved_actor_email or 'system'}")

        return audit_log

    async def log_auth_success(
        self,
        method: str,
        user: User,
        request: Request,
        *,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Log a successful authentication."""
        event_map = {
            "otp": EventType.AUTH_SIGNIN_OTP_SUCCESS,
            "google": EventType.AUTH_SIGNIN_GOOGLE,
            "github": EventType.AUTH_SIGNIN_GITHUB,
            "passkey": EventType.AUTH_SIGNIN_PASSKEY,
        }
        event_type = event_map.get(method, EventType.AUTH_SIGNIN_OTP_SUCCESS)

        log_details = {"method": method}
        if details:
            log_details.update(details)

        return await self.log(
            event_type,
            actor=user,
            request=request,
            details=log_details,
        )

    async def log_auth_failed(
        self,
        method: str,
        email: str | None,
        request: Request,
        *,
        reason: str | None = None,
    ) -> AuditLog:
        """Log a failed authentication attempt."""
        details = {"method": method}
        if reason:
            details["reason"] = reason

        return await self.log(
            EventType.AUTH_SIGNIN_FAILED,
            actor_email=email,
            request=request,
            details=details,
        )

    async def log_signout(self, user: User, request: Request) -> AuditLog:
        """Log a user signing out."""
        return await self.log(
            EventType.AUTH_SIGNOUT,
            actor=user,
            request=request,
        )

    async def log_admin_action(
        self,
        event_type: str,
        admin: User,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
        target_email: str | None = None,
        changes: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> AuditLog:
        """Log an admin action."""
        details: dict[str, Any] = {}
        if target_email:
            details["target_email"] = target_email
        if changes:
            details["changes"] = changes

        return await self.log(
            event_type,
            actor=admin,
            target_type=target_type,
            target_id=target_id,
            request=request,
            details=details if details else None,
        )
