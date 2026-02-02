import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from gatekeeper.api.deps import AdminUser, DbSession
from gatekeeper.models.app import AccessRequestStatus, App, AppAccessRequest, UserAppAccess
from gatekeeper.models.user import User, UserStatus
from gatekeeper.schemas.admin import AdminCreateUser, AdminUpdateUser, PendingUserList, UserList
from gatekeeper.schemas.app import (
    AccessRequestRead,
    AccessRequestReview,
    AppCreate,
    AppDetail,
    AppList,
    AppRead,
    AppUserAccess,
    GrantAccess,
)
from gatekeeper.schemas.auth import ErrorResponse, MessageResponse
from gatekeeper.schemas.user import UserRead
from gatekeeper.services.email import EmailService

router = APIRouter(prefix="/admin", tags=["Admin"])


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
) -> UserList:
    offset = (page - 1) * page_size

    count_stmt = select(func.count(User.id))
    query_stmt = select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)

    if status_filter:
        count_stmt = count_stmt.where(User.status == status_filter)
        query_stmt = query_stmt.where(User.status == status_filter)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    result = await db.execute(query_stmt)
    users = result.scalars().all()

    return UserList(
        users=[UserRead.model_validate(u) for u in users],
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

    return PendingUserList(
        users=[UserRead.model_validate(u) for u in users],
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

    return UserRead.model_validate(user)


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

    # Send invitation email
    if request.auto_approve:
        await email_service.send_invitation(email, admin.email)

    return UserRead.model_validate(user)


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

    await db.flush()
    await db.refresh(user)

    if was_pending and user.status == UserStatus.APPROVED:
        email_service = EmailService(db=db)
        await email_service.send_registration_approved(user.email)

    return UserRead.model_validate(user)


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

    return UserRead.model_validate(user)


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
    await db.flush()
    await db.refresh(user)

    return UserRead.model_validate(user)


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
            AppRead(id=str(a.id), slug=a.slug, name=a.name, created_at=a.created_at) for a in apps
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
    stmt = select(App).where(App.slug == request.slug)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"App with slug '{request.slug}' already exists",
        )

    app = App(slug=request.slug, name=request.name)
    db.add(app)
    await db.flush()
    await db.refresh(app)

    return AppRead(id=str(app.id), slug=app.slug, name=app.name, created_at=app.created_at)


@router.get(
    "/apps/{slug}",
    response_model=AppDetail,
    responses={
        200: {"description": "App details with users"},
        404: {"model": ErrorResponse, "description": "App not found"},
    },
    summary="Get app details",
    description="Get app details including users with access. Admin only.",
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

    # Get users with access
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


@router.get(
    "/apps/{slug}/users",
    response_model=list[AppUserAccess],
    responses={
        200: {"description": "Users with access"},
        404: {"model": ErrorResponse, "description": "App not found"},
    },
    summary="List app users",
    description="List all users with access to an app. Admin only.",
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
    description="Grant a user access to an app with optional role. Admin only.",
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
    description="Revoke a user's access to an app. Admin only.",
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
            detail=f"User '{email}' does not have access to '{slug}'",
        )

    await db.delete(access)
    await db.flush()

    return MessageResponse(message=f"Revoked access to '{slug}' for '{email}'")


# ============================================================================
# Access Request Management Endpoints
# ============================================================================


@router.get(
    "/apps/{slug}/requests",
    response_model=list[AccessRequestRead],
    responses={
        200: {"description": "Pending access requests"},
        404: {"model": ErrorResponse, "description": "App not found"},
    },
    summary="List pending access requests",
    description="List all pending access requests for an app. Admin only.",
)
async def list_access_requests(
    slug: str,
    admin: AdminUser,
    db: DbSession,
    status_filter: AccessRequestStatus | None = Query(None, description="Filter by status"),
) -> list[AccessRequestRead]:
    # Find app
    app_stmt = select(App).where(App.slug == slug)
    app_result = await db.execute(app_stmt)
    app = app_result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App '{slug}' not found",
        )

    # Get requests
    requests_stmt = (
        select(AppAccessRequest, User)
        .join(User, AppAccessRequest.user_id == User.id)
        .where(AppAccessRequest.app_id == app.id)
    )

    if status_filter:
        requests_stmt = requests_stmt.where(AppAccessRequest.status == status_filter)
    else:
        # By default, show pending requests
        requests_stmt = requests_stmt.where(AppAccessRequest.status == AccessRequestStatus.PENDING)

    requests_stmt = requests_stmt.order_by(AppAccessRequest.created_at.asc())
    result = await db.execute(requests_stmt)
    rows = result.all()

    return [
        AccessRequestRead(
            id=str(req.id),
            user_email=user.email,
            user_name=user.name,
            app_slug=app.slug,
            app_name=app.name,
            message=req.message,
            status=req.status,
            reviewed_by=req.reviewed_by,
            reviewed_at=req.reviewed_at,
            created_at=req.created_at,
        )
        for req, user in rows
    ]


@router.post(
    "/apps/{slug}/requests/{request_id}/approve",
    response_model=MessageResponse,
    responses={
        200: {"description": "Request approved and access granted"},
        404: {"model": ErrorResponse, "description": "App or request not found"},
        400: {"model": ErrorResponse, "description": "Request not pending"},
    },
    summary="Approve access request",
    description="Approve a pending access request and grant access. Admin only.",
)
async def approve_access_request(
    slug: str,
    request_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
    data: AccessRequestReview | None = None,
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

    # Find request
    req_stmt = (
        select(AppAccessRequest, User)
        .join(User, AppAccessRequest.user_id == User.id)
        .where(
            AppAccessRequest.id == request_id,
            AppAccessRequest.app_id == app.id,
        )
    )
    req_result = await db.execute(req_stmt)
    row = req_result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access request not found",
        )

    access_request, user = row

    if access_request.status != AccessRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {access_request.status.value}",
        )

    # Update request status
    access_request.status = AccessRequestStatus.APPROVED
    access_request.reviewed_by = admin.email
    access_request.reviewed_at = datetime.now(UTC)

    # Grant access
    role = data.role if data else None
    access = UserAppAccess(
        user_id=user.id,
        app_id=app.id,
        role=role,
        granted_by=admin.email,
    )
    db.add(access)
    await db.flush()

    role_msg = f" with role '{role}'" if role else ""
    return MessageResponse(message=f"Approved access to '{slug}' for '{user.email}'{role_msg}")


@router.post(
    "/apps/{slug}/requests/{request_id}/reject",
    response_model=MessageResponse,
    responses={
        200: {"description": "Request rejected"},
        404: {"model": ErrorResponse, "description": "App or request not found"},
        400: {"model": ErrorResponse, "description": "Request not pending"},
    },
    summary="Reject access request",
    description="Reject a pending access request. Admin only.",
)
async def reject_access_request(
    slug: str,
    request_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
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

    # Find request
    req_stmt = (
        select(AppAccessRequest, User)
        .join(User, AppAccessRequest.user_id == User.id)
        .where(
            AppAccessRequest.id == request_id,
            AppAccessRequest.app_id == app.id,
        )
    )
    req_result = await db.execute(req_stmt)
    row = req_result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Access request not found",
        )

    access_request, user = row

    if access_request.status != AccessRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {access_request.status.value}",
        )

    # Update request status
    access_request.status = AccessRequestStatus.REJECTED
    access_request.reviewed_by = admin.email
    access_request.reviewed_at = datetime.now(UTC)
    await db.flush()

    return MessageResponse(message=f"Rejected access request from '{user.email}' for '{slug}'")
