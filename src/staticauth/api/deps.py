from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from staticauth.database import get_db
from staticauth.models.user import User, UserStatus
from staticauth.services.session import SessionService
from staticauth.utils.security import verify_signed_token


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[str | None, Cookie()] = None,
) -> User:
    print(f"[AUTH DEBUG] session cookie received: {session[:20] if session else None}...")
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = verify_signed_token(session)
    print(f"[AUTH DEBUG] token after verify: {token[:20] if token else None}...")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    session_service = SessionService(db)
    user = await session_service.get_user_by_token(token)
    print(f"[AUTH DEBUG] user from db: {user}")

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    if user.status != UserStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not approved",
        )

    return user


async def get_current_user_optional(
    db: Annotated[AsyncSession, Depends(get_db)],
    session: Annotated[str | None, Cookie()] = None,
) -> User | None:
    if not session:
        return None

    token = verify_signed_token(session)
    if not token:
        return None

    session_service = SessionService(db)
    user = await session_service.get_user_by_token(token)

    if not user or user.status != UserStatus.APPROVED:
        return None

    return user


async def get_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]
AdminUser = Annotated[User, Depends(get_admin_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
