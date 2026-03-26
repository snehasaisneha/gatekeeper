from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App Config
    app_name: str = "Gatekeeper"
    app_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:4321"
    secret_key: str = Field(min_length=32)

    # Database
    database_url: str = "sqlite+aiosqlite:///./gatekeeper.db"

    # Email - Common
    email_provider: Literal["ses", "smtp"] = "ses"
    email_from_name: str = "Gatekeeper"

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
    otp_expiry_minutes: int = 5
    session_expiry_days: int = 30
    cookie_domain: str | None = None  # e.g., ".example.com" for multi-app SSO
    otp_send_limit_per_email_ip: int = 3
    otp_verify_fail_limit_per_email_ip: int = 8
    auth_failure_window_minutes: int = 15
    auto_ip_ban_failure_threshold: int = 10
    auto_ip_ban_duration_hours: int = 1

    # Multi-App Config
    # "allow" = unregistered apps allow any authenticated user
    # "deny" = unregistered apps return 403
    default_app_access: Literal["allow", "deny"] = "allow"

    # WebAuthn
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Gatekeeper"
    webauthn_origin: str = "http://localhost:4321"

    # OAuth - Google
    google_client_id: str = ""
    google_client_secret: str = ""

    @computed_field
    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    # OAuth - GitHub
    github_client_id: str = ""
    github_client_secret: str = ""

    @computed_field
    @property
    def github_oauth_enabled(self) -> bool:
        return bool(self.github_client_id and self.github_client_secret)

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_reload: bool = True
    public_api_docs: bool = False
    trusted_proxy_ips: str = "127.0.0.1,::1"

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

    @computed_field
    @property
    def trusted_proxy_ips_list(self) -> list[str]:
        if not self.trusted_proxy_ips:
            return []
        return [ip.strip() for ip in self.trusted_proxy_ips.split(",") if ip.strip()]

    def is_accepted_domain(self, email: str) -> bool:
        if not self.accepted_domains_list:
            return False
        domain = email.split("@")[-1].lower()
        return domain in self.accepted_domains_list

    @computed_field
    @property
    def cors_origin_regex(self) -> str:
        hosts: set[str] = set()
        for candidate in (self.app_url, self.frontend_url):
            hostname = urlparse(candidate).hostname
            if hostname:
                hosts.add(hostname)

        if self.cookie_domain:
            base_domain = self.cookie_domain.lstrip(".")
            if base_domain:
                escaped = base_domain.replace(".", r"\.")
                return rf"^https?://([a-zA-Z0-9-]+\.)*{escaped}(:\d+)?$"

        for host in list(hosts):
            parts = host.split(".")
            if len(parts) >= 2 and host not in {"localhost", "127.0.0.1"}:
                base_domain = ".".join(parts[-2:])
                escaped = base_domain.replace(".", r"\.")
                return rf"^https?://([a-zA-Z0-9-]+\.)*{escaped}(:\d+)?$"

        return r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


@lru_cache
def get_settings() -> Settings:
    return Settings()
