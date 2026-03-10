from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from gatekeeper.models.audit import AuditLog
from gatekeeper.models.otp import OTPPurpose
from gatekeeper.models.security import BannedEmail, BannedIP, BanReason
from gatekeeper.models.session import Session
from gatekeeper.models.user import UserStatus

from .conftest import create_test_otp, create_test_user, get_latest_otp


class TestSignIn:
    """Tests for the sign-in flow (which now handles registration automatically)."""

    async def test_signin_approved_user(self, client: AsyncClient, db_session):
        """Test sign-in flow for an approved user."""
        # Create approved user
        await create_test_user(db_session, "signinuser@test.com", UserStatus.APPROVED)

        # Start sign-in
        response = await client.post(
            "/api/v1/auth/signin",
            json={"email": "signinuser@test.com"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Verification code sent"

        # Get OTP
        otp = await get_latest_otp(db_session, "signinuser@test.com", OTPPurpose.SIGNIN)
        assert otp is not None

        # Verify sign-in
        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": "signinuser@test.com", "code": otp},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "signinuser@test.com"
        assert "session" in response.cookies

    async def test_signin_auto_creates_user_from_approved_domain(
        self, client: AsyncClient, db_session
    ):
        """Test that sign-in auto-creates and approves users from approved domains."""
        email = "newuser@approved-domain.com"

        # Start sign-in (user doesn't exist yet)
        response = await client.post(
            "/api/v1/auth/signin",
            json={"email": email},
        )
        assert response.status_code == 200

        # Get OTP
        otp = await get_latest_otp(db_session, email, OTPPurpose.SIGNIN)
        assert otp is not None

        # Verify sign-in
        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": email, "code": otp},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"] is not None
        assert data["user"]["email"] == email
        assert "session" in response.cookies

    async def test_signin_records_session_metadata(self, client: AsyncClient, db_session):
        await create_test_user(db_session, "metadata@test.com", UserStatus.APPROVED)

        await client.post("/api/v1/auth/signin", json={"email": "metadata@test.com"})
        otp = await get_latest_otp(db_session, "metadata@test.com", OTPPurpose.SIGNIN)

        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": "metadata@test.com", "code": otp},
            headers={
                "user-agent": "MetadataBrowser/1.0",
                "x-forwarded-for": "203.0.113.10",
            },
        )
        assert response.status_code == 200

        session_result = await db_session.execute(
            select(Session).where(Session.auth_method == "otp")
        )
        session = session_result.scalar_one_or_none()
        assert session is not None
        assert session.ip_address == "203.0.113.10"
        assert session.user_agent == "MetadataBrowser/1.0"
        assert session.last_seen_at is not None

    async def test_signin_auto_creates_pending_user_from_unknown_domain(
        self, client: AsyncClient, db_session
    ):
        """Test that sign-in auto-creates pending users from non-approved domains."""
        email = "newuser@unknown-domain.com"

        # Start sign-in (user doesn't exist yet)
        response = await client.post(
            "/api/v1/auth/signin",
            json={"email": email},
        )
        assert response.status_code == 200

        # Get OTP
        otp = await get_latest_otp(db_session, email, OTPPurpose.SIGNIN)
        assert otp is not None

        # Verify sign-in
        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": email, "code": otp},
        )

        assert response.status_code == 200
        data = response.json()
        # Pending users don't get a user object or session
        assert data["user"] is None
        assert "pending" in data["message"].lower()
        assert "session" not in response.cookies

    async def test_signin_pending_user_sends_otp(self, client: AsyncClient, db_session):
        """Test that pending users can verify their email (but remain pending)."""
        await create_test_user(db_session, "pendingsignin@test.com", UserStatus.PENDING)

        # Pending users should be able to get an OTP
        response = await client.post(
            "/api/v1/auth/signin",
            json={"email": "pendingsignin@test.com"},
        )
        assert response.status_code == 200

        # Get OTP
        otp = await get_latest_otp(db_session, "pendingsignin@test.com", OTPPurpose.SIGNIN)
        assert otp is not None

        # Verify - should return pending status
        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": "pendingsignin@test.com", "code": otp},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user"] is None
        assert "pending" in data["message"].lower()

    async def test_signin_rejected_user_fails(self, client: AsyncClient, db_session):
        """Test that sign-in fails for rejected users."""
        await create_test_user(db_session, "rejectedsignin@test.com", UserStatus.REJECTED)

        response = await client.post(
            "/api/v1/auth/signin",
            json={"email": "rejectedsignin@test.com"},
        )

        assert response.status_code == 400
        assert "rejected" in response.json()["detail"].lower()

    async def test_signin_delivery_failure_is_audited_with_attempt_ip(
        self, client: AsyncClient, db_session
    ):
        """Test that undeliverable OTP attempts are captured for security review."""
        attempted_email = "typo-user@external-example.com"
        attempt_ip = "203.0.113.25"

        with patch(
            "gatekeeper.services.email.EmailService.send_otp",
            new=AsyncMock(return_value=False),
        ):
            response = await client.post(
                "/api/v1/auth/signin",
                json={"email": attempted_email},
                headers={"X-Forwarded-For": attempt_ip},
            )

        assert response.status_code == 500

        audit_stmt = select(AuditLog).where(
            AuditLog.actor_email == attempted_email,
            AuditLog.event_type == "auth.signin.failed",
        )
        audit_result = await db_session.execute(audit_stmt)
        audit_log = audit_result.scalar_one_or_none()
        assert audit_log is not None
        assert audit_log.ip_address == attempt_ip
        assert "otp_delivery_failed" in audit_log.details

    async def test_repeated_failed_signin_attempts_auto_ban_ip(
        self, client: AsyncClient, db_session
    ):
        """Test that repeated auth failures can trigger an automatic temporary IP ban."""
        attempt_ip = "203.0.113.26"
        attempted_email = "typo-user@external-example.com"

        with patch(
            "gatekeeper.services.email.EmailService.send_otp",
            new=AsyncMock(return_value=False),
        ):
            for _ in range(10):
                response = await client.post(
                    "/api/v1/auth/signin",
                    json={"email": attempted_email},
                    headers={"X-Forwarded-For": attempt_ip},
                )
                assert response.status_code == 500

        banned_ip_stmt = select(BannedIP).where(BannedIP.ip_address == attempt_ip)
        banned_ip_result = await db_session.execute(banned_ip_stmt)
        banned_ip = banned_ip_result.scalar_one_or_none()
        assert banned_ip is not None
        assert banned_ip.reason == BanReason.RATE_LIMIT.value
        assert banned_ip.expires_at is not None
        assert banned_ip.expires_at > datetime.utcnow()

        blocked_response = await client.post(
            "/api/v1/auth/signin",
            json={"email": attempted_email},
            headers={"X-Forwarded-For": attempt_ip},
        )
        assert blocked_response.status_code == 403


class TestOTPExpiry:
    """Tests for OTP expiry handling."""

    async def test_expired_otp_rejected(self, client: AsyncClient, db_session):
        """Test that expired OTPs are rejected."""
        email = "expiredotp@test.com"
        await create_test_user(db_session, email, UserStatus.APPROVED)

        # Create an expired OTP directly in the database
        await create_test_otp(
            db_session,
            email,
            code="654321",
            purpose=OTPPurpose.SIGNIN,
            expired=True,
        )

        # Try to verify with expired OTP
        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": email, "code": "654321"},
        )

        assert response.status_code == 400
        detail = response.json()["detail"].lower()
        assert "invalid" in detail or "expired" in detail


class TestOTPAttempts:
    """Tests for OTP attempt limiting."""

    async def test_max_attempts_exceeded(self, client: AsyncClient, db_session):
        """Test that OTP is invalidated after 5 failed attempts."""
        email = "attempttest@test.com"
        await create_test_user(db_session, email, UserStatus.APPROVED)

        # Request OTP
        await client.post(
            "/api/v1/auth/signin",
            json={"email": email},
        )

        # Make 5 failed attempts with wrong code
        for _ in range(5):
            response = await client.post(
                "/api/v1/auth/signin/verify",
                json={"email": email, "code": "000000"},
            )
            assert response.status_code == 400

        # Get the correct OTP
        otp = await get_latest_otp(db_session, email, OTPPurpose.SIGNIN)

        # 6th attempt should fail even with correct code
        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": email, "code": otp},
        )

        assert response.status_code == 400
        assert "too many" in response.json()["detail"].lower()


class TestAuthenticatedEndpoints:
    """Tests for endpoints requiring authentication."""

    async def test_me_without_auth_fails(self, client: AsyncClient):
        """Test that /me fails without authentication."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401

    async def test_me_with_auth_succeeds(self, client: AsyncClient, db_session):
        """Test that /me succeeds with valid session."""
        # Create user and sign in (using approved domain for auto-approval)
        email = "metest@approved-domain.com"

        # Sign in (auto-creates and approves user)
        await client.post(
            "/api/v1/auth/signin",
            json={"email": email},
        )
        otp = await get_latest_otp(db_session, email, OTPPurpose.SIGNIN)

        signin_response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": email, "code": otp},
        )

        # Use the session cookie from sign-in
        cookies = signin_response.cookies

        # Call /me with the session
        response = await client.get(
            "/api/v1/auth/me",
            cookies=cookies,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email


class TestAdminEndpoints:
    """Tests for admin-only endpoints."""

    async def test_admin_endpoint_non_admin_forbidden(self, client: AsyncClient, db_session):
        """Test that non-admin users get 403 on admin endpoints."""
        # Create regular user and sign in
        email = "regularuser@approved-domain.com"

        # Sign in (auto-creates and approves user)
        await client.post(
            "/api/v1/auth/signin",
            json={"email": email},
        )
        otp = await get_latest_otp(db_session, email, OTPPurpose.SIGNIN)

        signin_response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": email, "code": otp},
        )

        cookies = signin_response.cookies

        # Try to access admin endpoint
        response = await client.get(
            "/api/v1/admin/users",
            cookies=cookies,
        )

        assert response.status_code == 403


class TestRejectedUserSecurityBans:
    """Tests for cross-banning rejected pending users."""

    async def test_reject_pending_user_bans_signup_ip_and_shows_in_security_api(
        self, client: AsyncClient, db_session
    ):
        pending_email = "pending@external-example.com"
        admin_email = "admin@approved-domain.com"
        signup_ip = "203.0.113.10"

        pending_user = await create_test_user(db_session, pending_email, UserStatus.PENDING)
        await create_test_user(
            db_session,
            admin_email,
            UserStatus.APPROVED,
            is_admin=True,
        )

        await client.post("/api/v1/auth/signin", json={"email": pending_email})
        pending_otp = await get_latest_otp(db_session, pending_email, OTPPurpose.SIGNIN)
        pending_verify = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": pending_email, "code": pending_otp},
            headers={"X-Forwarded-For": signup_ip},
        )
        assert pending_verify.status_code == 200
        assert "pending" in pending_verify.json()["message"].lower()

        audit_stmt = select(AuditLog).where(
            AuditLog.actor_email == pending_email,
            AuditLog.event_type == "auth.identity.pending_approval",
        )
        audit_result = await db_session.execute(audit_stmt)
        registration_audit = audit_result.scalar_one_or_none()
        assert registration_audit is not None
        assert registration_audit.ip_address == signup_ip

        await client.post("/api/v1/auth/signin", json={"email": admin_email})
        admin_otp = await get_latest_otp(db_session, admin_email, OTPPurpose.SIGNIN)
        admin_verify = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": admin_email, "code": admin_otp},
        )
        assert admin_verify.status_code == 200

        admin_cookies = admin_verify.cookies
        reject_response = await client.post(
            f"/api/v1/admin/users/{pending_user.id}/reject",
            cookies=admin_cookies,
        )
        assert reject_response.status_code == 200

        banned_email_stmt = select(BannedEmail).where(BannedEmail.email == pending_email)
        banned_email_result = await db_session.execute(banned_email_stmt)
        banned_email = banned_email_result.scalar_one_or_none()
        assert banned_email is not None
        assert banned_email.associated_ip == signup_ip

        banned_ip_stmt = select(BannedIP).where(BannedIP.ip_address == signup_ip)
        banned_ip_result = await db_session.execute(banned_ip_stmt)
        banned_ip = banned_ip_result.scalar_one_or_none()
        assert banned_ip is not None
        assert banned_ip.associated_email == pending_email

        security_response = await client.get(
            "/api/v1/admin/security/banned-ips",
            cookies=admin_cookies,
        )
        assert security_response.status_code == 200
        banned_ips = security_response.json()["banned_ips"]
        assert any(entry["ip_address"] == signup_ip for entry in banned_ips)

    async def test_security_stats_split_manual_bans_from_blocked_requests(
        self, client: AsyncClient, db_session
    ):
        admin = await create_test_user(
            db_session, "stats-admin@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )

        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        admin_otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)
        signin_response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": admin.email, "code": admin_otp},
        )
        cookies = signin_response.cookies

        await client.post(
            "/api/v1/admin/security/banned-ips",
            json={"ip_address": "198.51.100.10", "reason": "manual"},
            cookies=cookies,
        )
        await client.post(
            "/api/v1/admin/security/banned-emails",
            json={"email": "blocked@example.com", "reason": "manual"},
            cookies=cookies,
        )

        stats_response = await client.get("/api/v1/admin/security/stats", cookies=cookies)
        assert stats_response.status_code == 200
        data = stats_response.json()
        assert data["manual_bans_today"] == 2
        assert data["blocked_today"] == 0


class TestPublicSurfaceProtection:
    """Tests for public docs and openapi protection."""

    async def test_public_api_docs_disabled_by_default(self, client: AsyncClient):
        root_response = await client.get("/", follow_redirects=False)
        docs_response = await client.get("/api/v1")
        openapi_response = await client.get("/api/v1/openapi.json")

        assert root_response.status_code == 307
        assert root_response.headers["location"] == "/health"
        assert docs_response.status_code == 404
        assert openapi_response.status_code == 404

    async def test_banned_ip_cannot_access_public_openapi(self, client: AsyncClient, db_session):
        blocked_ip = "203.0.113.40"
        db_session.add(
            BannedIP(
                ip_address=blocked_ip,
                reason=BanReason.MANUAL.value,
                details="Test ban",
                banned_by="test",
                expires_at=datetime.utcnow() + timedelta(hours=1),
                is_active=True,
            )
        )
        await db_session.commit()

        response = await client.get(
            "/api/v1/openapi.json",
            headers={"X-Forwarded-For": blocked_ip},
        )

        assert response.status_code == 403

    async def test_untrusted_peer_cannot_spoof_forwarded_for(self, client: AsyncClient, db_session):
        from gatekeeper.main import app

        blocked_ip = "203.0.113.41"
        db_session.add(
            BannedIP(
                ip_address=blocked_ip,
                reason=BanReason.MANUAL.value,
                details="Test ban",
                banned_by="test",
                expires_at=datetime.utcnow() + timedelta(hours=1),
                is_active=True,
            )
        )
        await db_session.commit()

        transport = ASGITransport(app=app, client=("198.51.100.99", 1234))
        async with AsyncClient(transport=transport, base_url="http://test") as untrusted_client:
            response = await untrusted_client.get(
                "/api/v1/openapi.json",
                headers={"X-Forwarded-For": blocked_ip},
            )

        assert response.status_code == 404

    async def test_google_callback_invalid_state_can_trigger_auto_ban(
        self, client: AsyncClient, db_session
    ):
        attack_ip = "203.0.113.42"

        for _ in range(10):
            response = await client.get(
                "/api/v1/auth/google/callback",
                params={"code": "fake-code", "state": "invalid-state"},
                headers={"X-Forwarded-For": attack_ip},
            )
            assert response.status_code == 302

        banned_ip_stmt = select(BannedIP).where(BannedIP.ip_address == attack_ip)
        banned_ip_result = await db_session.execute(banned_ip_stmt)
        banned_ip = banned_ip_result.scalar_one_or_none()

        assert banned_ip is not None
        assert banned_ip.reason == BanReason.RATE_LIMIT.value

    async def test_admin_endpoint_admin_succeeds(self, client: AsyncClient, db_session):
        """Test that admin users can access admin endpoints."""
        # Create admin user directly
        admin = await create_test_user(
            db_session,
            "admin@approved-domain.com",
            UserStatus.APPROVED,
            is_admin=True,
        )

        # Sign in as admin
        await client.post(
            "/api/v1/auth/signin",
            json={"email": admin.email},
        )
        otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)

        signin_response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": admin.email, "code": otp},
        )

        cookies = signin_response.cookies

        # Access admin endpoint
        response = await client.get(
            "/api/v1/admin/users",
            cookies=cookies,
        )

        assert response.status_code == 200


class TestSignOut:
    """Tests for sign-out functionality."""

    async def test_signout_clears_session(self, client: AsyncClient, db_session):
        """Test that signing out clears the session."""
        # Sign in first
        email = "signouttest@approved-domain.com"

        await client.post(
            "/api/v1/auth/signin",
            json={"email": email},
        )
        otp = await get_latest_otp(db_session, email, OTPPurpose.SIGNIN)

        signin_response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": email, "code": otp},
        )

        cookies = signin_response.cookies

        # Sign out
        signout_response = await client.post(
            "/api/v1/auth/signout",
            cookies=cookies,
        )

        assert signout_response.status_code == 200

        # Session cookie should be cleared (empty or expired)
        # Try to access /me - should fail
        me_response = await client.get("/api/v1/auth/me")
        assert me_response.status_code == 401
