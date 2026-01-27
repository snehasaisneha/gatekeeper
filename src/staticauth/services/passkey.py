import base64
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from staticauth.config import Settings, get_settings
from staticauth.models.passkey import PasskeyCredential
from staticauth.models.user import User


class PasskeyService:
    def __init__(self, db: AsyncSession, settings: Settings | None = None):
        self.db = db
        self.settings = settings or get_settings()
        self._challenges: dict[str, bytes] = {}

    async def generate_registration_options(self, user: User) -> dict[str, Any]:
        existing_credentials = await self._get_user_credentials(user.id)

        exclude_credentials = [
            PublicKeyCredentialDescriptor(id=cred.credential_id)
            for cred in existing_credentials
        ]

        options = generate_registration_options(
            rp_id=self.settings.webauthn_rp_id,
            rp_name=self.settings.webauthn_rp_name,
            user_id=str(user.id).encode(),
            user_name=user.email,
            user_display_name=user.email,
            exclude_credentials=exclude_credentials,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
        )

        self._challenges[str(user.id)] = options.challenge

        return {
            "challenge": bytes_to_base64url(options.challenge),
            "rp": {"id": options.rp.id, "name": options.rp.name},
            "user": {
                "id": bytes_to_base64url(options.user.id),
                "name": options.user.name,
                "displayName": options.user.display_name,
            },
            "pubKeyCredParams": [
                {"type": p.type, "alg": p.alg} for p in options.pub_key_cred_params
            ],
            "timeout": options.timeout,
            "excludeCredentials": [
                {"type": "public-key", "id": bytes_to_base64url(c.id)}
                for c in (options.exclude_credentials or [])
            ],
            "authenticatorSelection": {
                "residentKey": options.authenticator_selection.resident_key
                if options.authenticator_selection
                else None,
                "userVerification": options.authenticator_selection.user_verification
                if options.authenticator_selection
                else None,
            },
            "attestation": options.attestation,
        }

    async def verify_registration(
        self, user: User, credential: dict[str, Any], name: str = "Passkey"
    ) -> PasskeyCredential | None:
        challenge = self._challenges.pop(str(user.id), None)
        if not challenge:
            return None

        try:
            verification = verify_registration_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=self.settings.webauthn_rp_id,
                expected_origin=self.settings.webauthn_origin,
            )

            transports = credential.get("response", {}).get("transports", [])

            passkey = PasskeyCredential(
                user_id=user.id,
                credential_id=verification.credential_id,
                public_key=verification.credential_public_key,
                sign_count=verification.sign_count,
                name=name,
            )
            passkey.transports_list = transports

            self.db.add(passkey)
            await self.db.flush()
            return passkey
        except Exception:
            return None

    async def generate_authentication_options(
        self, email: str | None = None
    ) -> tuple[dict[str, Any], bytes]:
        allow_credentials = []

        if email:
            user = await self._get_user_by_email(email)
            if user:
                credentials = await self._get_user_credentials(user.id)
                allow_credentials = [
                    PublicKeyCredentialDescriptor(
                        id=cred.credential_id,
                        transports=cred.transports_list if cred.transports else None,
                    )
                    for cred in credentials
                ]

        options = generate_authentication_options(
            rp_id=self.settings.webauthn_rp_id,
            allow_credentials=allow_credentials if allow_credentials else None,
            user_verification=UserVerificationRequirement.PREFERRED,
        )

        return (
            {
                "challenge": bytes_to_base64url(options.challenge),
                "timeout": options.timeout,
                "rpId": options.rp_id,
                "allowCredentials": [
                    {
                        "type": "public-key",
                        "id": bytes_to_base64url(c.id),
                        "transports": c.transports,
                    }
                    for c in (options.allow_credentials or [])
                ],
                "userVerification": options.user_verification,
            },
            options.challenge,
        )

    async def verify_authentication(
        self, credential: dict[str, Any], challenge: bytes
    ) -> User | None:
        try:
            raw_id = credential.get("rawId") or credential.get("id")
            if not raw_id:
                print("[PASSKEY] No rawId or id in credential")
                return None

            credential_id = base64.urlsafe_b64decode(raw_id + "==")

            passkey = await self._get_credential_by_id(credential_id)
            if not passkey:
                print("[PASSKEY] No passkey found for credential_id")
                return None

            verification = verify_authentication_response(
                credential=credential,
                expected_challenge=challenge,
                expected_rp_id=self.settings.webauthn_rp_id,
                expected_origin=self.settings.webauthn_origin,
                credential_public_key=passkey.public_key,
                credential_current_sign_count=passkey.sign_count,
            )

            passkey.sign_count = verification.new_sign_count
            await self.db.flush()

            stmt = select(User).where(User.id == passkey.user_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            print(f"[PASSKEY] verify_authentication error: {e}")
            return None

    async def _get_user_credentials(self, user_id: uuid.UUID) -> list[PasskeyCredential]:
        stmt = select(PasskeyCredential).where(PasskeyCredential.user_id == user_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_credential_by_id(self, credential_id: bytes) -> PasskeyCredential | None:
        stmt = select(PasskeyCredential).where(PasskeyCredential.credential_id == credential_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_passkey(self, passkey_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        stmt = select(PasskeyCredential).where(
            PasskeyCredential.id == passkey_id,
            PasskeyCredential.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        passkey = result.scalar_one_or_none()

        if not passkey:
            return False

        await self.db.delete(passkey)
        await self.db.flush()
        return True

    async def list_passkeys(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        credentials = await self._get_user_credentials(user_id)
        return [
            {
                "id": str(cred.id),
                "name": cred.name,
                "created_at": cred.created_at.isoformat(),
            }
            for cred in credentials
        ]
