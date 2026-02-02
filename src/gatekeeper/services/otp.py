import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.config import Settings, get_settings
from gatekeeper.models.otp import MAX_OTP_ATTEMPTS, OTP, OTPPurpose
from gatekeeper.services.email import EmailService


class OTPService:
    def __init__(self, db: AsyncSession, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()
        self.email_service = EmailService(self.settings)

    def _generate_code(self) -> str:
        return "".join(secrets.choice("0123456789") for _ in range(6))

    async def create_and_send(self, email: str, purpose: OTPPurpose) -> bool:
        email = email.lower()

        await self._invalidate_previous(email, purpose)

        code = self._generate_code()
        expires_at = datetime.now(UTC) + timedelta(minutes=self.settings.otp_expiry_minutes)

        otp = OTP(
            email=email,
            code=code,
            purpose=purpose,
            expires_at=expires_at,
        )
        self.db.add(otp)
        await self.db.flush()

        purpose_text = "sign in" if purpose == OTPPurpose.SIGNIN else "register"
        return await self.email_service.send_otp(email, code, purpose_text)

    async def verify(self, email: str, code: str, purpose: OTPPurpose) -> tuple[bool, str | None]:
        """
        Verify an OTP code.

        Returns:
            tuple: (success, error_message)
            - (True, None) on success
            - (False, "error message") on failure
        """
        email = email.lower()

        # Find the most recent unused, unexpired OTP for this email/purpose
        stmt = (
            select(OTP)
            .where(
                OTP.email == email,
                OTP.purpose == purpose,
                OTP.used == False,  # noqa: E712
                OTP.expires_at > datetime.now(UTC),
            )
            .order_by(OTP.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        otp = result.scalar_one_or_none()

        if not otp:
            return False, "Invalid or expired code. Please request a new one."

        # Check if max attempts exceeded
        if otp.attempts >= MAX_OTP_ATTEMPTS:
            return False, "Too many failed attempts. Please request a new code."

        # Check if code matches
        if otp.code != code:
            otp.attempts += 1
            await self.db.flush()
            remaining = MAX_OTP_ATTEMPTS - otp.attempts
            if remaining <= 0:
                return False, "Too many failed attempts. Please request a new code."
            return False, f"Invalid code. {remaining} attempt(s) remaining."

        # Success - mark as used
        otp.used = True
        await self.db.flush()
        return True, None

    async def _invalidate_previous(self, email: str, purpose: OTPPurpose) -> None:
        stmt = select(OTP).where(
            OTP.email == email,
            OTP.purpose == purpose,
            OTP.used == False,  # noqa: E712
        )
        result = await self.db.execute(stmt)
        otps = result.scalars().all()

        for otp in otps:
            otp.used = True
        await self.db.flush()
