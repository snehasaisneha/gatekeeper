import base64
import json
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Path, Request, Response, status
from sqlalchemy import select

from gatekeeper.api.deps import CurrentUser, CurrentUserOptional, DbSession
from gatekeeper.config import get_settings
from gatekeeper.models.app import AccessRequestStatus, App, AppAccessRequest, UserAppAccess
from gatekeeper.models.otp import OTPPurpose
from gatekeeper.models.user import User, UserStatus
from gatekeeper.rate_limit import limiter
from gatekeeper.schemas.app import AccessRequestCreate, AppPublic
from gatekeeper.schemas.auth import (
    AuthResponse,
    ErrorResponse,
    MessageResponse,
    OTPRequest,
    OTPVerifyRequest,
    PasskeyInfo,
    PasskeyOptionsRequest,
    PasskeyVerifyRequest,
    ProfileUpdateRequest,
    UserAppAccessInfo,
    UserResponse,
)
from gatekeeper.services.email import EmailService
from gatekeeper.services.otp import OTPService
from gatekeeper.services.passkey import PasskeyService
from gatekeeper.services.session import SessionService
from gatekeeper.utils.security import create_signed_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

settings = get_settings()

COOKIE_NAME = "session"
COOKIE_MAX_AGE = settings.session_expiry_days * 24 * 60 * 60


def set_session_cookie(response: Response, token: str) -> None:
    signed_token = create_signed_token(token)
    response.set_cookie(
        key=COOKIE_NAME,
        value=signed_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.app_url.startswith("https"),
        domain=settings.cookie_domain,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, domain=settings.cookie_domain, path="/")


@router.get(
    "/validate",
    responses={
        200: {"description": "Access granted"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied to this app"},
    },
    summary="Validate access (nginx auth_request)",
    description="Validate user authentication and app access. "
    "Used by nginx auth_request directive.",
)
async def validate(
    response: Response,
    db: DbSession,
    current_user: CurrentUserOptional,
    x_gk_app: str | None = Header(None, alias="X-GK-App"),
) -> Response:
    """
    Validate endpoint for nginx auth_request.

    - If user not authenticated: 401
    - If no X-GK-App header: 200 with X-Auth-User (pure identity check)
    - If app not registered: follows DEFAULT_APP_ACCESS setting
    - If app registered: checks user_app_access table
    """
    # Check authentication
    if not current_user:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    # Build base headers for all authenticated requests
    base_headers = {"X-Auth-User": current_user.email}
    if current_user.name:
        base_headers["X-Auth-Name"] = current_user.name

    # No app specified - pure identity check
    if not x_gk_app:
        return Response(status_code=status.HTTP_200_OK, headers=base_headers)

    # Super admins have access to all apps
    if current_user.is_admin:
        return Response(
            status_code=status.HTTP_200_OK,
            headers={**base_headers, "X-Auth-Role": "admin"},
        )

    # Look up the app
    stmt = select(App).where(App.slug == x_gk_app)
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()

    # App not registered - follow default policy
    if not app:
        if settings.default_app_access == "deny":
            return Response(status_code=status.HTTP_403_FORBIDDEN)
        # default_app_access == "allow"
        return Response(status_code=status.HTTP_200_OK, headers=base_headers)

    # Check if user has explicit access (with role)
    access_stmt = select(UserAppAccess).where(
        UserAppAccess.user_id == current_user.id,
        UserAppAccess.app_id == app.id,
    )
    access_result = await db.execute(access_stmt)
    access = access_result.scalar_one_or_none()

    if access:
        # User has explicit access - return headers with role if set
        headers = {**base_headers}
        if access.role:
            headers["X-Auth-Role"] = access.role
        return Response(status_code=status.HTTP_200_OK, headers=headers)

    # No explicit access - public apps are accessible to all approved users
    if app.is_public:
        return Response(status_code=status.HTTP_200_OK, headers=base_headers)

    # Private app without access - deny
    return Response(status_code=status.HTTP_403_FORBIDDEN)


@router.post(
    "/register",
    response_model=MessageResponse,
    responses={
        200: {"description": "OTP sent successfully"},
        400: {"model": ErrorResponse, "description": "Email already registered"},
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
    summary="Start registration",
    description="Send an OTP to the provided email address to start registration.",
)
@limiter.limit("3/hour")
async def register(request: Request, data: OTPRequest, db: DbSession) -> MessageResponse:
    email = data.email.lower()

    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.status == UserStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered. Please sign in instead.",
            )
        elif existing_user.status == UserStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration pending approval. Please wait for admin approval.",
            )
        elif existing_user.status == UserStatus.REJECTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration was rejected. Please contact an administrator.",
            )

    otp_service = OTPService(db)
    sent = await otp_service.create_and_send(email, OTPPurpose.REGISTER)

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please try again.",
        )

    return MessageResponse(
        message="Verification code sent",
        detail="Check your email for the 6-digit code.",
    )


@router.post(
    "/register/verify",
    response_model=AuthResponse,
    responses={
        200: {"description": "Registration successful"},
        400: {"model": ErrorResponse, "description": "Invalid or expired OTP"},
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
    summary="Complete registration",
    description="Verify the OTP and complete registration. "
    "Auto-approves if email domain is in accepted domains.",
)
@limiter.limit("5/15minutes")
async def register_verify(
    request: Request,
    data: OTPVerifyRequest,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    email = data.email.lower()

    otp_service = OTPService(db)
    success, error_message = await otp_service.verify(email, data.code, OTPPurpose.REGISTER)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message or "Invalid or expired verification code.",
        )

    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        )

    auto_approve = settings.is_accepted_domain(email)

    user = User(
        email=email,
        status=UserStatus.APPROVED if auto_approve else UserStatus.PENDING,
        is_admin=False,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    if auto_approve:
        session_service = SessionService(db)
        session = await session_service.create(user)
        await db.commit()  # Commit before responding so /auth/me can find the session
        set_session_cookie(response, session.token)

        return AuthResponse(
            message="Registration successful",
            user=UserResponse.model_validate(user),
        )
    else:
        email_service = EmailService(db=db)
        await email_service.send_registration_pending(email)

        # Notify all admins of the pending registration
        admin_stmt = select(User).where(User.is_admin == True)  # noqa: E712
        admin_result = await db.execute(admin_stmt)
        admins = admin_result.scalars().all()
        for admin in admins:
            await email_service.send_pending_registration_notification(admin.email, email)

        await db.commit()  # Commit pending user so they persist

        return AuthResponse(
            message="Registration pending approval",
            user=None,
        )


@router.post(
    "/signin",
    response_model=MessageResponse,
    responses={
        200: {"description": "OTP sent successfully"},
        400: {"model": ErrorResponse, "description": "User not found or not approved"},
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
    summary="Start sign-in",
    description="Send an OTP to the provided email address to start sign-in.",
)
@limiter.limit("5/15minutes")
async def signin(request: Request, data: OTPRequest, db: DbSession) -> MessageResponse:
    email = data.email.lower()

    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No account found with this email. Please register first.",
        )

    if user.status == UserStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your registration is pending approval.",
        )

    if user.status == UserStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your registration was rejected. Please contact an administrator.",
        )

    otp_service = OTPService(db)
    sent = await otp_service.create_and_send(email, OTPPurpose.SIGNIN)

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please try again.",
        )

    return MessageResponse(
        message="Verification code sent",
        detail="Check your email for the 6-digit code.",
    )


@router.post(
    "/signin/verify",
    response_model=AuthResponse,
    responses={
        200: {"description": "Sign-in successful"},
        400: {"model": ErrorResponse, "description": "Invalid or expired OTP"},
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
    summary="Complete sign-in",
    description="Verify the OTP and complete sign-in.",
)
@limiter.limit("5/15minutes")
async def signin_verify(
    request: Request,
    data: OTPVerifyRequest,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    email = data.email.lower()

    stmt = select(User).where(User.email == email, User.status == UserStatus.APPROVED)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No approved account found with this email.",
        )

    otp_service = OTPService(db)
    success, error_message = await otp_service.verify(email, data.code, OTPPurpose.SIGNIN)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message or "Invalid or expired verification code.",
        )

    session_service = SessionService(db)
    session = await session_service.create(user)
    await db.commit()  # Commit before responding so /auth/me can find the session
    set_session_cookie(response, session.token)

    return AuthResponse(
        message="Successfully signed in",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/signout",
    response_model=MessageResponse,
    summary="Sign out",
    description="Clear the session cookie and invalidate the session.",
)
async def signout(
    response: Response,
    current_user: CurrentUser,
    db: DbSession,
    session: str | None = None,
) -> MessageResponse:
    if session:
        from gatekeeper.utils.security import verify_signed_token

        token = verify_signed_token(session)
        if token:
            session_service = SessionService(db)
            await session_service.delete(token)

    clear_session_cookie(response)
    return MessageResponse(message="Successfully signed out")


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        200: {"description": "Current user info"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Get current user",
    description="Get the currently authenticated user's information.",
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    responses={
        200: {"description": "Profile updated"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Update profile",
    description="Update the current user's profile information.",
)
async def update_me(
    data: ProfileUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    if data.name is not None:
        current_user.name = data.name
    # Only super-admins can toggle notification preferences
    if data.notify_private_app_requests is not None and current_user.is_admin:
        current_user.notify_private_app_requests = data.notify_private_app_requests
    await db.flush()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.get(
    "/apps/public",
    response_model=list[AppPublic],
    responses={
        200: {"description": "List of public apps"},
    },
    summary="List public apps",
    description="List all publicly visible apps for discovery.",
)
async def list_public_apps(db: DbSession) -> list[AppPublic]:
    stmt = select(App).where(App.is_public == True).order_by(App.name)  # noqa: E712
    result = await db.execute(stmt)
    apps = result.scalars().all()

    return [
        AppPublic(slug=app.slug, name=app.name, description=app.description, app_url=app.app_url)
        for app in apps
    ]


@router.get(
    "/apps/private",
    response_model=list[AppPublic],
    responses={
        200: {"description": "List of private apps user can request access to"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="List private apps",
    description="List private apps the user doesn't have access to (for requesting access).",
)
async def list_private_apps(
    current_user: CurrentUser,
    db: DbSession,
) -> list[AppPublic]:
    # Get IDs of apps user already has access to
    access_stmt = select(UserAppAccess.app_id).where(UserAppAccess.user_id == current_user.id)
    access_result = await db.execute(access_stmt)
    accessible_app_ids = {row[0] for row in access_result.all()}

    # Get private apps the user doesn't have access to
    stmt = (
        select(App)
        .where(App.is_public == False)  # noqa: E712
        .where(App.id.notin_(accessible_app_ids) if accessible_app_ids else True)
        .order_by(App.name)
    )
    result = await db.execute(stmt)
    apps = result.scalars().all()

    return [
        AppPublic(slug=app.slug, name=app.name, description=app.description, app_url=app.app_url)
        for app in apps
    ]


@router.get(
    "/me/apps",
    response_model=list[UserAppAccessInfo],
    responses={
        200: {"description": "List of apps user has access to"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="List my apps",
    description="List all apps the user can access (explicit grants + public apps).",
)
async def list_my_apps(
    current_user: CurrentUser,
    db: DbSession,
) -> list[UserAppAccessInfo]:
    # Get apps with explicit access
    stmt = (
        select(UserAppAccess, App)
        .join(App, UserAppAccess.app_id == App.id)
        .where(UserAppAccess.user_id == current_user.id)
        .order_by(App.name)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Build result with explicit access apps
    apps_by_slug: dict[str, UserAppAccessInfo] = {}
    for access, app in rows:
        apps_by_slug[app.slug] = UserAppAccessInfo(
            app_slug=app.slug,
            app_name=app.name,
            app_description=app.description,
            app_url=app.app_url,
            role=access.role,
            granted_at=access.granted_at,
        )

    # Add public apps the user doesn't have explicit access to
    public_stmt = select(App).where(App.is_public == True).order_by(App.name)  # noqa: E712
    public_result = await db.execute(public_stmt)
    public_apps = public_result.scalars().all()

    for app in public_apps:
        if app.slug not in apps_by_slug:
            apps_by_slug[app.slug] = UserAppAccessInfo(
                app_slug=app.slug,
                app_name=app.name,
                app_description=app.description,
                app_url=app.app_url,
                role="user",  # Default role for public apps
                granted_at=app.created_at,  # Use app creation time
            )

    # Return sorted by app name
    return sorted(apps_by_slug.values(), key=lambda x: x.app_name.lower())


@router.post(
    "/me/apps/{slug}/request",
    response_model=MessageResponse,
    responses={
        200: {"description": "Access request submitted"},
        400: {"model": ErrorResponse, "description": "Already have access or pending request"},
        404: {"model": ErrorResponse, "description": "App not found"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="Request app access",
    description="Request access to an app. Creates a pending request for admin review.",
)
async def request_app_access(
    slug: str,
    current_user: CurrentUser,
    db: DbSession,
    data: AccessRequestCreate | None = None,
) -> MessageResponse:
    # Find the app
    stmt = select(App).where(App.slug == slug)
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="App not found.",
        )

    # Check if user already has access
    access_stmt = select(UserAppAccess).where(
        UserAppAccess.user_id == current_user.id,
        UserAppAccess.app_id == app.id,
    )
    access_result = await db.execute(access_stmt)
    if access_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have access to this app.",
        )

    # Check if there's already a pending request
    pending_stmt = select(AppAccessRequest).where(
        AppAccessRequest.user_id == current_user.id,
        AppAccessRequest.app_id == app.id,
        AppAccessRequest.status == AccessRequestStatus.PENDING,
    )
    pending_result = await db.execute(pending_stmt)
    if pending_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a pending request for this app.",
        )

    # Create the request
    access_request = AppAccessRequest(
        user_id=current_user.id,
        app_id=app.id,
        message=data.message if data else None,
    )
    db.add(access_request)
    await db.flush()

    # For private apps, notify opted-in super-admins
    # Wrap in try/except so notification failures don't affect the request
    if not app.is_public:
        try:
            admin_stmt = select(User).where(
                User.is_admin == True,  # noqa: E712
                User.notify_private_app_requests == True,  # noqa: E712
            )
            admin_result = await db.execute(admin_stmt)
            admins = admin_result.scalars().all()

            email_service = EmailService(db=db)
            for admin in admins:
                await email_service.send_private_app_access_request_notification(
                    admin_email=admin.email,
                    requester_email=current_user.email,
                    requester_name=current_user.name,
                    app_name=app.name,
                    message=data.message if data else None,
                )
        except Exception:
            # Log but don't fail the request
            import logging

            logging.getLogger(__name__).exception(
                "Failed to send private app access request notifications"
            )

    return MessageResponse(
        message="Access request submitted",
        detail="Your request is pending admin review.",
    )


@router.delete(
    "/me",
    response_model=MessageResponse,
    responses={
        200: {"description": "Account deleted"},
        400: {"model": ErrorResponse, "description": "Cannot delete seeded admin"},
    },
    summary="Delete account",
    description="Delete the current user's account and all associated data.",
)
async def delete_me(
    response: Response,
    current_user: CurrentUser,
    db: DbSession,
) -> MessageResponse:
    if current_user.is_seeded:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete seeded admin account.",
        )

    await db.delete(current_user)
    await db.flush()
    clear_session_cookie(response)
    return MessageResponse(message="Account deleted successfully")


_passkey_challenges: dict[str, bytes] = {}
_passkey_registration_challenges: dict[str, bytes] = {}


@router.post(
    "/passkey/register/options",
    response_model=dict[str, Any],
    summary="Get passkey registration options",
    description="Get WebAuthn options for registering a new passkey. Requires authentication.",
)
async def passkey_register_options(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    passkey_service = PasskeyService(db)
    options = await passkey_service.generate_registration_options(current_user)
    # Store challenge at module level so it persists across requests
    user_id = str(current_user.id)
    _passkey_registration_challenges[user_id] = passkey_service._challenges.get(user_id)
    return options


@router.post(
    "/passkey/register/verify",
    response_model=MessageResponse,
    responses={
        200: {"description": "Passkey registered successfully"},
        400: {"model": ErrorResponse, "description": "Passkey registration failed"},
    },
    summary="Complete passkey registration",
    description="Verify and save a new passkey credential.",
)
async def passkey_register_verify(
    request: PasskeyVerifyRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> MessageResponse:
    # Retrieve challenge from module-level storage
    challenge = _passkey_registration_challenges.pop(str(current_user.id), None)
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Challenge expired or invalid. Please try again.",
        )

    passkey_service = PasskeyService(db)
    credential_dict = request.credential.model_dump()
    passkey_name = request.name or "Passkey"
    passkey = await passkey_service.verify_registration_with_challenge(
        current_user, credential_dict, challenge, name=passkey_name
    )

    if not passkey:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to register passkey. Please try again.",
        )

    return MessageResponse(
        message="Passkey registered successfully",
        detail="You can now use this passkey to sign in.",
    )


@router.post(
    "/passkey/signin/options",
    response_model=dict[str, Any],
    responses={
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
    summary="Get passkey sign-in options",
    description="Get WebAuthn options for signing in with a passkey.",
)
@limiter.limit("10/15minutes")
async def passkey_signin_options(
    request: Request,
    data: PasskeyOptionsRequest,
    db: DbSession,
) -> dict[str, Any]:
    passkey_service = PasskeyService(db)
    options, challenge = await passkey_service.generate_authentication_options(data.email)

    challenge_key = options["challenge"]
    _passkey_challenges[challenge_key] = challenge

    return options


@router.post(
    "/passkey/signin/verify",
    response_model=AuthResponse,
    responses={
        200: {"description": "Sign-in successful"},
        400: {"model": ErrorResponse, "description": "Passkey authentication failed"},
    },
    summary="Complete passkey sign-in",
    description="Verify passkey authentication and create a session.",
)
async def passkey_signin_verify(
    request: PasskeyVerifyRequest,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    credential_dict = request.credential.model_dump()
    client_data = credential_dict.get("response", {}).get("clientDataJSON", "")

    try:
        client_data_json = json.loads(base64.urlsafe_b64decode(client_data + "=="))
        challenge_from_client = client_data_json.get("challenge", "")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid credential format.",
        ) from None

    challenge = _passkey_challenges.pop(challenge_from_client, None)
    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Challenge expired or invalid. Please try again.",
        )

    passkey_service = PasskeyService(db)
    user = await passkey_service.verify_authentication(credential_dict, challenge)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passkey authentication failed.",
        )

    if user.status != UserStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not approved.",
        )

    session_service = SessionService(db)
    session = await session_service.create(user)
    await db.commit()  # Commit before responding so /auth/me can find the session
    set_session_cookie(response, session.token)

    return AuthResponse(
        message="Successfully signed in",
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/passkeys",
    response_model=list[PasskeyInfo],
    summary="List passkeys",
    description="List all registered passkeys for the current user.",
)
async def list_passkeys(current_user: CurrentUser, db: DbSession) -> list[PasskeyInfo]:
    passkey_service = PasskeyService(db)
    passkeys = await passkey_service.list_passkeys(current_user.id)
    return [PasskeyInfo(**p) for p in passkeys]


@router.delete(
    "/passkeys/{passkey_id}",
    response_model=MessageResponse,
    responses={
        200: {"description": "Passkey deleted successfully"},
        404: {"model": ErrorResponse, "description": "Passkey not found"},
    },
    summary="Delete passkey",
    description="Delete a registered passkey.",
)
async def delete_passkey(
    passkey_id: str = Path(..., description="UUID of the passkey to delete"),
    current_user: CurrentUser = None,
    db: DbSession = None,
) -> MessageResponse:
    try:
        pk_uuid = uuid.UUID(passkey_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid passkey ID format. Must be a valid UUID.",
        ) from None

    passkey_service = PasskeyService(db)
    deleted = await passkey_service.delete_passkey(pk_uuid, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Passkey not found.",
        )

    return MessageResponse(message="Passkey deleted successfully")
