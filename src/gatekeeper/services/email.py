import logging
import uuid
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.config import Settings, get_settings
from gatekeeper.models.email_suppression import EmailSuppression, SuppressionReason

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> bool:
        pass


class SESProvider(EmailProvider):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = boto3.client(
            "ses",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> bool:
        try:
            from_address = (
                f"{self.settings.email_from_name} <{self.settings.ses_from_email}>"
                if self.settings.email_from_name
                else self.settings.ses_from_email
            )

            body = {"Html": {"Charset": "UTF-8", "Data": html_body}}
            if text_body:
                body["Text"] = {"Charset": "UTF-8", "Data": text_body}

            self.client.send_email(
                Source=from_address,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Charset": "UTF-8", "Data": subject},
                    "Body": body,
                },
            )
            logger.info(f"Email sent successfully via SES to {to_email}")
            return True
        except ClientError as e:
            logger.error(f"Failed to send email via SES: {e}")
            return False


class SMTPProvider(EmailProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> bool:
        try:
            from_address = (
                f"{self.settings.email_from_name} <{self.settings.smtp_from_email}>"
                if self.settings.email_from_name
                else self.settings.smtp_from_email
            )

            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = from_address
            message["To"] = to_email

            if text_body:
                message.attach(MIMEText(text_body, "plain"))
            message.attach(MIMEText(html_body, "html"))

            await aiosmtplib.send(
                message,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_user,
                password=self.settings.smtp_password,
                start_tls=True,
            )
            logger.info(f"Email sent successfully via SMTP to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SMTP: {e}")
            return False


class EmailService:
    def __init__(self, settings: Settings | None = None, db: AsyncSession | None = None):
        self.settings = settings or get_settings()
        self.db = db
        self.provider: EmailProvider

        if self.settings.email_provider == "ses":
            self.provider = SESProvider(self.settings)
        else:
            self.provider = SMTPProvider(self.settings)

    async def is_suppressed(self, email: str) -> bool:
        """Check if an email is on the suppression list."""
        if not self.db:
            return False
        stmt = select(EmailSuppression).where(EmailSuppression.email == email.lower())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add_suppression(
        self, email: str, reason: SuppressionReason, details: str | None = None
    ) -> None:
        """Add an email to the suppression list."""
        if not self.db:
            logger.warning(f"Cannot add suppression for {email}: no database session")
            return
        suppression = EmailSuppression(
            id=uuid.uuid4(),
            email=email.lower(),
            reason=reason,
            details=details,
        )
        self.db.add(suppression)
        await self.db.flush()
        logger.info(f"Added {email} to suppression list: {reason.value}")

    async def _send_with_suppression_check(
        self, to_email: str, subject: str, html_body: str, text_body: str | None = None
    ) -> bool:
        """Send email with suppression check."""
        if await self.is_suppressed(to_email):
            logger.warning(f"Email to {to_email} blocked: address is suppressed")
            return False
        return await self.provider.send_email(to_email, subject, html_body, text_body)

    def _base_styles(self) -> str:
        """Brutalist email styles matching the app design system."""
        return """
            body {
                font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
                background-color: #ffffff;
                color: #000000;
                line-height: 1.6;
                margin: 0;
                padding: 0;
            }
            .container {
                max-width: 560px;
                margin: 0 auto;
                padding: 32px 24px;
            }
            .header {
                font-size: 14px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 2px;
                border-bottom: 4px solid #000000;
                padding-bottom: 16px;
                margin-bottom: 32px;
            }
            .content {
                font-size: 14px;
            }
            .code-box {
                font-size: 32px;
                font-weight: 700;
                letter-spacing: 8px;
                text-align: center;
                padding: 24px;
                border: 4px solid #000000;
                margin: 24px 0;
                background: #ffffff;
            }
            .button {
                display: inline-block;
                padding: 16px 32px;
                background: #000000;
                color: #ffffff !important;
                text-decoration: none;
                font-size: 12px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1px;
                border: none;
                margin: 24px 0;
            }
            .info-box {
                border: 4px solid #000000;
                padding: 16px;
                margin: 24px 0;
            }
            .info-box-header {
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #666666;
                margin-bottom: 8px;
            }
            .divider {
                border-top: 2px solid #e5e5e5;
                margin: 32px 0;
            }
            .footer {
                font-size: 12px;
                color: #666666;
                margin-top: 32px;
            }
            .highlight {
                font-weight: 700;
            }
            ul {
                margin: 8px 0;
                padding-left: 20px;
            }
            li {
                margin: 4px 0;
            }
        """

    async def send_otp(self, to_email: str, otp_code: str, purpose: str = "sign in") -> bool:
        subject = f"{self.settings.app_name} — VERIFICATION CODE"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>{self._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header">{self.settings.app_name}</div>
                <div class="content">
                    <p>Use this code to {purpose}:</p>
                    <div class="code-box">{otp_code}</div>
                    <p>Expires in <span class="highlight">{self.settings.otp_expiry_minutes} minutes</span>.</p>
                </div>
                <div class="footer">
                    <p>If you didn't request this code, ignore this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name.upper()}

VERIFICATION CODE: {otp_code}

Use this code to {purpose}.
Expires in {self.settings.otp_expiry_minutes} minutes.

If you didn't request this code, ignore this email.
        """
        return await self._send_with_suppression_check(to_email, subject, html_body, text_body)

    async def send_registration_pending(self, to_email: str) -> bool:
        subject = f"{self.settings.app_name} — REGISTRATION PENDING"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>{self._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header">{self.settings.app_name}</div>
                <div class="content">
                    <div class="info-box">
                        <div class="info-box-header">Status</div>
                        <span class="highlight">PENDING APPROVAL</span>
                    </div>
                    <p>Your registration is awaiting admin review.</p>
                    <p>You'll receive an email once your account is approved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name.upper()}

STATUS: PENDING APPROVAL

Your registration is awaiting admin review.
You'll receive an email once your account is approved.
        """
        return await self._send_with_suppression_check(to_email, subject, html_body, text_body)

    async def send_registration_approved(self, to_email: str) -> bool:
        subject = f"{self.settings.app_name} — ACCESS GRANTED"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>{self._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header">{self.settings.app_name}</div>
                <div class="content">
                    <div class="info-box">
                        <div class="info-box-header">Status</div>
                        <span class="highlight">APPROVED</span>
                    </div>
                    <p>Your registration has been approved.</p>
                    <p>You can now sign in to your account.</p>
                    <a href="{self.settings.frontend_url}/signin" class="button">Sign In</a>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name.upper()}

STATUS: APPROVED

Your registration has been approved.
Sign in at: {self.settings.frontend_url}/signin
        """
        return await self._send_with_suppression_check(to_email, subject, html_body, text_body)

    async def send_pending_registration_notification(
        self, admin_email: str, pending_user_email: str
    ) -> bool:
        """Notify admin of a new pending registration."""
        subject = f"{self.settings.app_name} — NEW REGISTRATION"
        admin_url = f"{self.settings.frontend_url}/admin"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>{self._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header">{self.settings.app_name}</div>
                <div class="content">
                    <p>A new user is waiting for approval:</p>
                    <div class="info-box">
                        <div class="info-box-header">User</div>
                        <span class="highlight">{pending_user_email}</span>
                    </div>
                    <a href="{admin_url}" class="button">Review in Admin Panel</a>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name.upper()}

NEW REGISTRATION PENDING

User: {pending_user_email}

Review in admin panel: {admin_url}
        """
        return await self._send_with_suppression_check(admin_email, subject, html_body, text_body)

    async def send_new_user_notification(
        self, admin_email: str, new_user_email: str, is_auto_approved: bool
    ) -> bool:
        """Notify admin of any new user registration (including auto-approved)."""
        status = "AUTO-APPROVED" if is_auto_approved else "PENDING"
        subject = f"{self.settings.app_name} — NEW USER: {status}"
        admin_url = f"{self.settings.frontend_url}/admin"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>{self._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header">{self.settings.app_name}</div>
                <div class="content">
                    <p>A new user has registered:</p>
                    <div class="info-box">
                        <div class="info-box-header">User</div>
                        <span class="highlight">{new_user_email}</span>
                    </div>
                    <div class="info-box">
                        <div class="info-box-header">Status</div>
                        <span class="highlight">{status}</span>
                    </div>
                    <a href="{admin_url}" class="button">View in Admin Panel</a>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name.upper()}

NEW USER REGISTERED

User: {new_user_email}
Status: {status}

View in admin panel: {admin_url}
        """
        return await self._send_with_suppression_check(admin_email, subject, html_body, text_body)

    async def send_super_admin_welcome(self, to_email: str, invited_by: str) -> bool:
        """Send welcome email when a super admin account is created."""
        subject = f"{self.settings.app_name} — SUPER ADMIN ACCESS"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>{self._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header">{self.settings.app_name}</div>
                <div class="content">
                    <div class="info-box">
                        <div class="info-box-header">Role</div>
                        <span class="highlight">SUPER ADMIN</span>
                    </div>
                    <p><span class="highlight">{invited_by}</span> added you as a Super Admin.</p>
                    <a href="{self.settings.frontend_url}/signin" class="button">Sign In</a>

                    <div class="divider"></div>

                    <div class="info-box-header">What is {self.settings.app_name}?</div>
                    <p>A centralized authentication platform for single sign-on access to multiple applications.</p>

                    <div class="info-box-header" style="margin-top: 16px;">Super Admin Capabilities</div>
                    <ul>
                        <li>Create and manage user accounts</li>
                        <li>Create and configure applications</li>
                        <li>Grant or revoke user access</li>
                        <li>Review and approve requests</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name.upper()}

ROLE: SUPER ADMIN

{invited_by} added you as a Super Admin.

Sign in: {self.settings.frontend_url}/signin

---

WHAT IS {self.settings.app_name.upper()}?
A centralized authentication platform for single sign-on access to multiple applications.

SUPER ADMIN CAPABILITIES:
- Create and manage user accounts
- Create and configure applications
- Grant or revoke user access
- Review and approve requests
        """
        return await self._send_with_suppression_check(to_email, subject, html_body, text_body)

    async def send_app_access_granted(
        self,
        to_email: str,
        app_name: str,
        app_description: str | None,
        app_url: str | None,
        granted_by: str,
    ) -> bool:
        """Send email when a user is granted access to an app."""
        subject = f"{self.settings.app_name} — APP ACCESS GRANTED"

        description_html = ""
        description_text = ""
        if app_description:
            description_html = f'<p style="margin-top: 8px;">{app_description}</p>'
            description_text = f"\n{app_description}\n"

        if app_url:
            button_html = f'<a href="{app_url}" class="button">Open {app_name}</a>'
            button_text = f"Open: {app_url}"
        else:
            button_html = (
                f'<a href="{self.settings.frontend_url}" class="button">'
                f"Go to {self.settings.app_name}</a>"
            )
            button_text = f"Sign in: {self.settings.frontend_url}"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>{self._base_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="header">{self.settings.app_name}</div>
                <div class="content">
                    <p>You've been granted access by <span class="highlight">{granted_by}</span>.</p>
                    <div class="info-box">
                        <div class="info-box-header">Application</div>
                        <span class="highlight">{app_name}</span>
                        {description_html}
                    </div>
                    {button_html}
                </div>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name.upper()}

APP ACCESS GRANTED

Application: {app_name}
Granted by: {granted_by}
{description_text}
{button_text}
        """
        return await self._send_with_suppression_check(to_email, subject, html_body, text_body)
