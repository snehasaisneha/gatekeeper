from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from gatekeeper.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()


async def seed_approved_domains(session: AsyncSession) -> None:
    """Seed approved_domains table from ACCEPTED_DOMAINS env var."""
    from gatekeeper.models.domain import ApprovedDomain

    domains_to_seed = settings.accepted_domains_list
    if not domains_to_seed:
        return

    for domain in domains_to_seed:
        stmt = select(ApprovedDomain).where(ApprovedDomain.domain == domain)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            new_domain = ApprovedDomain(domain=domain, created_by="system:seed")
            session.add(new_domain)

    await session.commit()


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
    """Initialize database connection and seed data.

    Note: Tables are created via migrations, not auto-generated.
    Run `uv run python -m gatekeeper.db.migrate` to apply migrations.
    """
    # Verify connection works
    async with engine.begin():
        pass

    # Seed approved_domains from ACCEPTED_DOMAINS env var
    async with async_session_maker() as session:
        await seed_approved_domains(session)
