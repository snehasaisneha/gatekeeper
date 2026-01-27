import base64
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Response, status
from sqlalchemy import select

from staticauth.api.deps import CurrentUser, DbSession
from staticauth.config import get_settings
from staticauth.models.otp import OTPPurpose
from staticauth.models.user import User, UserStatus
from staticauth.schemas.auth import (
    AuthResponse,
    ErrorResponse,
    MessageResponse,
    OTPRequest,
    OTPVerifyRequest,
    PasskeyInfo,
    PasskeyOptionsRequest,
    PasskeyVerifyRequest,
    UserResponse,
)
from staticauth.services.email import EmailService
from staticauth.services.otp import OTPService
from staticauth.services.passkey import PasskeyService
from staticauth.services.session import SessionService
from staticauth.utils.security import create_signed_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

settings = get_settings()

COOKIE_NAME = "session"
COOKIE_MAX_AGE = settings.session_expiry_days * 24 * 60 * 60


def set_session_cookie(response: Response, token: str) -> None:
    signed_token = create_signed_token(token)
    print(f"[COOKIE DEBUG] domain={settings.cookie_domain!r}, secure={settings.app_url.startswith('https')}, app_url={settings.app_url}")
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


@router.post(
    "/register",
    response_model=MessageResponse,
    responses={
        200: {"description": "OTP sent successfully"},
        400: {"model": ErrorResponse, "description": "Email already registered"},
    },
    summary="Start registration",
    description="Send an OTP to the provided email address to start registration.",
)
async def register(request: OTPRequest, db: DbSession) -> MessageResponse:
    email = request.email.lower()

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
    },
    summary="Complete registration",
    description="Verify the OTP and complete registration. Auto-approves if email domain is in accepted domains.",
)
async def register_verify(
    request: OTPVerifyRequest,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    email = request.email.lower()

    otp_service = OTPService(db)
    if not await otp_service.verify(email, request.code, OTPPurpose.REGISTER):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code.",
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
        email_service = EmailService()
        await email_service.send_registration_pending(email)

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
    },
    summary="Start sign-in",
    description="Send an OTP to the provided email address to start sign-in.",
)
async def signin(request: OTPRequest, db: DbSession) -> MessageResponse:
    email = request.email.lower()

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
    },
    summary="Complete sign-in",
    description="Verify the OTP and complete sign-in.",
)
async def signin_verify(
    request: OTPVerifyRequest,
    response: Response,
    db: DbSession,
) -> AuthResponse:
    email = request.email.lower()

    stmt = select(User).where(User.email == email, User.status == UserStatus.APPROVED)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No approved account found with this email.",
        )

    otp_service = OTPService(db)
    if not await otp_service.verify(email, request.code, OTPPurpose.SIGNIN):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code.",
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
        from staticauth.utils.security import verify_signed_token

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


@router.post(
    "/passkey/register/options",
    response_model=dict[str, Any],
    summary="Get passkey registration options",
    description="Get WebAuthn options for registering a new passkey. Requires authentication.",
)
async def passkey_register_options(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    passkey_service = PasskeyService(db)
    options = await passkey_service.generate_registration_options(current_user)
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
    passkey_service = PasskeyService(db)
    credential_dict = request.credential.model_dump()
    passkey = await passkey_service.verify_registration(current_user, credential_dict)

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
    summary="Get passkey sign-in options",
    description="Get WebAuthn options for signing in with a passkey.",
)
async def passkey_signin_options(
    request: PasskeyOptionsRequest,
    db: DbSession,
) -> dict[str, Any]:
    passkey_service = PasskeyService(db)
    options, challenge = await passkey_service.generate_authentication_options(request.email)

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
        )

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
        )

    passkey_service = PasskeyService(db)
    deleted = await passkey_service.delete_passkey(pk_uuid, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Passkey not found.",
        )

    return MessageResponse(message="Passkey deleted successfully")
