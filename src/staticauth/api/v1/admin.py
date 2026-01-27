import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from staticauth.api.deps import AdminUser, DbSession
from staticauth.models.user import User, UserStatus
from staticauth.schemas.admin import AdminCreateUser, AdminUpdateUser, PendingUserList, UserList
from staticauth.schemas.auth import ErrorResponse, MessageResponse
from staticauth.schemas.user import UserRead
from staticauth.services.email import EmailService

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

    stmt = (
        select(User)
        .where(User.status == UserStatus.PENDING)
        .order_by(User.created_at.asc())
    )
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
