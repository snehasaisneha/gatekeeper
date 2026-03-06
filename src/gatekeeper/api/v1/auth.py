import base64
import json
import logging
import secrets
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from gatekeeper.api.deps import CurrentUser, CurrentUserOptional, DbSession
from gatekeeper.config import get_settings
from gatekeeper.models.app import App, UserAppAccess
from gatekeeper.models.branding import Branding
from gatekeeper.models.domain import ApprovedDomain
from gatekeeper.models.otp import OTPPurpose
from gatekeeper.models.user import User, UserStatus
from gatekeeper.rate_limit import limiter
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
from gatekeeper.schemas.branding import BrandingRead
from gatekeeper.services.audit import AuditService
from gatekeeper.services.email import EmailService
from gatekeeper.services.otp import OTPService
from gatekeeper.services.passkey import PasskeyService
from gatekeeper.services.session import SessionService
from gatekeeper.utils.security import create_signed_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

settings = get_settings()

COOKIE_NAME = "session"
COOKIE_MAX_AGE = settings.session_expiry_days * 24 * 60 * 60


async def is_internal_user(db: DbSession, email: str) -> bool:
    """Check if user's email domain is in approved_domains table."""
    domain = email.split("@")[-1].lower()
    stmt = select(ApprovedDomain).where(ApprovedDomain.domain == domain)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


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


def create_redirect(url: str, status_code: int = status.HTTP_302_FOUND) -> RedirectResponse:
    """Create a redirect response with no-cache headers to prevent browser caching."""
    response = RedirectResponse(url=url, status_code=status_code)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


async def _build_user_response(db: DbSession, user: User) -> UserResponse:
    """Build UserResponse with is_internal computed."""
    is_internal = await is_internal_user(db, user.email)
    return UserResponse(
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
    - If app registered: checks access based on internal/external status
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

    # Check if user is internal (domain in approved_domains)
    if await is_internal_user(db, current_user.email):
        # Internal user - grant access with "user" role
        return Response(
            status_code=status.HTTP_200_OK,
            headers={**base_headers, "X-Auth-Role": "user"},
        )

    # External user - check explicit user_app_access
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

    # External user without explicit access - deny
    return Response(status_code=status.HTTP_403_FORBIDDEN)


@router.post(
    "/signin",
    response_model=MessageResponse,
    responses={
        200: {"description": "OTP sent successfully"},
        400: {"model": ErrorResponse, "description": "User rejected"},
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
    summary="Start sign-in",
    description="Send an OTP to the provided email address. "
    "Auto-creates account if user doesn't exist (auto-approved if domain is in approved_domains).",
)
@limiter.limit("5/15minutes")
async def signin(request: Request, data: OTPRequest, db: DbSession) -> MessageResponse:
    email = data.email.lower()

    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Auto-create user if they don't exist
    if not user:
        is_internal = await is_internal_user(db, email)
        user = User(
            email=email,
            status=UserStatus.APPROVED if is_internal else UserStatus.PENDING,
            is_admin=False,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

        # Notify admins who want to know about ALL new registrations
        try:
            email_service = EmailService(db=db)
            admin_stmt = select(User).where(
                User.is_admin == True,  # noqa: E712
                User.notify_all_registrations == True,  # noqa: E712
            )
            admin_result = await db.execute(admin_stmt)
            admins = admin_result.scalars().all()
            for admin in admins:
                await email_service.send_new_user_notification(
                    admin.email, email, is_auto_approved=(user.status == UserStatus.APPROVED)
                )
        except Exception:
            # Don't let notification failures prevent user signin
            logger.exception("Failed to send new user notification")

    # Rejected users cannot sign in
    if user.status == UserStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account was rejected. Please contact an administrator.",
        )

    # Pending users can still verify their email, but won't get a session until approved
    # We send them the OTP so they can prove email ownership

    otp_service = OTPService(db)
    sent = await otp_service.create_and_send(email, OTPPurpose.SIGNIN)

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please try again.",
        )

    return MessageResponse(
        message="Verification code sent",
        detail="Check your email for the 6-digit code. Check spam if not found.",
    )


@router.post(
    "/signin/verify",
    response_model=AuthResponse,
    responses={
        200: {"description": "Sign-in successful or pending approval"},
        400: {"model": ErrorResponse, "description": "Invalid or expired OTP"},
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
    summary="Complete sign-in",
    description="Verify the OTP and complete sign-in. "
    "For pending users, sends notification to admins and returns pending status.",
)
@limiter.limit("5/15minutes")
async def signin_verify(
    request: Request,
    data: OTPVerifyRequest,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    email = data.email.lower()

    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No account found with this email.",
        )

    if user.status == UserStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your account was rejected. Please contact an administrator.",
        )

    otp_service = OTPService(db)
    audit_service = AuditService(db)
    success, error_message = await otp_service.verify(email, data.code, OTPPurpose.SIGNIN)
    if not success:
        await audit_service.log_auth_failed("otp", email, request, reason=error_message)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message or "Invalid or expired verification code.",
        )

    # Handle pending users - notify them and admins who opted in
    if user.status == UserStatus.PENDING:
        email_service = EmailService(db=db)
        await email_service.send_registration_pending(email)

        # Notify admins who have enabled registration notifications
        admin_stmt = select(User).where(
            User.is_admin == True,  # noqa: E712
            User.notify_new_registrations == True,  # noqa: E712
        )
        admin_result = await db.execute(admin_stmt)
        admins = admin_result.scalars().all()
        for admin in admins:
            await email_service.send_pending_registration_notification(admin.email, email)

        await db.commit()

        return AuthResponse(
            message="Your account is pending approval",
            user=None,
        )

    # Approved user - create session
    session_service = SessionService(db)
    session = await session_service.create(user)

    # Log successful sign-in
    await audit_service.log_auth_success("otp", user, request)

    await db.commit()  # Commit before responding so /auth/me can find the session
    set_session_cookie(response, session.token)

    return AuthResponse(
        message="Successfully signed in",
        user=await _build_user_response(db, user),
    )


@router.post(
    "/signout",
    response_model=MessageResponse,
    summary="Sign out",
    description="Clear the session cookie and invalidate the session.",
)
async def signout(
    request: Request,
    response: Response,
    current_user: CurrentUserOptional,
    db: DbSession,
    session: str | None = None,
) -> MessageResponse:
    if session:
        from gatekeeper.utils.security import verify_signed_token

        token = verify_signed_token(session)
        if token:
            session_service = SessionService(db)
            await session_service.delete(token)

    # Log sign-out if user was authenticated
    if current_user:
        audit_service = AuditService(db)
        await audit_service.log_signout(current_user, request)
        await db.commit()

    # Always clear the cookie, even if session was invalid
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
async def get_me(current_user: CurrentUser, db: DbSession) -> UserResponse:
    return await _build_user_response(db, current_user)


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
    # Only admins can set notification preferences
    if data.notify_new_registrations is not None and current_user.is_admin:
        current_user.notify_new_registrations = data.notify_new_registrations
    if data.notify_all_registrations is not None and current_user.is_admin:
        current_user.notify_all_registrations = data.notify_all_registrations
    await db.flush()
    await db.refresh(current_user)
    return await _build_user_response(db, current_user)


@router.get(
    "/me/apps",
    response_model=list[UserAppAccessInfo],
    responses={
        200: {"description": "List of apps user has access to"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
    summary="List my apps",
    description="List all apps the user can access. Internal users see all apps, "
    "external users see only explicitly granted apps.",
)
async def list_my_apps(
    current_user: CurrentUser,
    db: DbSession,
) -> list[UserAppAccessInfo]:
    # Check if user is internal
    is_internal = await is_internal_user(db, current_user.email)

    if is_internal:
        # Internal users have access to ALL apps with "user" role
        stmt = select(App).order_by(App.name)
        result = await db.execute(stmt)
        apps = result.scalars().all()

        # Check for explicit access to override default role
        access_stmt = (
            select(UserAppAccess, App)
            .join(App, UserAppAccess.app_id == App.id)
            .where(UserAppAccess.user_id == current_user.id)
        )
        access_result = await db.execute(access_stmt)
        explicit_access = {row[1].slug: row[0] for row in access_result.all()}

        return [
            UserAppAccessInfo(
                app_slug=app.slug,
                app_name=app.name,
                app_description=app.description,
                app_url=app.app_url,
                role=explicit_access[app.slug].role if app.slug in explicit_access else "user",
                granted_at=(
                    explicit_access[app.slug].granted_at
                    if app.slug in explicit_access
                    else app.created_at
                ),
            )
            for app in apps
        ]
    else:
        # External users only see apps they have explicit access to
        stmt = (
            select(UserAppAccess, App)
            .join(App, UserAppAccess.app_id == App.id)
            .where(UserAppAccess.user_id == current_user.id)
            .order_by(App.name)
        )
        result = await db.execute(stmt)
        rows = result.all()

        return [
            UserAppAccessInfo(
                app_slug=app.slug,
                app_name=app.name,
                app_description=app.description,
                app_url=app.app_url,
                role=access.role,
                granted_at=access.granted_at,
            )
            for access, app in rows
        ]


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

# OAuth state storage (state -> redirect_url)
_oauth_states: dict[str, str] = {}

# Google OAuth constants
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# GitHub OAuth constants
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


@router.post(
    "/passkey/register/options",
    response_model=dict[str, Any],
    responses={
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
    summary="Get passkey registration options",
    description="Get WebAuthn options for registering a new passkey. Requires authentication.",
)
@limiter.limit("10/15minutes")
async def passkey_register_options(
    request: Request, current_user: CurrentUser, db: DbSession
) -> dict[str, Any]:
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
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
    summary="Complete passkey registration",
    description="Verify and save a new passkey credential.",
)
@limiter.limit("10/15minutes")
async def passkey_register_verify(
    request: Request,
    data: PasskeyVerifyRequest,
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
    credential_dict = data.credential.model_dump()
    passkey_name = data.name or "Passkey"
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
        429: {"model": ErrorResponse, "description": "Too many requests"},
    },
    summary="Complete passkey sign-in",
    description="Verify passkey authentication and create a session.",
)
@limiter.limit("10/15minutes")
async def passkey_signin_verify(
    request: Request,
    data: PasskeyVerifyRequest,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    credential_dict = data.credential.model_dump()
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
    audit_service = AuditService(db)
    user = await passkey_service.verify_authentication(credential_dict, challenge)

    if not user:
        await audit_service.log_auth_failed("passkey", None, request, reason="Invalid credential")
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passkey authentication failed.",
        )

    if user.status != UserStatus.APPROVED:
        await audit_service.log_auth_failed(
            "passkey", user.email, request, reason="Account not approved"
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not approved.",
        )

    session_service = SessionService(db)
    session = await session_service.create(user)

    # Log successful sign-in
    await audit_service.log_auth_success("passkey", user, request)

    await db.commit()  # Commit before responding so /auth/me can find the session
    set_session_cookie(response, session.token)

    return AuthResponse(
        message="Successfully signed in",
        user=await _build_user_response(db, user),
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
    passkey_id: str,
    current_user: CurrentUser,
    db: DbSession,
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


@router.get(
    "/google/login",
    response_class=RedirectResponse,
    responses={
        302: {"description": "Redirect to Google OAuth"},
        400: {"model": ErrorResponse, "description": "Google OAuth not configured"},
    },
    summary="Start Google OAuth",
    description="Redirect to Google OAuth for authentication.",
)
async def google_login(
    request: Request,
    redirect: str | None = None,
) -> RedirectResponse:
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth is not configured.",
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = redirect or "/"

    # Build Google OAuth URL
    callback_url = f"{settings.app_url}/api/v1/auth/google/callback"
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/google/callback",
    response_class=RedirectResponse,
    responses={
        302: {"description": "Redirect to frontend after authentication"},
        400: {"model": ErrorResponse, "description": "OAuth error"},
    },
    summary="Google OAuth callback",
    description="Handle Google OAuth callback and create session.",
)
async def google_callback(
    request: Request,
    response: Response,
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    # Handle OAuth errors
    if error:
        return create_redirect(f"{settings.frontend_url}/signin?error={error}")

    if not code or not state:
        return create_redirect(f"{settings.frontend_url}/signin?error=missing_params")

    # Verify state
    redirect_url = _oauth_states.pop(state, None)
    if redirect_url is None:
        return create_redirect(f"{settings.frontend_url}/signin?error=invalid_state")

    try:
        # Exchange code for tokens
        callback_url = f"{settings.app_url}/api/v1/auth/google/callback"
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": callback_url,
                },
            )
            token_response.raise_for_status()
            tokens = token_response.json()

            # Get user info
            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()

        email = userinfo.get("email", "").lower()
        if not email:
            return create_redirect(f"{settings.frontend_url}/signin?error=no_email")

        # Find or create user
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # Auto-create user
            is_internal = await is_internal_user(db, email)
            user = User(
                email=email,
                name=userinfo.get("name"),
                status=UserStatus.APPROVED if is_internal else UserStatus.PENDING,
                is_admin=False,
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)

            # Notify admins who want to know about ALL new registrations
            try:
                email_service = EmailService(db=db)
                admin_stmt = select(User).where(
                    User.is_admin == True,  # noqa: E712
                    User.notify_all_registrations == True,  # noqa: E712
                )
                admin_result = await db.execute(admin_stmt)
                admins = admin_result.scalars().all()
                for admin in admins:
                    await email_service.send_new_user_notification(
                        admin.email, email, is_auto_approved=(user.status == UserStatus.APPROVED)
                    )
            except Exception:
                logger.exception("Failed to send new user notification")

        # Handle rejected users
        if user.status == UserStatus.REJECTED:
            return create_redirect(f"{settings.frontend_url}/signin?error=account_rejected")

        # Handle pending users
        if user.status == UserStatus.PENDING:
            email_service = EmailService(db=db)
            await email_service.send_registration_pending(email)

            # Notify admins who have enabled registration notifications
            admin_stmt = select(User).where(
                User.is_admin == True,  # noqa: E712
                User.notify_new_registrations == True,  # noqa: E712
            )
            admin_result = await db.execute(admin_stmt)
            admins = admin_result.scalars().all()
            for admin in admins:
                await email_service.send_pending_registration_notification(admin.email, email)

            await db.commit()
            return create_redirect(f"{settings.frontend_url}/signin?pending=true")

        # Update name from Google if not set
        if not user.name and userinfo.get("name"):
            user.name = userinfo.get("name")

        # Create session
        session_service = SessionService(db)
        session = await session_service.create(user)

        # Log successful sign-in
        audit_service = AuditService(db)
        await audit_service.log_auth_success("google", user, request)

        await db.commit()

        # Create response with cookie
        # Use redirect_url directly if it's an absolute URL, otherwise prepend frontend_url
        if redirect_url.startswith(("http://", "https://")):
            final_url = redirect_url
        else:
            final_url = f"{settings.frontend_url}{redirect_url}"
        final_redirect = create_redirect(final_url)
        set_session_cookie(final_redirect, session.token)
        return final_redirect

    except httpx.HTTPStatusError:
        # Log failed OAuth
        audit_service = AuditService(db)
        await audit_service.log_auth_failed(
            "google", None, request, reason="HTTP error from Google"
        )
        await db.commit()
        return create_redirect(f"{settings.frontend_url}/signin?error=oauth_failed")
    except Exception:
        logger.exception("Unexpected error in Google OAuth callback")
        return create_redirect(f"{settings.frontend_url}/signin?error=internal_error")


@router.get(
    "/google/enabled",
    response_model=dict[str, bool],
    summary="Check if Google OAuth is enabled",
    description="Returns whether Google OAuth is configured and available.",
)
async def google_enabled() -> dict[str, bool]:
    return {"enabled": settings.google_oauth_enabled}


@router.get(
    "/github/login",
    response_class=RedirectResponse,
    responses={
        302: {"description": "Redirect to GitHub OAuth"},
        400: {"model": ErrorResponse, "description": "GitHub OAuth not configured"},
    },
    summary="Start GitHub OAuth",
    description="Redirect to GitHub OAuth for authentication.",
)
async def github_login(
    request: Request,
    redirect: str | None = None,
) -> RedirectResponse:
    if not settings.github_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub OAuth is not configured.",
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = redirect or "/"

    # Build GitHub OAuth URL
    callback_url = f"{settings.app_url}/api/v1/auth/github/callback"
    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": callback_url,
        "scope": "user:email",
        "state": state,
    }

    auth_url = f"{GITHUB_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/github/callback",
    response_class=RedirectResponse,
    responses={
        302: {"description": "Redirect to frontend after authentication"},
        400: {"model": ErrorResponse, "description": "OAuth error"},
    },
    summary="GitHub OAuth callback",
    description="Handle GitHub OAuth callback and create session.",
)
async def github_callback(
    request: Request,
    response: Response,
    db: DbSession,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    # Handle OAuth errors
    if error:
        return create_redirect(f"{settings.frontend_url}/signin?error={error}")

    if not code or not state:
        return create_redirect(f"{settings.frontend_url}/signin?error=missing_params")

    # Verify state
    redirect_url = _oauth_states.pop(state, None)
    if redirect_url is None:
        return create_redirect(f"{settings.frontend_url}/signin?error=invalid_state")

    try:
        # Exchange code for access token
        callback_url = f"{settings.app_url}/api/v1/auth/github/callback"
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GITHUB_TOKEN_URL,
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": callback_url,
                },
                headers={"Accept": "application/json"},
            )
            token_response.raise_for_status()
            tokens = token_response.json()

            access_token = tokens.get("access_token")
            if not access_token:
                return create_redirect(f"{settings.frontend_url}/signin?error=oauth_failed")

            # Get user info
            user_response = await client.get(
                GITHUB_USER_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            user_response.raise_for_status()
            userinfo = user_response.json()

            # Get all user emails
            emails_response = await client.get(
                GITHUB_EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            emails_response.raise_for_status()
            emails_data = emails_response.json()

        # Find verified emails and check for approved domains
        verified_emails = [e["email"].lower() for e in emails_data if e.get("verified", False)]

        if not verified_emails:
            return create_redirect(f"{settings.frontend_url}/signin?error=no_email")

        # Check if any verified email matches an approved domain
        matching_email = None
        for email in verified_emails:
            if await is_internal_user(db, email):
                matching_email = email
                break

        # If no domain match, check if user already exists with any of these emails
        existing_user = None
        if not matching_email:
            for email in verified_emails:
                stmt = select(User).where(User.email == email)
                result = await db.execute(stmt)
                existing_user = result.scalar_one_or_none()
                if existing_user:
                    matching_email = email
                    break

        # If still no match, use primary email but they'll need approval
        if not matching_email:
            primary_emails = [e["email"].lower() for e in emails_data if e.get("primary")]
            matching_email = primary_emails[0] if primary_emails else verified_emails[0]

        email = matching_email

        # Find or create user
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        is_internal = await is_internal_user(db, email)

        if not user:
            # For GitHub, if no approved domain match, show specific error
            if not is_internal:
                return create_redirect(f"{settings.frontend_url}/signin?error=github_no_org_email")

            # Auto-create user (only for internal domain matches)
            user = User(
                email=email,
                name=userinfo.get("name") or userinfo.get("login"),
                status=UserStatus.APPROVED,
                is_admin=False,
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)

            # Notify admins who want to know about ALL new registrations
            try:
                email_service = EmailService(db=db)
                admin_stmt = select(User).where(
                    User.is_admin == True,  # noqa: E712
                    User.notify_all_registrations == True,  # noqa: E712
                )
                admin_result = await db.execute(admin_stmt)
                admins = admin_result.scalars().all()
                for admin in admins:
                    await email_service.send_new_user_notification(
                        admin.email, email, is_auto_approved=True
                    )
            except Exception:
                logger.exception("Failed to send new user notification")

        # Handle rejected users
        if user.status == UserStatus.REJECTED:
            return create_redirect(f"{settings.frontend_url}/signin?error=account_rejected")

        # Handle pending users
        if user.status == UserStatus.PENDING:
            email_service = EmailService(db=db)
            await email_service.send_registration_pending(email)

            # Notify admins who have enabled registration notifications
            admin_stmt = select(User).where(
                User.is_admin == True,  # noqa: E712
                User.notify_new_registrations == True,  # noqa: E712
            )
            admin_result = await db.execute(admin_stmt)
            admins = admin_result.scalars().all()
            for admin in admins:
                await email_service.send_pending_registration_notification(admin.email, email)

            await db.commit()
            return create_redirect(f"{settings.frontend_url}/signin?pending=true")

        # Update name from GitHub if not set
        if not user.name:
            user.name = userinfo.get("name") or userinfo.get("login")

        # Create session
        session_service = SessionService(db)
        session = await session_service.create(user)

        # Log successful sign-in
        audit_service = AuditService(db)
        await audit_service.log_auth_success(
            "github", user, request, details={"email_matched": email}
        )

        await db.commit()

        # Create response with cookie
        # Use redirect_url directly if it's an absolute URL, otherwise prepend frontend_url
        if redirect_url.startswith(("http://", "https://")):
            final_url = redirect_url
        else:
            final_url = f"{settings.frontend_url}{redirect_url}"
        final_redirect = create_redirect(final_url)
        set_session_cookie(final_redirect, session.token)
        return final_redirect

    except httpx.HTTPStatusError:
        # Log failed OAuth
        audit_service = AuditService(db)
        await audit_service.log_auth_failed(
            "github", None, request, reason="HTTP error from GitHub"
        )
        await db.commit()
        return create_redirect(f"{settings.frontend_url}/signin?error=oauth_failed")
    except Exception:
        logger.exception("Unexpected error in GitHub OAuth callback")
        return create_redirect(f"{settings.frontend_url}/signin?error=internal_error")


@router.get(
    "/github/enabled",
    response_model=dict[str, bool],
    summary="Check if GitHub OAuth is enabled",
    description="Returns whether GitHub OAuth is configured and available.",
)
async def github_enabled() -> dict[str, bool]:
    return {"enabled": settings.github_oauth_enabled}


@router.get(
    "/oauth/providers",
    response_model=dict[str, bool],
    summary="Get enabled OAuth providers",
    description="Returns which OAuth providers are configured and available.",
)
async def oauth_providers() -> dict[str, bool]:
    return {
        "google": settings.google_oauth_enabled,
        "github": settings.github_oauth_enabled,
    }


@router.get(
    "/branding",
    response_model=BrandingRead,
    summary="Get branding settings",
    description="Public endpoint for logo URLs and accent color (no auth required).",
)
async def get_public_branding(db: DbSession) -> BrandingRead:
    """Get branding settings for public use (sign-in page, favicon, etc.)."""
    stmt = select(Branding).where(Branding.id == 1)
    result = await db.execute(stmt)
    branding = result.scalar_one_or_none()

    if not branding:
        # Return defaults if no branding configured
        return BrandingRead(
            logo_url=None,
            logo_square_url=None,
            favicon_url=None,
            accent_color="ink",
            accent_hex="#000000",
        )

    return BrandingRead(
        logo_url=branding.logo_url,
        logo_square_url=branding.logo_square_url,
        favicon_url=branding.favicon_url,
        accent_color=branding.accent_color,
        accent_hex=branding.accent_hex,
    )
