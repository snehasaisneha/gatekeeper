import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gatekeeper.database import Base
from gatekeeper.models.otp import OTP, OTPPurpose
from gatekeeper.models.user import User, UserStatus


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary database file path."""
    return tmp_path / "test.db"


@pytest_asyncio.fixture
async def test_engine(test_db_path):
    """Create a test database engine."""
    db_url = f"sqlite+aiosqlite:///{test_db_path}"
    engine = create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_engine, test_session, test_db_path) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with mocked dependencies."""
    from gatekeeper.api.deps import get_db
    from gatekeeper.config import Settings, get_settings
    from gatekeeper.main import app
    from gatekeeper.rate_limit import limiter

    # Create test settings with the temp database
    db_url = f"sqlite+aiosqlite:///{test_db_path}"
    test_settings = Settings(
        secret_key="test-secret-key-that-is-at-least-32-characters-long",
        database_url=db_url,
        accepted_domains="approved-domain.com,test.com",
        otp_expiry_minutes=5,
        email_provider="smtp",
        smtp_host="localhost",
        smtp_port=1025,
        smtp_from_email="test@test.com",
        app_url="http://localhost:8000",
        frontend_url="http://localhost:4321",
        webauthn_rp_id="localhost",
        webauthn_origin="http://localhost:4321",
    )

    # Override dependencies
    async def override_get_db():
        from fastapi import HTTPException

        async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except HTTPException:
                # HTTPException is a normal response flow, still commit
                await session.commit()
                raise
            except Exception:
                await session.rollback()
                raise

    def override_get_settings():
        return test_settings

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings

    # Disable rate limiting for tests
    limiter.enabled = False

    # Also patch get_settings at module level for services and auth
    patches = [
        patch("gatekeeper.config.get_settings", return_value=test_settings),
        patch("gatekeeper.services.otp.get_settings", return_value=test_settings),
        patch("gatekeeper.api.v1.auth.settings", test_settings),
        patch(
            "gatekeeper.services.email.EmailService.send_otp",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "gatekeeper.services.email.EmailService.send_registration_pending",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "gatekeeper.services.email.EmailService.send_pending_registration_notification",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ]
    for p in patches:
        p.start()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        for p in patches:
            p.stop()

    # Re-enable rate limiting after tests
    limiter.enabled = True
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for direct DB access in tests.

    This session shares the same engine as the API, so committed
    transactions will be visible after calling commit().
    """
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


async def get_latest_otp(
    db_session: AsyncSession, email: str, purpose: OTPPurpose = OTPPurpose.REGISTER
) -> str | None:
    """Get the latest OTP code for an email."""
    # Commit any pending changes and start fresh transaction to see external commits
    await db_session.commit()
    stmt = (
        select(OTP)
        .where(OTP.email == email.lower(), OTP.purpose == purpose)
        .order_by(OTP.created_at.desc())
        .limit(1)
    )
    result = await db_session.execute(stmt)
    otp = result.scalar_one_or_none()
    return otp.code if otp else None


async def create_test_user(
    db_session: AsyncSession,
    email: str,
    status: UserStatus = UserStatus.APPROVED,
    is_admin: bool = False,
) -> User:
    """Create a test user directly in the database."""
    user = User(
        email=email.lower(),
        status=status,
        is_admin=is_admin,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def create_test_otp(
    db_session: AsyncSession,
    email: str,
    code: str = "123456",
    purpose: OTPPurpose = OTPPurpose.SIGNIN,
    expired: bool = False,
    used: bool = False,
) -> OTP:
    """Create a test OTP directly in the database."""
    if expired:
        expires_at = datetime.now(UTC) - timedelta(minutes=1)
    else:
        expires_at = datetime.now(UTC) + timedelta(minutes=5)

    otp = OTP(
        email=email.lower(),
        code=code,
        purpose=purpose,
        expires_at=expires_at,
        used=used,
    )
    db_session.add(otp)
    await db_session.commit()
    await db_session.refresh(otp)
    return otp
