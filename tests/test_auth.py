"""
Tests for authentication flows.
"""

from httpx import AsyncClient

from gatekeeper.models.otp import OTPPurpose
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
