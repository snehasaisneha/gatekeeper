import base64
import hashlib
import hmac

from gatekeeper.config import get_settings


def create_signed_token(token: str) -> str:
    settings = get_settings()
    signature = hmac.new(
        settings.secret_key.encode(),
        token.encode(),
        hashlib.sha256,
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{token}.{sig_b64}"


def verify_signed_token(signed_token: str) -> str | None:
    if "." not in signed_token:
        return None

    parts = signed_token.rsplit(".", 1)
    if len(parts) != 2:
        return None

    token, provided_sig = parts

    settings = get_settings()
    expected_signature = hmac.new(
        settings.secret_key.encode(),
        token.encode(),
        hashlib.sha256,
    ).digest()
    expected_sig_b64 = base64.urlsafe_b64encode(expected_signature).decode().rstrip("=")

    if hmac.compare_digest(provided_sig, expected_sig_b64):
        return token
    return None
