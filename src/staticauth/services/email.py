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

from staticauth.config import Settings, get_settings
from staticauth.models.email_suppression import EmailSuppression, SuppressionReason

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

    async def send_otp(self, to_email: str, otp_code: str, purpose: str = "sign in") -> bool:
        subject = f"{self.settings.app_name} - Your verification code"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .code {{ font-size: 32px; font-weight: bold; letter-spacing: 4px; color: #1a1a1a; padding: 20px; background: #f5f5f5; border-radius: 8px; text-align: center; margin: 20px 0; }}
                .footer {{ color: #666; font-size: 14px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>{self.settings.app_name}</h2>
                <p>Use the following code to {purpose}:</p>
                <div class="code">{otp_code}</div>
                <p>This code will expire in {self.settings.otp_expiry_minutes} minutes.</p>
                <div class="footer">
                    <p>If you didn't request this code, you can safely ignore this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name}

Your verification code to {purpose} is: {otp_code}

This code will expire in {self.settings.otp_expiry_minutes} minutes.

If you didn't request this code, you can safely ignore this email.
        """
        return await self._send_with_suppression_check(to_email, subject, html_body, text_body)

    async def send_registration_pending(self, to_email: str) -> bool:
        subject = f"{self.settings.app_name} - Registration pending approval"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>{self.settings.app_name}</h2>
                <p>Your registration is pending approval.</p>
                <p>An administrator will review your request and you'll receive an email once your account is approved.</p>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name}

Your registration is pending approval.

An administrator will review your request and you'll receive an email once your account is approved.
        """
        return await self._send_with_suppression_check(to_email, subject, html_body, text_body)

    async def send_registration_approved(self, to_email: str) -> bool:
        subject = f"{self.settings.app_name} - Registration approved"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #1a1a1a; color: #ffffff !important; text-decoration: none; border-radius: 6px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>{self.settings.app_name}</h2>
                <p>Great news! Your registration has been approved.</p>
                <p>You can now sign in to your account.</p>
                <a href="{self.settings.frontend_url}/signin" class="button">Sign In</a>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name}

Great news! Your registration has been approved.

You can now sign in to your account at {self.settings.frontend_url}/signin
        """
        return await self._send_with_suppression_check(to_email, subject, html_body, text_body)

    async def send_pending_registration_notification(
        self, admin_email: str, pending_user_email: str
    ) -> bool:
        """Notify admin of a new pending registration."""
        subject = f"{self.settings.app_name} - New registration pending approval"
        admin_url = f"{self.settings.frontend_url}/admin"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .email-box {{ background: #f5f5f5; padding: 12px 16px; border-radius: 6px; margin: 16px 0; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #1a1a1a; color: #ffffff !important; text-decoration: none; border-radius: 6px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>{self.settings.app_name}</h2>
                <p>A new user has registered and is waiting for approval:</p>
                <div class="email-box"><strong>{pending_user_email}</strong></div>
                <p>Please review this request in the admin panel.</p>
                <a href="{admin_url}" class="button">Review Pending Registrations</a>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name}

A new user has registered and is waiting for approval:

{pending_user_email}

Please review this request in the admin panel: {admin_url}
        """
        return await self._send_with_suppression_check(admin_email, subject, html_body, text_body)

    async def send_invitation(self, to_email: str, invited_by: str) -> bool:
        """Send invitation email when admin creates a user."""
        subject = f"You've been invited to {self.settings.app_name}"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #1a1a1a; color: #ffffff !important; text-decoration: none; border-radius: 6px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>{self.settings.app_name}</h2>
                <p>You've been invited to {self.settings.app_name} by <strong>{invited_by}</strong>.</p>
                <p>Your account has been created and you can sign in using your email address.</p>
                <a href="{self.settings.frontend_url}/signin" class="button">Sign In</a>
            </div>
        </body>
        </html>
        """
        text_body = f"""
{self.settings.app_name}

You've been invited to {self.settings.app_name} by {invited_by}.

Your account has been created and you can sign in using your email address.

Sign in at: {self.settings.frontend_url}/signin
        """
        return await self._send_with_suppression_check(to_email, subject, html_body, text_body)
