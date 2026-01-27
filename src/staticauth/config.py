from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App Config
    app_name: str = "StaticAuth"
    app_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:4321"
    secret_key: str = Field(min_length=32)

    # Database
    database_url: str = "sqlite+aiosqlite:///./staticauth.db"

    # Email - Common
    email_provider: Literal["ses", "smtp"] = "ses"
    email_from_name: str = "StaticAuth"

    # Email - SES
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    ses_from_email: str = ""

    # Email - SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    # Auth Config
    accepted_domains: str = ""
    otp_expiry_minutes: int = 10
    session_expiry_days: int = 30
    cookie_domain: str | None = None  # e.g., "engg.artpark.ai" for production

    # WebAuthn
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "StaticAuth"
    webauthn_origin: str = "http://localhost:4321"

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_reload: bool = True

    @computed_field
    @property
    def accepted_domains_list(self) -> list[str]:
        if not self.accepted_domains:
            return []
        return [d.strip().lower() for d in self.accepted_domains.split(",") if d.strip()]

    @computed_field
    @property
    def from_email(self) -> str:
        if self.email_provider == "ses":
            return self.ses_from_email
        return self.smtp_from_email

    def is_accepted_domain(self, email: str) -> bool:
        if not self.accepted_domains_list:
            return False
        domain = email.split("@")[-1].lower()
        return domain in self.accepted_domains_list


@lru_cache
def get_settings() -> Settings:
    return Settings()
