import hashlib
import secrets
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.models.app import App, AppApiKey
from gatekeeper.models.user import User


class AppApiKeyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _generate_raw_key() -> tuple[str, str]:
        prefix = f"gka_{secrets.token_hex(4)}"
        secret = secrets.token_urlsafe(24)
        return prefix, f"{prefix}.{secret}"

    async def create_key(
        self,
        *,
        app: App,
        name: str,
        created_by: User | None = None,
        created_by_email: str | None = None,
    ) -> tuple[AppApiKey, str]:
        prefix, raw_key = self._generate_raw_key()
        api_key = AppApiKey(
            app_id=app.id,
            name=name,
            key_prefix=prefix,
            key_hash=self._hash_key(raw_key),
            created_by_user_id=created_by.id if created_by else None,
            created_by_email=created_by.email if created_by else created_by_email,
        )
        self.db.add(api_key)
        await self.db.flush()
        await self.db.refresh(api_key)
        return api_key, raw_key

    async def resolve_key(self, raw_key: str) -> AppApiKey | None:
        if "." not in raw_key:
            return None
        prefix = raw_key.split(".", 1)[0]
        stmt = select(AppApiKey).where(
            AppApiKey.key_prefix == prefix,
            AppApiKey.revoked_at.is_(None),
        )
        result = await self.db.execute(stmt)
        api_key = result.scalar_one_or_none()
        if not api_key:
            return None
        if api_key.key_hash != self._hash_key(raw_key):
            return None
        api_key.last_used_at = datetime.utcnow()
        await self.db.flush()
        return api_key
