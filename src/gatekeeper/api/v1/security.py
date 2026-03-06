"""Security API endpoints for IP and email banning."""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select

from gatekeeper.api.deps import AdminUser, DbSession
from gatekeeper.models.audit import AuditLog
from gatekeeper.models.security import BannedEmail, BannedIP, BanReason
from gatekeeper.schemas.auth import MessageResponse
from gatekeeper.schemas.security import (
    BannedEmailCreate,
    BannedEmailList,
    BannedEmailRead,
    BannedIPCreate,
    BannedIPList,
    BannedIPRead,
    SecurityEvent,
    SecurityEventList,
    SecurityStats,
)

router = APIRouter(prefix="/admin/security", tags=["Security"])


# ============================================================================
# Security Stats
# ============================================================================


@router.get(
    "/stats",
    response_model=SecurityStats,
    summary="Get security dashboard statistics",
    description="Get overview stats for the security dashboard. Admin only.",
)
async def get_security_stats(admin: AdminUser, db: DbSession) -> SecurityStats:
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Count active IP bans
    ip_ban_stmt = select(func.count(BannedIP.id)).where(
        and_(
            BannedIP.is_active == True,  # noqa: E712
            or_(BannedIP.expires_at.is_(None), BannedIP.expires_at > now),
        )
    )
    ip_ban_result = await db.execute(ip_ban_stmt)
    banned_ips = ip_ban_result.scalar() or 0

    # Count active email bans
    email_ban_stmt = select(func.count(BannedEmail.id)).where(
        and_(
            BannedEmail.is_active == True,  # noqa: E712
            or_(BannedEmail.expires_at.is_(None), BannedEmail.expires_at > now),
        )
    )
    email_ban_result = await db.execute(email_ban_stmt)
    banned_emails = email_ban_result.scalar() or 0

    # Count blocked requests today (security.blocked.* events)
    blocked_stmt = select(func.count(AuditLog.id)).where(
        and_(
            AuditLog.event_type.like("security.blocked.%"),
            AuditLog.created_at >= today_start,
        )
    )
    blocked_result = await db.execute(blocked_stmt)
    blocked_today = blocked_result.scalar() or 0

    # Count failed logins today
    failed_stmt = select(func.count(AuditLog.id)).where(
        and_(
            or_(
                AuditLog.event_type == "auth.signin.otp_failed",
                AuditLog.event_type == "auth.signin.passkey_failed",
            ),
            AuditLog.created_at >= today_start,
        )
    )
    failed_result = await db.execute(failed_stmt)
    failed_logins_today = failed_result.scalar() or 0

    return SecurityStats(
        blocked_today=blocked_today,
        banned_ips=banned_ips,
        banned_emails=banned_emails,
        failed_logins_today=failed_logins_today,
    )


# ============================================================================
# Banned IPs
# ============================================================================


@router.get(
    "/banned-ips",
    response_model=BannedIPList,
    summary="List banned IPs",
    description="List all banned IP addresses. Admin only.",
)
async def list_banned_ips(
    admin: AdminUser,
    db: DbSession,
    include_expired: bool = Query(default=False, description="Include expired bans"),
    include_inactive: bool = Query(default=False, description="Include inactive bans"),
) -> BannedIPList:
    now = datetime.utcnow()

    conditions = []
    if not include_inactive:
        conditions.append(BannedIP.is_active == True)  # noqa: E712
    if not include_expired:
        conditions.append(or_(BannedIP.expires_at.is_(None), BannedIP.expires_at > now))

    # Count total
    count_stmt = select(func.count(BannedIP.id))
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Get bans
    stmt = select(BannedIP).order_by(BannedIP.banned_at.desc())
    if conditions:
        stmt = stmt.where(and_(*conditions))
    result = await db.execute(stmt)
    bans = result.scalars().all()

    return BannedIPList(
        banned_ips=[
            BannedIPRead(
                id=ban.id,
                ip_address=ban.ip_address,
                reason=ban.reason,
                details=ban.details,
                banned_at=ban.banned_at,
                banned_by=ban.banned_by,
                expires_at=ban.expires_at,
                is_active=ban.is_active,
                associated_email=ban.associated_email,
            )
            for ban in bans
        ],
        total=total,
    )


@router.post(
    "/banned-ips",
    response_model=BannedIPRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ban an IP address",
    description="Add a new IP ban. Admin only.",
)
async def ban_ip(
    request: BannedIPCreate,
    admin: AdminUser,
    db: DbSession,
) -> BannedIPRead:
    # Check if IP is already banned
    existing_stmt = select(BannedIP).where(
        and_(
            BannedIP.ip_address == request.ip_address,
            BannedIP.is_active == True,  # noqa: E712
        )
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IP address is already banned",
        )

    ban = BannedIP(
        ip_address=request.ip_address,
        reason=request.reason.value,
        details=request.details,
        banned_by=admin.email,
        expires_at=request.expires_at,
        is_active=True,
        associated_email=request.associated_email,
    )
    db.add(ban)

    # Also ban associated email if provided
    if request.associated_email:
        email_ban = BannedEmail(
            email=request.associated_email,
            is_pattern=False,
            reason=BanReason.ASSOCIATED_IP.value,
            details=f"Associated with banned IP: {request.ip_address}",
            banned_by=admin.email,
            expires_at=request.expires_at,
            is_active=True,
            associated_ip=request.ip_address,
        )
        db.add(email_ban)

    # Log the action
    audit = AuditLog(
        event_type="security.ip.banned.manual",
        actor_email=admin.email,
        details={
            "ip_address": request.ip_address,
            "reason": request.reason.value,
            "associated_email": request.associated_email,
        },
    )
    db.add(audit)

    await db.flush()
    await db.refresh(ban)

    return BannedIPRead(
        id=ban.id,
        ip_address=ban.ip_address,
        reason=ban.reason,
        details=ban.details,
        banned_at=ban.banned_at,
        banned_by=ban.banned_by,
        expires_at=ban.expires_at,
        is_active=ban.is_active,
        associated_email=ban.associated_email,
    )


@router.delete(
    "/banned-ips/{ban_id}",
    response_model=MessageResponse,
    summary="Unban an IP address",
    description="Remove an IP ban. Admin only.",
)
async def unban_ip(
    ban_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
) -> MessageResponse:
    stmt = select(BannedIP).where(BannedIP.id == ban_id)
    result = await db.execute(stmt)
    ban = result.scalar_one_or_none()

    if not ban:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ban not found",
        )

    ban.is_active = False

    # Log the action
    audit = AuditLog(
        event_type="security.ip.unbanned",
        actor_email=admin.email,
        details={"ip_address": ban.ip_address, "original_reason": ban.reason},
    )
    db.add(audit)

    await db.flush()

    return MessageResponse(message=f"IP {ban.ip_address} has been unbanned")


# ============================================================================
# Banned Emails
# ============================================================================


@router.get(
    "/banned-emails",
    response_model=BannedEmailList,
    summary="List banned emails",
    description="List all banned email addresses and patterns. Admin only.",
)
async def list_banned_emails(
    admin: AdminUser,
    db: DbSession,
    include_expired: bool = Query(default=False, description="Include expired bans"),
    include_inactive: bool = Query(default=False, description="Include inactive bans"),
) -> BannedEmailList:
    now = datetime.utcnow()

    conditions = []
    if not include_inactive:
        conditions.append(BannedEmail.is_active == True)  # noqa: E712
    if not include_expired:
        conditions.append(or_(BannedEmail.expires_at.is_(None), BannedEmail.expires_at > now))

    # Count total
    count_stmt = select(func.count(BannedEmail.id))
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Get bans
    stmt = select(BannedEmail).order_by(BannedEmail.banned_at.desc())
    if conditions:
        stmt = stmt.where(and_(*conditions))
    result = await db.execute(stmt)
    bans = result.scalars().all()

    return BannedEmailList(
        banned_emails=[
            BannedEmailRead(
                id=ban.id,
                email=ban.email,
                is_pattern=ban.is_pattern,
                reason=ban.reason,
                details=ban.details,
                banned_at=ban.banned_at,
                banned_by=ban.banned_by,
                expires_at=ban.expires_at,
                is_active=ban.is_active,
                associated_ip=ban.associated_ip,
            )
            for ban in bans
        ],
        total=total,
    )


@router.post(
    "/banned-emails",
    response_model=BannedEmailRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ban an email address",
    description="Add a new email ban. Admin only.",
)
async def ban_email(
    request: BannedEmailCreate,
    admin: AdminUser,
    db: DbSession,
) -> BannedEmailRead:
    # Check if email is already banned
    existing_stmt = select(BannedEmail).where(
        and_(
            BannedEmail.email == request.email.lower(),
            BannedEmail.is_active == True,  # noqa: E712
        )
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already banned",
        )

    ban = BannedEmail(
        email=request.email.lower(),
        is_pattern=request.is_pattern,
        reason=request.reason.value,
        details=request.details,
        banned_by=admin.email,
        expires_at=request.expires_at,
        is_active=True,
        associated_ip=request.associated_ip,
    )
    db.add(ban)

    # Also ban associated IP if provided
    if request.associated_ip:
        ip_ban = BannedIP(
            ip_address=request.associated_ip,
            reason=BanReason.ASSOCIATED_EMAIL.value,
            details=f"Associated with banned email: {request.email}",
            banned_by=admin.email,
            expires_at=request.expires_at,
            is_active=True,
            associated_email=request.email.lower(),
        )
        db.add(ip_ban)

    # Log the action
    audit = AuditLog(
        event_type="security.email.banned.manual",
        actor_email=admin.email,
        details={
            "email": request.email,
            "is_pattern": request.is_pattern,
            "reason": request.reason.value,
            "associated_ip": request.associated_ip,
        },
    )
    db.add(audit)

    await db.flush()
    await db.refresh(ban)

    return BannedEmailRead(
        id=ban.id,
        email=ban.email,
        is_pattern=ban.is_pattern,
        reason=ban.reason,
        details=ban.details,
        banned_at=ban.banned_at,
        banned_by=ban.banned_by,
        expires_at=ban.expires_at,
        is_active=ban.is_active,
        associated_ip=ban.associated_ip,
    )


@router.delete(
    "/banned-emails/{ban_id}",
    response_model=MessageResponse,
    summary="Unban an email address",
    description="Remove an email ban. Admin only.",
)
async def unban_email(
    ban_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
) -> MessageResponse:
    stmt = select(BannedEmail).where(BannedEmail.id == ban_id)
    result = await db.execute(stmt)
    ban = result.scalar_one_or_none()

    if not ban:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ban not found",
        )

    ban.is_active = False

    # Log the action
    audit = AuditLog(
        event_type="security.email.unbanned",
        actor_email=admin.email,
        details={"email": ban.email, "original_reason": ban.reason},
    )
    db.add(audit)

    await db.flush()

    return MessageResponse(message=f"Email {ban.email} has been unbanned")


# ============================================================================
# Security Events
# ============================================================================


@router.get(
    "/events",
    response_model=SecurityEventList,
    summary="List security events",
    description="List recent security events from the audit log. Admin only.",
)
async def list_security_events(
    admin: AdminUser,
    db: DbSession,
    limit: int = Query(default=50, le=100, description="Maximum events to return"),
) -> SecurityEventList:
    # Security-related event types
    security_events = [
        "security.%",
        "auth.signin.otp_failed",
        "auth.signin.passkey_failed",
    ]

    # Build conditions
    conditions = []
    for pattern in security_events:
        if "%" in pattern:
            conditions.append(AuditLog.event_type.like(pattern))
        else:
            conditions.append(AuditLog.event_type == pattern)

    # Get events
    stmt = (
        select(AuditLog).where(or_(*conditions)).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()

    # Count total
    count_stmt = select(func.count(AuditLog.id)).where(or_(*conditions))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    events = []
    for log in logs:
        details = log.details or {}
        events.append(
            SecurityEvent(
                id=log.id,
                event_type=log.event_type,
                ip_address=details.get("ip_address"),
                email=log.actor_email or details.get("email"),
                details=details.get("details") or details.get("reason"),
                created_at=log.created_at,
            )
        )

    return SecurityEventList(events=events, total=total)
