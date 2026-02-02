from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from gatekeeper.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    from fastapi import HTTPException

    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except HTTPException:
            # HTTPException is a normal response flow, still commit
            # This ensures OTP attempts are tracked even on failed verifications
            await session.commit()
            raise
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database connection.

    Note: Tables are created via migrations, not auto-generated.
    Run `uv run python -m gatekeeper.db.migrate` to apply migrations.
    """
    # Verify connection works
    async with engine.begin():
        pass
