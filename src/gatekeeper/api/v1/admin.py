import json
import uuid
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.api.deps import AdminUser, DbSession
from gatekeeper.config import get_settings
from gatekeeper.models.app import App, UserAppAccess
from gatekeeper.models.audit import AuditLog
from gatekeeper.models.branding import Branding
from gatekeeper.models.domain import ApprovedDomain
from gatekeeper.models.security import BannedEmail, BannedIP, BanReason
from gatekeeper.models.user import User, UserStatus
from gatekeeper.schemas.admin import (
    AdminCreateUser,
    AdminUpdateUser,
    DeploymentConfig,
    PendingUserList,
    UserList,
    UserLookupResponse,
)
from gatekeeper.schemas.app import (
    AppCreate,
    AppDetail,
    AppList,
    AppRead,
    AppUpdate,
    AppUserAccess,
    BulkGrantAccess,
    GrantAccess,
)
from gatekeeper.schemas.audit import AuditLogList, AuditLogRead
from gatekeeper.schemas.auth import ErrorResponse, MessageResponse
from gatekeeper.schemas.branding import (
    AccentPresetsResponse,
    BrandingReadAdmin,
    BrandingUpdate,
)
from gatekeeper.schemas.domain import DomainCreate, DomainList, DomainRead
from gatekeeper.schemas.user import UserRead
from gatekeeper.services.email import EmailService

router = APIRouter(prefix="/admin", tags=["Admin"])


async def _get_approved_domains_set(db: AsyncSession) -> set[str]:
    """Fetch all approved domains as a set for efficient lookup."""
    stmt = select(ApprovedDomain.domain)
    result = await db.execute(stmt)
    return set(result.scalars().all())


def _get_reserved_app_slugs() -> set[str]:
    reserved_slugs: set[str] = set()
    app_hostname = urlparse(get_settings().app_url).hostname
    if not app_hostname:
        return reserved_slugs

    first_label = app_hostname.split(".")[0].strip().lower()
    if first_label:
        reserved_slugs.add(first_label)

    return reserved_slugs


def _user_to_read(user: User, approved_domains: set[str]) -> UserRead:
    """Convert a User model to UserRead schema with computed is_internal."""
    domain = user.email.split("@")[-1].lower()
    is_internal = domain in approved_domains
    return UserRead(
        id=user.id,
        email=user.email,
        name=user.name,
        status=user.status,
        is_admin=user.is_admin,
        is_seeded=user.is_seeded,
        is_internal=is_internal,
        notify_new_registrations=user.notify_new_registrations,
        notify_all_registrations=user.notify_all_registrations,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def _find_registration_ip(db: AsyncSession, email: str) -> str | None:
    """Find the earliest known registration IP for a user."""
    event_groups = (
        (
            "auth.identity.pending_approval",
            "auth.registration.pending_verified",
            "auth.signin.otp_success",
            "auth.signin.passkey",
            "auth.signin.google",
            "auth.signin.github",
        ),
        (
            "auth.signin.otp_sent",
            "auth.signin.failed",
        ),
    )

    for event_types in event_groups:
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.actor_email == email,
                AuditLog.ip_address.is_not(None),
                AuditLog.event_type.in_(event_types),
            )
            .order_by(AuditLog.timestamp.asc())
            .limit(1)
        )
        result = await db.execute(stmt)
        audit_log = result.scalar_one_or_none()
        if audit_log:
            return audit_log.ip_address

    return None


# ============================================================================
# Domain Management Endpoints
# ============================================================================


@router.get(
    "/domains",
    response_model=DomainList,
    summary="List approved domains",
    description="List all approved email domains for internal users. Admin only.",
)
async def list_domains(admin: AdminUser, db: DbSession) -> DomainList:
    count_stmt = select(func.count(ApprovedDomain.id))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = select(ApprovedDomain).order_by(ApprovedDomain.domain)
    result = await db.execute(stmt)
    domains = result.scalars().all()

    return DomainList(
        domains=[
            DomainRead(
                id=str(d.id),
                domain=d.domain,
                created_at=d.created_at,
                created_by=d.created_by,
            )
            for d in domains
        ],
        total=total,
    )


@router.post(
    "/domains",
    response_model=DomainRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Domain added"},
        400: {"model": ErrorResponse, "description": "Domain already exists"},
    },
    summary="Add approved domain",
    description="Add a new approved email domain. Users from this domain are internal. Admin only.",
)
async def add_domain(request: DomainCreate, admin: AdminUser, db: DbSession) -> DomainRead:
    import re

    domain = request.domain.lower().strip()

    # Validate domain format with regex
    domain_regex = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$")
    if not domain or not domain_regex.match(domain):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid domain format. Example: example.com",
        )

    stmt = select(ApprovedDomain).where(ApprovedDomain.domain == domain)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Domain '{domain}' already exists",
        )

    approved_domain = ApprovedDomain(
        domain=domain,
        created_by=admin.email,
    )
    db.add(approved_domain)
    await db.flush()
    await db.refresh(approved_domain)

    return DomainRead(
        id=str(approved_domain.id),
        domain=approved_domain.domain,
        created_at=approved_domain.created_at,
        created_by=approved_domain.created_by,
    )


@router.delete(
    "/domains/{domain}",
    response_model=MessageResponse,
    responses={
        200: {"description": "Domain removed"},
        404: {"model": ErrorResponse, "description": "Domain not found"},
    },
    summary="Remove approved domain",
    description="Remove an approved email domain. Users from this domain become external.",
)
async def remove_domain(domain: str, admin: AdminUser, db: DbSession) -> MessageResponse:
    domain = domain.lower().strip()

    stmt = select(ApprovedDomain).where(ApprovedDomain.domain == domain)
    result = await db.execute(stmt)
    approved_domain = result.scalar_one_or_none()

    if not approved_domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Domain '{domain}' not found",
        )

    await db.delete(approved_domain)
    await db.flush()

    return MessageResponse(message=f"Domain '{domain}' removed successfully")


# ============================================================================
# User Management Endpoints
# ============================================================================


@router.get(
    "/users/lookup",
    response_model=UserLookupResponse,
    summary="Look up a user by email",
    description="Check whether a user already exists for the given email. Admin only.",
)
async def lookup_user_by_email(
    _admin: AdminUser,
    db: DbSession,
    email: str,
) -> UserLookupResponse:
    normalized_email = email.lower().strip()

    stmt = select(User).where(User.email == normalized_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return UserLookupResponse(exists=False, user=None)

    approved_domains = await _get_approved_domains_set(db)
    return UserLookupResponse(exists=True, user=_user_to_read(user, approved_domains))


@router.get(
    "/users",
    response_model=UserList,
    summary="List all users",
    description="List all users with pagination. Admin only.",
)
async def list_users(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: UserStatus | None = Query(None, description="Filter by status"),
    include_rejected: bool = Query(False, description="Include rejected users"),
) -> UserList:
    offset = (page - 1) * page_size

    count_stmt = select(func.count(User.id))
    query_stmt = select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)

    if status_filter:
        count_stmt = count_stmt.where(User.status == status_filter)
        query_stmt = query_stmt.where(User.status == status_filter)
    elif not include_rejected:
        # By default, hide rejected users (they're treated as banned)
        count_stmt = count_stmt.where(User.status != UserStatus.REJECTED)
        query_stmt = query_stmt.where(User.status != UserStatus.REJECTED)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    result = await db.execute(query_stmt)
    users = result.scalars().all()

    # Get approved domains for is_internal computation
    approved_domains = await _get_approved_domains_set(db)

    return UserList(
        users=[_user_to_read(u, approved_domains) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/users/pending",
    response_model=PendingUserList,
    summary="List pending registrations",
    description="List all users with pending registration status. Admin only.",
)
async def list_pending_users(admin: AdminUser, db: DbSession) -> PendingUserList:
    count_stmt = select(func.count(User.id)).where(User.status == UserStatus.PENDING)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = select(User).where(User.status == UserStatus.PENDING).order_by(User.created_at.asc())
    result = await db.execute(stmt)
    users = result.scalars().all()

    # Get approved domains for is_internal computation
    approved_domains = await _get_approved_domains_set(db)

    return PendingUserList(
        users=[_user_to_read(u, approved_domains) for u in users],
        total=total,
    )


@router.get(
    "/users/{user_id}",
    response_model=UserRead,
    responses={
        200: {"description": "User details"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Get user details",
    description="Get details of a specific user. Admin only.",
)
async def get_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> UserRead:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    approved_domains = await _get_approved_domains_set(db)
    return _user_to_read(user, approved_domains)


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User created"},
        400: {"model": ErrorResponse, "description": "Email already registered"},
    },
    summary="Create user",
    description="Create a new user directly. Admin only.",
)
async def create_user(request: AdminCreateUser, admin: AdminUser, db: DbSession) -> UserRead:
    email = request.email.lower()

    # Check if email is suppressed (bounced/complained)
    email_service = EmailService(db=db)
    if await email_service.is_suppressed(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email address is blocked due to previous delivery issues",
        )

    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = User(
        email=email,
        status=UserStatus.APPROVED if request.auto_approve else UserStatus.PENDING,
        is_admin=request.is_admin,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # Only send welcome email to super admins
    # Regular users will only receive emails when granted access to specific apps
    if request.auto_approve and request.is_admin:
        await email_service.send_super_admin_welcome(email, admin.email)

    approved_domains = await _get_approved_domains_set(db)
    return _user_to_read(user, approved_domains)


@router.patch(
    "/users/{user_id}",
    response_model=UserRead,
    responses={
        200: {"description": "User updated"},
        404: {"model": ErrorResponse, "description": "User not found"},
        400: {"model": ErrorResponse, "description": "Cannot modify yourself"},
    },
    summary="Update user",
    description="Update a user's status or admin flag. Admin only.",
)
async def update_user(
    user_id: uuid.UUID,
    request: AdminUpdateUser,
    admin: AdminUser,
    db: DbSession,
) -> UserRead:
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own account through this endpoint",
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    was_pending = user.status == UserStatus.PENDING

    if request.status is not None:
        user.status = request.status

    if request.is_admin is not None:
        user.is_admin = request.is_admin

    if request.notify_new_registrations is not None:
        user.notify_new_registrations = request.notify_new_registrations

    if request.notify_all_registrations is not None:
        user.notify_all_registrations = request.notify_all_registrations

    await db.flush()
    await db.refresh(user)

    if was_pending and user.status == UserStatus.APPROVED:
        email_service = EmailService(db=db)
        await email_service.send_registration_approved(user.email)

    approved_domains = await _get_approved_domains_set(db)
    return _user_to_read(user, approved_domains)


@router.post(
    "/users/{user_id}/approve",
    response_model=UserRead,
    responses={
        200: {"description": "User approved"},
        404: {"model": ErrorResponse, "description": "User not found"},
        400: {"model": ErrorResponse, "description": "User not pending"},
    },
    summary="Approve registration",
    description="Approve a pending user registration. Admin only.",
)
async def approve_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> UserRead:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.status != UserStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is already {user.status.value}",
        )

    user.status = UserStatus.APPROVED
    await db.flush()
    await db.refresh(user)

    email_service = EmailService(db=db)
    await email_service.send_registration_approved(user.email)

    approved_domains = await _get_approved_domains_set(db)
    return _user_to_read(user, approved_domains)


@router.post(
    "/users/{user_id}/reject",
    response_model=UserRead,
    responses={
        200: {"description": "User rejected"},
        404: {"model": ErrorResponse, "description": "User not found"},
        400: {"model": ErrorResponse, "description": "User not pending"},
    },
    summary="Reject registration",
    description="Reject a pending user registration. Admin only.",
)
async def reject_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> UserRead:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.status != UserStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User is already {user.status.value}",
        )

    user.status = UserStatus.REJECTED
    approved_domains = await _get_approved_domains_set(db)

    # Cross-ban: Ban the email
    email_ban = BannedEmail(
        email=user.email.lower(),
        is_pattern=False,
        reason=BanReason.REJECTED_USER.value,
        details=f"User rejected by {admin.email}",
        banned_by=admin.email,
        expires_at=None,  # Permanent
        is_active=True,
    )
    db.add(email_ban)

    # Cross-ban: Find the IP used during registration and ban it.
    registration_ip = await _find_registration_ip(db, user.email)

    if registration_ip:
        # Check if the IP has been used by any approved domain user (don't ban)
        user_domain = user.email.split("@")[-1].lower()
        is_user_from_approved_domain = user_domain in approved_domains

        if not is_user_from_approved_domain:
            # Check if any approved user has used this IP
            ip_logs_stmt = (
                select(AuditLog)
                .where(
                    AuditLog.ip_address == registration_ip,
                )
                .limit(50)
            )
            ip_logs_result = await db.execute(ip_logs_stmt)
            ip_logs = ip_logs_result.scalars().all()

            has_approved_domain_user = False
            for log in ip_logs:
                if log.actor_email:
                    log_domain = log.actor_email.split("@")[-1].lower()
                    if log_domain in approved_domains:
                        has_approved_domain_user = True
                        break

            if not has_approved_domain_user:
                # Ban the IP
                ip_ban = BannedIP(
                    ip_address=registration_ip,
                    reason=BanReason.REJECTED_USER.value,
                    details=f"Associated with rejected user: {user.email}",
                    banned_by=admin.email,
                    expires_at=None,  # Permanent
                    is_active=True,
                    associated_email=user.email.lower(),
                )
                db.add(ip_ban)

                # Update email ban with associated IP
                email_ban.associated_ip = registration_ip

                # Log the IP ban
                ip_ban_audit = AuditLog(
                    event_type="security.ip.banned.cross",
                    actor_email=admin.email,
                    details=json.dumps(
                        {
                            "ip_address": registration_ip,
                            "reason": BanReason.REJECTED_USER.value,
                            "associated_email": user.email,
                        }
                    ),
                )
                db.add(ip_ban_audit)

    # Log the email ban
    email_ban_audit = AuditLog(
        event_type="security.email.banned.rejected",
        actor_email=admin.email,
        details=json.dumps(
            {
                "email": user.email,
                "reason": BanReason.REJECTED_USER.value,
                "associated_ip": registration_ip,
            }
        ),
    )
    db.add(email_ban_audit)

    await db.flush()
    await db.refresh(user)

    return _user_to_read(user, approved_domains)


@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse,
    responses={
        200: {"description": "User deleted"},
        404: {"model": ErrorResponse, "description": "User not found"},
        400: {"model": ErrorResponse, "description": "Cannot delete yourself"},
    },
    summary="Delete user",
    description="Delete a user and all their associated data. Admin only.",
)
async def delete_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> MessageResponse:
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.delete(user)
    await db.flush()

    return MessageResponse(message="User deleted successfully")


# ============================================================================
# App Management Endpoints
# ============================================================================


@router.get(
    "/apps",
    response_model=AppList,
    summary="List all apps",
    description="List all registered apps. Admin only.",
)
async def list_apps(admin: AdminUser, db: DbSession) -> AppList:
    count_stmt = select(func.count(App.id))
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = select(App).order_by(App.created_at.desc())
    result = await db.execute(stmt)
    apps = result.scalars().all()

    return AppList(
        apps=[
            AppRead(
                id=str(a.id),
                slug=a.slug,
                name=a.name,
                description=a.description,
                app_url=a.app_url,
                roles=a.roles,
                created_at=a.created_at,
            )
            for a in apps
        ],
        total=total,
    )


@router.post(
    "/apps",
    response_model=AppRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "App created"},
        400: {"model": ErrorResponse, "description": "App slug already exists"},
    },
    summary="Create app",
    description="Register a new app. Admin only.",
)
async def create_app(request: AppCreate, admin: AdminUser, db: DbSession) -> AppRead:
    if request.slug in _get_reserved_app_slugs():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"App slug '{request.slug}' is reserved for the auth host",
        )

    stmt = select(App).where(App.slug == request.slug)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"App with slug '{request.slug}' already exists",
        )

    app = App(
        slug=request.slug,
        name=request.name,
        description=request.description,
        app_url=request.app_url,
        roles=request.roles,
    )
    db.add(app)
    await db.flush()
    await db.refresh(app)

    return AppRead(
        id=str(app.id),
        slug=app.slug,
        name=app.name,
        description=app.description,
        app_url=app.app_url,
        roles=app.roles,
        created_at=app.created_at,
    )


@router.get(
    "/apps/{slug}",
    response_model=AppDetail,
    responses={
        200: {"description": "App details with users"},
        404: {"model": ErrorResponse, "description": "App not found"},
    },
    summary="Get app details",
    description="Get app details including users with explicit access. Admin only.",
)
async def get_app(slug: str, admin: AdminUser, db: DbSession) -> AppDetail:
    stmt = select(App).where(App.slug == slug)
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{slug}' not found",
        )

    # Get users with explicit access (external users granted access)
    access_stmt = (
        select(UserAppAccess, User)
        .join(User, UserAppAccess.user_id == User.id)
        .where(UserAppAccess.app_id == app.id)
        .order_by(UserAppAccess.granted_at.desc())
    )
    access_result = await db.execute(access_stmt)
    access_rows = access_result.all()

    users = [
        AppUserAccess(
            email=user.email,
            role=access.role,
            granted_at=access.granted_at,
            granted_by=access.granted_by,
        )
        for access, user in access_rows
    ]

    return AppDetail(
        id=str(app.id),
        slug=app.slug,
        name=app.name,
        description=app.description,
        app_url=app.app_url,
        roles=app.roles,
        created_at=app.created_at,
        users=users,
    )


@router.delete(
    "/apps/{slug}",
    response_model=MessageResponse,
    responses={
        200: {"description": "App deleted"},
        404: {"model": ErrorResponse, "description": "App not found"},
    },
    summary="Delete app",
    description="Delete an app and all associated access grants. Admin only.",
)
async def delete_app(slug: str, admin: AdminUser, db: DbSession) -> MessageResponse:
    stmt = select(App).where(App.slug == slug)
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{slug}' not found",
        )

    await db.delete(app)
    await db.flush()

    return MessageResponse(message=f"App '{slug}' deleted successfully")


@router.patch(
    "/apps/{slug}",
    response_model=AppRead,
    responses={
        200: {"description": "App updated"},
        404: {"model": ErrorResponse, "description": "App not found"},
    },
    summary="Update app",
    description="Update an app's details. Admin only.",
)
async def update_app(slug: str, request: AppUpdate, admin: AdminUser, db: DbSession) -> AppRead:
    stmt = select(App).where(App.slug == slug)
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{slug}' not found",
        )

    if request.name is not None:
        app.name = request.name
    if request.description is not None:
        app.description = request.description
    if request.app_url is not None:
        app.app_url = request.app_url
    if request.roles is not None:
        app.roles = request.roles

    await db.flush()
    await db.refresh(app)

    return AppRead(
        id=str(app.id),
        slug=app.slug,
        name=app.name,
        description=app.description,
        app_url=app.app_url,
        roles=app.roles,
        created_at=app.created_at,
    )


@router.get(
    "/apps/{slug}/users",
    response_model=list[AppUserAccess],
    responses={
        200: {"description": "Users with explicit access"},
        404: {"model": ErrorResponse, "description": "App not found"},
    },
    summary="List app users",
    description="List all users with explicit access to an app (external users). Admin only.",
)
async def list_app_users(slug: str, admin: AdminUser, db: DbSession) -> list[AppUserAccess]:
    stmt = select(App).where(App.slug == slug)
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{slug}' not found",
        )

    access_stmt = (
        select(UserAppAccess, User)
        .join(User, UserAppAccess.user_id == User.id)
        .where(UserAppAccess.app_id == app.id)
        .order_by(UserAppAccess.granted_at.desc())
    )
    access_result = await db.execute(access_stmt)
    access_rows = access_result.all()

    return [
        AppUserAccess(
            email=user.email,
            role=access.role,
            granted_at=access.granted_at,
            granted_by=access.granted_by,
        )
        for access, user in access_rows
    ]


@router.post(
    "/apps/{slug}/grant",
    response_model=MessageResponse,
    responses={
        200: {"description": "Access granted"},
        404: {"model": ErrorResponse, "description": "App or user not found"},
        400: {"model": ErrorResponse, "description": "User already has access"},
    },
    summary="Grant app access",
    description="Grant a user explicit access to an app with optional role. Admin only.",
)
async def grant_app_access(
    slug: str, request: GrantAccess, admin: AdminUser, db: DbSession
) -> MessageResponse:
    # Find app
    app_stmt = select(App).where(App.slug == slug)
    app_result = await db.execute(app_stmt)
    app = app_result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{slug}' not found",
        )

    # Find user
    user_stmt = select(User).where(User.email == request.email.lower())
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{request.email}' not found",
        )

    # Check existing access
    access_stmt = select(UserAppAccess).where(
        UserAppAccess.user_id == user.id,
        UserAppAccess.app_id == app.id,
    )
    access_result = await db.execute(access_stmt)
    existing = access_result.scalar_one_or_none()

    if existing:
        # Update role if different
        if existing.role != request.role:
            existing.role = request.role
            existing.granted_by = admin.email
            await db.flush()
            return MessageResponse(message=f"Updated role for '{request.email}' on '{slug}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{request.email}' already has access to '{slug}'",
        )

    # Grant access
    access = UserAppAccess(
        user_id=user.id,
        app_id=app.id,
        role=request.role,
        granted_by=admin.email,
    )
    db.add(access)
    await db.flush()

    # Send email notification
    email_service = EmailService(db=db)
    await email_service.send_app_access_granted(
        to_email=user.email,
        app_name=app.name,
        app_description=app.description,
        app_url=app.app_url,
        granted_by=admin.email,
    )

    role_msg = f" with role '{request.role}'" if request.role else ""
    return MessageResponse(message=f"Granted access to '{slug}' for '{request.email}'{role_msg}")


@router.delete(
    "/apps/{slug}/revoke",
    response_model=MessageResponse,
    responses={
        200: {"description": "Access revoked"},
        404: {"model": ErrorResponse, "description": "App, user, or access not found"},
    },
    summary="Revoke app access",
    description="Revoke a user's explicit access to an app. Admin only.",
)
async def revoke_app_access(
    slug: str,
    email: str = Query(..., description="Email of user to revoke access"),
    admin: AdminUser = None,
    db: DbSession = None,
) -> MessageResponse:
    email = email.lower()

    # Find app
    app_stmt = select(App).where(App.slug == slug)
    app_result = await db.execute(app_stmt)
    app = app_result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{slug}' not found",
        )

    # Find user
    user_stmt = select(User).where(User.email == email)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{email}' not found",
        )

    # Find and delete access
    access_stmt = select(UserAppAccess).where(
        UserAppAccess.user_id == user.id,
        UserAppAccess.app_id == app.id,
    )
    access_result = await db.execute(access_stmt)
    access = access_result.scalar_one_or_none()

    if not access:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{email}' does not have explicit access to '{slug}'",
        )

    await db.delete(access)
    await db.flush()

    return MessageResponse(message=f"Revoked access to '{slug}' for '{email}'")


@router.post(
    "/users/grant-bulk",
    response_model=MessageResponse,
    responses={
        200: {"description": "Access granted to multiple apps"},
        400: {"model": ErrorResponse, "description": "Invalid emails or app slugs"},
    },
    summary="Bulk grant access",
    description="Grant multiple users access to multiple apps at once. Admin only.",
)
async def bulk_grant_access(
    request: BulkGrantAccess, admin: AdminUser, db: DbSession
) -> MessageResponse:
    # Find all users
    users_stmt = select(User).where(User.email.in_([e.lower() for e in request.emails]))
    users_result = await db.execute(users_stmt)
    users = {u.email: u for u in users_result.scalars().all()}

    missing_users = [e for e in request.emails if e.lower() not in users]
    if missing_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Users not found: {', '.join(missing_users)}",
        )

    # Find all apps
    apps_stmt = select(App).where(App.slug.in_(request.app_slugs))
    apps_result = await db.execute(apps_stmt)
    apps = {a.slug: a for a in apps_result.scalars().all()}

    missing_apps = [s for s in request.app_slugs if s not in apps]
    if missing_apps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apps not found: {', '.join(missing_apps)}",
        )

    # Grant access to each user-app pair
    grants_created = 0
    email_service = EmailService(db=db)

    for email in request.emails:
        user = users[email.lower()]
        for app_slug in request.app_slugs:
            app = apps[app_slug]

            # Check if access already exists
            access_stmt = select(UserAppAccess).where(
                UserAppAccess.user_id == user.id,
                UserAppAccess.app_id == app.id,
            )
            access_result = await db.execute(access_stmt)
            existing = access_result.scalar_one_or_none()

            if not existing:
                access = UserAppAccess(
                    user_id=user.id,
                    app_id=app.id,
                    role=request.role,
                    granted_by=admin.email,
                )
                db.add(access)
                grants_created += 1

                # Send email notification
                await email_service.send_app_access_granted(
                    to_email=user.email,
                    app_name=app.name,
                    app_description=app.description,
                    app_url=app.app_url,
                    granted_by=admin.email,
                )

    await db.flush()

    return MessageResponse(
        message=f"Created {grants_created} access grant(s) for {len(request.emails)} user(s) "
        f"across {len(request.app_slugs)} app(s)"
    )


# ============================================================================
# Audit Log Endpoints
# ============================================================================


@router.get(
    "/audit-logs",
    response_model=AuditLogList,
    summary="List audit logs",
    description="Query audit logs with optional filters. Admin only.",
)
async def list_audit_logs(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    event_type: str | None = Query(None, description="Filter by event type prefix"),
    actor_email: str | None = Query(None, description="Filter by actor email"),
    target_type: str | None = Query(None, description="Filter by target type"),
    since: datetime | None = Query(None, description="Filter events after this timestamp"),
    until: datetime | None = Query(None, description="Filter events before this timestamp"),
) -> AuditLogList:
    """Query audit logs with pagination and filters."""
    # Build query
    stmt = select(AuditLog)

    if event_type:
        stmt = stmt.where(AuditLog.event_type.startswith(event_type))
    if actor_email:
        stmt = stmt.where(AuditLog.actor_email == actor_email.lower())
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    if since:
        stmt = stmt.where(AuditLog.timestamp >= since)
    if until:
        stmt = stmt.where(AuditLog.timestamp <= until)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Paginate and order
    stmt = stmt.order_by(AuditLog.timestamp.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    logs = result.scalars().all()

    return AuditLogList(
        logs=[
            AuditLogRead(
                id=log.id,
                timestamp=log.timestamp,
                actor_id=log.actor_id,
                actor_email=log.actor_email,
                event_type=log.event_type,
                target_type=log.target_type,
                target_id=log.target_id,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                details=json.loads(log.details) if log.details else None,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================================================
# Branding Endpoints
# ============================================================================


async def _get_or_create_branding(db: AsyncSession) -> Branding:
    """Get the branding record, creating it if it doesn't exist."""
    stmt = select(Branding).where(Branding.id == 1)
    result = await db.execute(stmt)
    branding = result.scalar_one_or_none()

    if not branding:
        branding = Branding(id=1, accent_color="ink")
        db.add(branding)
        await db.flush()
        await db.refresh(branding)

    return branding


@router.get(
    "/branding",
    response_model=BrandingReadAdmin,
    summary="Get branding settings",
    description="Get current branding settings including metadata. Admin only.",
)
async def get_branding(admin: AdminUser, db: DbSession) -> BrandingReadAdmin:
    branding = await _get_or_create_branding(db)
    return BrandingReadAdmin(
        logo_url=branding.logo_url,
        logo_square_url=branding.logo_square_url,
        favicon_url=branding.favicon_url,
        accent_color=branding.accent_color,
        accent_hex=branding.accent_hex,
        updated_at=branding.updated_at,
        updated_by=branding.updated_by,
    )


@router.put(
    "/branding",
    response_model=BrandingReadAdmin,
    summary="Update branding settings",
    description="Update logo URLs and accent color. Admin only.",
)
async def update_branding(
    request: BrandingUpdate, admin: AdminUser, db: DbSession
) -> BrandingReadAdmin:
    branding = await _get_or_create_branding(db)

    # Handle URL fields: empty string means clear, None means don't change
    if request.logo_url is not None:
        branding.logo_url = request.logo_url if request.logo_url else None
    if request.logo_square_url is not None:
        branding.logo_square_url = request.logo_square_url if request.logo_square_url else None
    if request.favicon_url is not None:
        branding.favicon_url = request.favicon_url if request.favicon_url else None
    if request.accent_color is not None:
        branding.accent_color = request.accent_color

    branding.updated_at = datetime.utcnow()
    branding.updated_by = admin.email

    await db.flush()
    await db.refresh(branding)

    return BrandingReadAdmin(
        logo_url=branding.logo_url,
        logo_square_url=branding.logo_square_url,
        favicon_url=branding.favicon_url,
        accent_color=branding.accent_color,
        accent_hex=branding.accent_hex,
        updated_at=branding.updated_at,
        updated_by=branding.updated_by,
    )


@router.get(
    "/branding/presets",
    response_model=AccentPresetsResponse,
    summary="Get accent color presets",
    description="Get available accent color presets. Admin only.",
)
async def get_accent_presets(admin: AdminUser) -> AccentPresetsResponse:
    return AccentPresetsResponse.from_presets()


# ============================================================================
# Deployment Config Endpoint
# ============================================================================


@router.get(
    "/config",
    response_model=DeploymentConfig,
    summary="Get deployment configuration",
    description="Get deployment config for Nginx setup instructions. Admin only.",
)
async def get_deployment_config(admin: AdminUser) -> DeploymentConfig:
    settings = get_settings()
    return DeploymentConfig(
        cookie_domain=settings.cookie_domain,
        app_url=settings.app_url,
    )
