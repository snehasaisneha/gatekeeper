import json
import uuid
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.api.deps import AdminUser, CurrentUser, CurrentUserOptional, DbSession
from gatekeeper.config import get_settings
from gatekeeper.models.app import App, AppApiKey, UserAppAccess
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
    UserInvestigationAppAccess,
    UserInvestigationRead,
    UserList,
    UserLookupResponse,
    UserSessionRead,
)
from gatekeeper.schemas.app import (
    AppAdminScope,
    AppApiKeyCreate,
    AppApiKeyCreateResponse,
    AppApiKeyRead,
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
from gatekeeper.services.app_api_keys import AppApiKeyService
from gatekeeper.services.audit import AuditService, EventType
from gatekeeper.services.email import EmailService
from gatekeeper.services.session import SessionService

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


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _normalize_role(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _role_grants_app_admin(app: App, role: str | None) -> bool:
    normalized_role = _normalize_role(role)
    if not normalized_role:
        return False
    admin_roles = {candidate.lower() for candidate in _split_csv(app.admin_roles)}
    return normalized_role.lower() in admin_roles


async def _sync_app_admin_grants(db: AsyncSession, app: App) -> None:
    stmt = select(UserAppAccess).where(UserAppAccess.app_id == app.id)
    result = await db.execute(stmt)
    for access in result.scalars().all():
        access.is_app_admin = _role_grants_app_admin(app, access.role)
    await db.flush()


def _validate_admin_roles(roles: str, admin_roles: str) -> None:
    role_set = {role.lower() for role in _split_csv(roles)}
    admin_role_set = {role.lower() for role in _split_csv(admin_roles)}
    if not admin_role_set.issubset(role_set):
        missing = sorted(admin_role_set - role_set)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Admin roles must also exist in the app role list: " + ", ".join(missing)),
        )


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
        app_admin_apps=[],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def _get_user_app_admin_scopes(db: AsyncSession, user: User) -> list[AppAdminScope]:
    stmt = (
        select(UserAppAccess, App)
        .join(App, App.id == UserAppAccess.app_id)
        .where(
            UserAppAccess.user_id == user.id,
            UserAppAccess.is_app_admin == True,  # noqa: E712
        )
        .order_by(App.name.asc())
    )
    result = await db.execute(stmt)
    return [
        AppAdminScope(
            app_id=str(app.id),
            app_slug=app.slug,
            app_name=app.name,
            app_description=app.description,
            app_url=app.app_url,
        )
        for _, app in result.all()
    ]


async def _user_to_read_with_scopes(
    db: AsyncSession, user: User, approved_domains: set[str]
) -> UserRead:
    return _user_to_read(user, approved_domains).model_copy(
        update={"app_admin_apps": await _get_user_app_admin_scopes(db, user)}
    )


def _extract_api_key(
    authorization: str | None,
    x_api_key: str | None,
) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def _get_app_or_404(db: AsyncSession, slug: str) -> App:
    stmt = select(App).where(App.slug == slug)
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{slug}' not found",
        )
    return app


async def _user_can_admin_app(db: AsyncSession, user: User, app_id: uuid.UUID) -> bool:
    if user.is_admin:
        return True
    stmt = select(UserAppAccess).where(
        UserAppAccess.user_id == user.id,
        UserAppAccess.app_id == app_id,
        UserAppAccess.is_app_admin == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _resolve_app_actor(
    db: AsyncSession,
    app: App,
    current_user: User | None,
    authorization: str | None,
    x_api_key: str | None,
) -> dict[str, object]:
    raw_api_key = _extract_api_key(authorization, x_api_key)
    if raw_api_key:
        api_key = await AppApiKeyService(db).resolve_key(raw_api_key)
        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        if api_key.app_id != app.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key is not valid for this app",
            )
        return {
            "kind": "api_key",
            "user": None,
            "api_key": api_key,
            "actor_id": None,
            "actor_email": f"api-key:{api_key.name}",
            "changes": {
                "auth_method": "api_key",
                "api_key_id": str(api_key.id),
                "api_key_name": api_key.name,
            },
        }

    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if not await _user_can_admin_app(db, current_user, app.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for this app",
        )

    return {
        "kind": "user",
        "user": current_user,
        "api_key": None,
        "actor_id": current_user.id,
        "actor_email": current_user.email,
        "changes": {"auth_method": "session"},
    }


async def _log_actor_event(
    db: AsyncSession,
    *,
    event_type: str,
    actor: dict[str, object],
    target_type: str,
    target_id: str,
    details: dict[str, object] | None = None,
) -> None:
    audit_service = AuditService(db)
    merged_details = dict(actor["changes"])  # type: ignore[arg-type]
    if details:
        merged_details.update(details)
    await audit_service.log(
        event_type,
        actor=actor["user"] if actor["kind"] == "user" else None,  # type: ignore[arg-type]
        actor_id=actor["actor_id"],  # type: ignore[arg-type]
        actor_email=actor["actor_email"],  # type: ignore[arg-type]
        target_type=target_type,
        target_id=target_id,
        details=merged_details,
    )


def _app_user_access_to_read(access: UserAppAccess, user: User) -> AppUserAccess:
    return AppUserAccess(
        user_id=str(user.id),
        email=user.email,
        role=access.role,
        is_app_admin=access.is_app_admin,
        granted_at=access.granted_at,
        granted_by=access.granted_by,
    )


def _app_api_key_to_read(api_key: AppApiKey) -> AppApiKeyRead:
    return AppApiKeyRead(
        id=str(api_key.id),
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        created_by_email=api_key.created_by_email,
        last_used_at=api_key.last_used_at,
        revoked_at=api_key.revoked_at,
        revoked_by=api_key.revoked_by,
        created_at=api_key.created_at,
    )


def _audit_log_to_read(log: AuditLog) -> AuditLogRead:
    return AuditLogRead(
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


def _session_to_read(session) -> UserSessionRead:
    return UserSessionRead(
        id=session.id,
        auth_method=session.auth_method,
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        created_at=session.created_at,
        last_seen_at=session.last_seen_at,
        expires_at=session.expires_at,
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
    return UserLookupResponse(
        exists=True, user=await _user_to_read_with_scopes(db, user, approved_domains)
    )


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
        users=[await _user_to_read_with_scopes(db, u, approved_domains) for u in users],
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
        users=[await _user_to_read_with_scopes(db, u, approved_domains) for u in users],
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
    return await _user_to_read_with_scopes(db, user, approved_domains)


@router.get(
    "/users/{user_id}/investigation",
    response_model=UserInvestigationRead,
    responses={
        200: {"description": "Expanded user investigation details"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Get user investigation details",
    description="Get app access, recent activity, active sessions, and active bans for a user.",
)
async def get_user_investigation(
    user_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
    audit_limit: int = Query(
        20, ge=1, le=100, description="Number of recent audit events to return"
    ),
) -> UserInvestigationRead:
    user_stmt = select(User).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    approved_domains = await _get_approved_domains_set(db)

    app_access_stmt = (
        select(UserAppAccess, App)
        .join(App, App.id == UserAppAccess.app_id)
        .where(UserAppAccess.user_id == user.id)
        .order_by(UserAppAccess.granted_at.desc())
    )
    app_access_result = await db.execute(app_access_stmt)
    app_access = [
        UserInvestigationAppAccess(
            app_slug=app.slug,
            app_name=app.name,
            app_description=app.description,
            app_url=app.app_url,
            role=access.role,
            granted_at=access.granted_at,
            granted_by=access.granted_by,
        )
        for access, app in app_access_result.all()
    ]

    session_service = SessionService(db)
    sessions = await session_service.list_for_user(user.id)
    active_sessions = [_session_to_read(session) for session in sessions]

    audit_stmt = (
        select(AuditLog)
        .where(
            or_(
                AuditLog.actor_id == user.id,
                AuditLog.actor_email == user.email,
                and_(AuditLog.target_type == "user", AuditLog.target_id == str(user.id)),
            )
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(audit_limit)
    )
    audit_result = await db.execute(audit_stmt)
    recent_audit_logs = [_audit_log_to_read(log) for log in audit_result.scalars().all()]

    recent_ip_addresses: list[str] = []
    for log in recent_audit_logs:
        if log.ip_address and log.ip_address not in recent_ip_addresses:
            recent_ip_addresses.append(log.ip_address)

    now = datetime.utcnow()
    active_ip_ban_conditions = [
        BannedIP.is_active == True,  # noqa: E712
        or_(BannedIP.expires_at.is_(None), BannedIP.expires_at > now),
    ]
    if recent_ip_addresses:
        active_ip_ban_conditions.append(
            or_(
                BannedIP.associated_email == user.email,
                BannedIP.ip_address.in_(recent_ip_addresses),
            )
        )
    else:
        active_ip_ban_conditions.append(BannedIP.associated_email == user.email)

    active_ip_bans_stmt = (
        select(BannedIP).where(and_(*active_ip_ban_conditions)).order_by(BannedIP.banned_at.desc())
    )
    active_ip_bans_result = await db.execute(active_ip_bans_stmt)
    active_ip_bans = list(active_ip_bans_result.scalars().all())

    active_email_bans_stmt = (
        select(BannedEmail)
        .where(
            BannedEmail.is_active == True,  # noqa: E712
            or_(BannedEmail.expires_at.is_(None), BannedEmail.expires_at > now),
            BannedEmail.email == user.email,
            BannedEmail.is_pattern == False,  # noqa: E712
        )
        .order_by(BannedEmail.banned_at.desc())
    )
    active_email_bans_result = await db.execute(active_email_bans_stmt)
    active_email_bans = list(active_email_bans_result.scalars().all())

    last_auth_method = None
    last_seen_at = active_sessions[0].last_seen_at if active_sessions else None
    for log in recent_audit_logs:
        if log.event_type in {
            EventType.AUTH_SIGNIN_OTP_SUCCESS,
            EventType.AUTH_SIGNIN_GOOGLE,
            EventType.AUTH_SIGNIN_GITHUB,
            EventType.AUTH_SIGNIN_PASSKEY,
        }:
            if log.details and isinstance(log.details.get("method"), str):
                last_auth_method = log.details["method"]
            else:
                last_auth_method = log.event_type.rsplit(".", 1)[-1]
            if last_seen_at is None or log.timestamp > last_seen_at:
                last_seen_at = log.timestamp
            break

    return UserInvestigationRead(
        user=await _user_to_read_with_scopes(db, user, approved_domains),
        app_access=app_access,
        active_sessions=active_sessions,
        recent_audit_logs=recent_audit_logs,
        active_ip_bans=active_ip_bans,
        active_email_bans=active_email_bans,
        recent_ip_addresses=recent_ip_addresses,
        last_auth_method=last_auth_method,
        last_seen_at=last_seen_at,
    )


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
    return await _user_to_read_with_scopes(db, user, approved_domains)


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
    return await _user_to_read_with_scopes(db, user, approved_domains)


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
    return await _user_to_read_with_scopes(db, user, approved_domains)


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

    return await _user_to_read_with_scopes(db, user, approved_domains)


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


@router.delete(
    "/users/{user_id}/sessions/{session_id}",
    response_model=MessageResponse,
    responses={
        200: {"description": "Session revoked"},
        404: {"model": ErrorResponse, "description": "User or session not found"},
    },
    summary="Revoke a user session",
    description="Revoke a single active session for a user. Admin only.",
)
async def revoke_user_session(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
) -> MessageResponse:
    user_stmt = select(User).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    session_service = SessionService(db)
    deleted = await session_service.delete_session(session_id, user_id=user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    audit_service = AuditService(db)
    await audit_service.log_admin_action(
        EventType.AUTH_SESSION_REVOKED,
        admin,
        target_type="session",
        target_id=str(session_id),
        target_email=user.email,
        changes={"user_id": str(user.id)},
    )

    return MessageResponse(message="Session revoked successfully")


@router.post(
    "/users/{user_id}/sessions/revoke-all",
    response_model=MessageResponse,
    responses={
        200: {"description": "Sessions revoked"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
    summary="Revoke all user sessions",
    description="Revoke all active sessions for a user. Admin only.",
)
async def revoke_all_user_sessions(
    user_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
) -> MessageResponse:
    user_stmt = select(User).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    session_service = SessionService(db)
    deleted_count = await session_service.delete_all_for_user(user.id)

    audit_service = AuditService(db)
    await audit_service.log_admin_action(
        EventType.AUTH_SESSION_REVOKED,
        admin,
        target_type="user",
        target_id=str(user.id),
        target_email=user.email,
        changes={"revoked_session_count": deleted_count},
    )

    return MessageResponse(message=f"Revoked {deleted_count} session(s)")


# ============================================================================
# App Management Endpoints
# ============================================================================


@router.get(
    "/apps",
    response_model=AppList,
    summary="List all apps",
    description="List all registered apps visible to the current admin scope.",
)
async def list_apps(current_user: CurrentUser, db: DbSession) -> AppList:
    stmt = select(App)
    if not current_user.is_admin:
        scopes = await _get_user_app_admin_scopes(db, current_user)
        if not scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
        scoped_app_ids = select(UserAppAccess.app_id).where(
            UserAppAccess.user_id == current_user.id,
            UserAppAccess.is_app_admin == True,  # noqa: E712
        )
        stmt = stmt.where(App.id.in_(scoped_app_ids))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    result = await db.execute(stmt.order_by(App.created_at.desc()))
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
                admin_roles=a.admin_roles,
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
    _validate_admin_roles(request.roles, request.admin_roles)
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
        admin_roles=request.admin_roles,
    )
    db.add(app)
    await db.flush()
    await db.refresh(app)
    await _log_actor_event(
        db,
        event_type=EventType.ADMIN_APP_CREATED,
        actor={
            "kind": "user",
            "user": admin,
            "api_key": None,
            "actor_id": admin.id,
            "actor_email": admin.email,
            "changes": {"auth_method": "session"},
        },
        target_type="app",
        target_id=str(app.id),
        details={
            "app_slug": app.slug,
            "changes": {
                "name": app.name,
                "roles": app.roles,
                "admin_roles": app.admin_roles,
            },
        },
    )

    return AppRead(
        id=str(app.id),
        slug=app.slug,
        name=app.name,
        description=app.description,
        app_url=app.app_url,
        roles=app.roles,
        admin_roles=app.admin_roles,
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
async def get_app(
    slug: str,
    db: DbSession,
    current_user: CurrentUserOptional,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> AppDetail:
    app = await _get_app_or_404(db, slug)
    await _resolve_app_actor(db, app, current_user, authorization, x_api_key)

    # Get users with explicit access (external users granted access)
    access_stmt = (
        select(UserAppAccess, User)
        .join(User, UserAppAccess.user_id == User.id)
        .where(UserAppAccess.app_id == app.id)
        .order_by(UserAppAccess.granted_at.desc())
    )
    access_result = await db.execute(access_stmt)
    access_rows = access_result.all()

    users = [_app_user_access_to_read(access, user) for access, user in access_rows]

    api_keys_stmt = (
        select(AppApiKey).where(AppApiKey.app_id == app.id).order_by(AppApiKey.created_at.desc())
    )
    api_keys_result = await db.execute(api_keys_stmt)
    api_keys = [_app_api_key_to_read(api_key) for api_key in api_keys_result.scalars().all()]

    return AppDetail(
        id=str(app.id),
        slug=app.slug,
        name=app.name,
        description=app.description,
        app_url=app.app_url,
        roles=app.roles,
        admin_roles=app.admin_roles,
        created_at=app.created_at,
        users=users,
        api_keys=api_keys,
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
    await _log_actor_event(
        db,
        event_type=EventType.ADMIN_APP_DELETED,
        actor={
            "kind": "user",
            "user": admin,
            "api_key": None,
            "actor_id": admin.id,
            "actor_email": admin.email,
            "changes": {"auth_method": "session"},
        },
        target_type="app",
        target_id=str(app.id),
        details={"app_slug": app.slug},
    )

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
async def update_app(
    slug: str,
    request: AppUpdate,
    db: DbSession,
    current_user: CurrentUserOptional,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> AppRead:
    app = await _get_app_or_404(db, slug)
    actor = await _resolve_app_actor(db, app, current_user, authorization, x_api_key)
    next_roles = request.roles if request.roles is not None else app.roles
    next_admin_roles = request.admin_roles if request.admin_roles is not None else app.admin_roles
    _validate_admin_roles(next_roles, next_admin_roles)

    changes: dict[str, object] = {}

    if request.name is not None:
        changes["name"] = {"from": app.name, "to": request.name}
        app.name = request.name
    if request.description is not None:
        changes["description"] = {"from": app.description, "to": request.description}
        app.description = request.description
    if request.app_url is not None:
        changes["app_url"] = {"from": app.app_url, "to": request.app_url}
        app.app_url = request.app_url
    if request.roles is not None:
        changes["roles"] = {"from": app.roles, "to": request.roles}
        app.roles = request.roles
    if request.admin_roles is not None:
        changes["admin_roles"] = {"from": app.admin_roles, "to": request.admin_roles}
        app.admin_roles = request.admin_roles

    await db.flush()
    if request.roles is not None or request.admin_roles is not None:
        await _sync_app_admin_grants(db, app)
    await db.refresh(app)
    if changes:
        await _log_actor_event(
            db,
            event_type=EventType.ADMIN_APP_UPDATED,
            actor=actor,
            target_type="app",
            target_id=str(app.id),
            details={"changes": changes, "app_slug": app.slug},
        )

    return AppRead(
        id=str(app.id),
        slug=app.slug,
        name=app.name,
        description=app.description,
        app_url=app.app_url,
        roles=app.roles,
        admin_roles=app.admin_roles,
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
async def list_app_users(
    slug: str,
    db: DbSession,
    current_user: CurrentUserOptional,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> list[AppUserAccess]:
    app = await _get_app_or_404(db, slug)
    await _resolve_app_actor(db, app, current_user, authorization, x_api_key)

    access_stmt = (
        select(UserAppAccess, User)
        .join(User, UserAppAccess.user_id == User.id)
        .where(UserAppAccess.app_id == app.id)
        .order_by(UserAppAccess.granted_at.desc())
    )
    access_result = await db.execute(access_stmt)
    access_rows = access_result.all()

    return [_app_user_access_to_read(access, user) for access, user in access_rows]


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
    slug: str,
    request: GrantAccess,
    db: DbSession,
    current_user: CurrentUserOptional,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> MessageResponse:
    app = await _get_app_or_404(db, slug)
    actor = await _resolve_app_actor(db, app, current_user, authorization, x_api_key)
    requested_role = _normalize_role(request.role)
    derived_app_admin = _role_grants_app_admin(app, requested_role)
    normalized_email = request.email.lower().strip()

    # Find user
    user_stmt = select(User).where(User.email == normalized_email)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if not user:
        user = User(
            email=normalized_email,
            status=UserStatus.APPROVED,
            is_admin=False,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        await _log_actor_event(
            db,
            event_type=EventType.ADMIN_USER_CREATED,
            actor=actor,
            target_type="user",
            target_id=str(user.id),
            details={
                "target_email": user.email,
                "changes": {
                    "source": "app_grant",
                    "app_slug": app.slug,
                    "status": user.status.value,
                },
            },
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
        if existing.role != requested_role or existing.is_app_admin != derived_app_admin:
            previous = {"role": existing.role, "is_app_admin": existing.is_app_admin}
            existing.role = requested_role
            existing.is_app_admin = derived_app_admin
            existing.granted_by = actor["actor_email"]  # type: ignore[index]
            await db.flush()
            await _log_actor_event(
                db,
                event_type=EventType.ADMIN_ACCESS_GRANTED,
                actor=actor,
                target_type="app",
                target_id=str(app.id),
                details={
                    "app_slug": app.slug,
                    "target_email": user.email,
                    "changes": {
                        "previous": previous,
                        "current": {
                            "role": existing.role,
                            "is_app_admin": existing.is_app_admin,
                        },
                    },
                },
            )
            return MessageResponse(message=f"Updated role for '{request.email}' on '{slug}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{request.email}' already has access to '{slug}'",
        )

    # Grant access
    access = UserAppAccess(
        user_id=user.id,
        app_id=app.id,
        role=requested_role,
        is_app_admin=derived_app_admin,
        granted_by=actor["actor_email"],  # type: ignore[index]
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
        granted_by=str(actor["actor_email"]),
    )

    await _log_actor_event(
        db,
        event_type=EventType.ADMIN_ACCESS_GRANTED,
        actor=actor,
        target_type="app",
        target_id=str(app.id),
        details={
            "app_slug": app.slug,
            "target_email": user.email,
            "changes": {"role": requested_role, "is_app_admin": derived_app_admin},
        },
    )

    role_msg = f" with role '{requested_role}'" if requested_role else ""
    app_admin_msg = " as app admin" if derived_app_admin else ""
    return MessageResponse(
        message=f"Granted access to '{slug}' for '{request.email}'{role_msg}{app_admin_msg}"
    )


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
    current_user: CurrentUserOptional = None,
    db: DbSession = None,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> MessageResponse:
    email = email.lower()
    app = await _get_app_or_404(db, slug)
    actor = await _resolve_app_actor(db, app, current_user, authorization, x_api_key)

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

    await _log_actor_event(
        db,
        event_type=EventType.ADMIN_ACCESS_REVOKED,
        actor=actor,
        target_type="app",
        target_id=str(app.id),
        details={
            "app_slug": app.slug,
            "target_email": user.email,
            "changes": {"role": access.role, "is_app_admin": access.is_app_admin},
        },
    )

    return MessageResponse(message=f"Revoked access to '{slug}' for '{email}'")


@router.post(
    "/apps/{slug}/api-keys",
    response_model=AppApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create app admin API key",
    description="Create a scoped API key for managing a single app.",
)
async def create_app_api_key(
    slug: str,
    request: AppApiKeyCreate,
    db: DbSession,
    current_user: CurrentUserOptional,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> AppApiKeyCreateResponse:
    app = await _get_app_or_404(db, slug)
    actor = await _resolve_app_actor(db, app, current_user, authorization, x_api_key)
    api_key, plain_text_key = await AppApiKeyService(db).create_key(
        app=app,
        name=request.name,
        created_by=actor["user"] if actor["kind"] == "user" else None,  # type: ignore[arg-type]
        created_by_email=str(actor["actor_email"]),
    )
    await _log_actor_event(
        db,
        event_type=EventType.ADMIN_APP_API_KEY_CREATED,
        actor=actor,
        target_type="app",
        target_id=str(app.id),
        details={
            "app_slug": app.slug,
            "api_key_id": str(api_key.id),
            "api_key_name": api_key.name,
            "key_prefix": api_key.key_prefix,
        },
    )
    return AppApiKeyCreateResponse(
        api_key=_app_api_key_to_read(api_key),
        plain_text_key=plain_text_key,
    )


@router.delete(
    "/apps/{slug}/api-keys/{api_key_id}",
    response_model=MessageResponse,
    summary="Revoke app admin API key",
    description="Revoke a scoped API key for managing a single app.",
)
async def revoke_app_api_key(
    slug: str,
    api_key_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUserOptional,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> MessageResponse:
    app = await _get_app_or_404(db, slug)
    actor = await _resolve_app_actor(db, app, current_user, authorization, x_api_key)
    stmt = select(AppApiKey).where(AppApiKey.id == api_key_id, AppApiKey.app_id == app.id)
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    api_key.revoked_at = datetime.utcnow()
    api_key.revoked_by = str(actor["actor_email"])
    await db.flush()
    await _log_actor_event(
        db,
        event_type=EventType.ADMIN_APP_API_KEY_REVOKED,
        actor=actor,
        target_type="app",
        target_id=str(app.id),
        details={
            "app_slug": app.slug,
            "api_key_id": str(api_key.id),
            "api_key_name": api_key.name,
            "key_prefix": api_key.key_prefix,
        },
    )
    return MessageResponse(message=f"Revoked API key '{api_key.name}'")


@router.get(
    "/apps/{slug}/audit-logs",
    response_model=AuditLogList,
    summary="List app audit logs",
    description="Query audit logs related to a single app scope.",
)
async def list_app_audit_logs(
    slug: str,
    db: DbSession,
    current_user: CurrentUserOptional,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> AuditLogList:
    app = await _get_app_or_404(db, slug)
    await _resolve_app_actor(db, app, current_user, authorization, x_api_key)
    stmt = (
        select(AuditLog)
        .where(
            AuditLog.target_type == "app",
            AuditLog.target_id == str(app.id),
        )
        .order_by(AuditLog.timestamp.desc())
    )
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    logs = result.scalars().all()
    return AuditLogList(
        logs=[_audit_log_to_read(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


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
    target_id: str | None = Query(None, description="Filter by target identifier"),
    ip_address: str | None = Query(None, description="Filter by request IP address"),
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
    if target_id:
        stmt = stmt.where(AuditLog.target_id == target_id)
    if ip_address:
        stmt = stmt.where(AuditLog.ip_address == ip_address)
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
        logs=[_audit_log_to_read(log) for log in logs],
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
