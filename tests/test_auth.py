"""
Tests for authentication flows.
"""

from httpx import AsyncClient

from gatekeeper.models.otp import OTPPurpose
from gatekeeper.models.user import UserStatus

from .conftest import create_test_otp, create_test_user, get_latest_otp


class TestRegistration:
    """Tests for the registration flow."""

    async def test_register_sends_otp(self, client: AsyncClient, db_session):
        """Test that registration sends an OTP to a new email."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "newuser@test.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Verification code sent"

        # Verify OTP was created in database
        otp = await get_latest_otp(db_session, "newuser@test.com", OTPPurpose.REGISTER)
        assert otp is not None
        assert len(otp) == 6

    async def test_register_existing_approved_user_fails(self, client: AsyncClient, db_session):
        """Test that registration fails for an already approved user."""
        await create_test_user(db_session, "existing@test.com", UserStatus.APPROVED)

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "existing@test.com"},
        )

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    async def test_register_existing_pending_user_fails(self, client: AsyncClient, db_session):
        """Test that registration fails for a pending user."""
        await create_test_user(db_session, "pending@test.com", UserStatus.PENDING)

        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "pending@test.com"},
        )

        assert response.status_code == 400
        assert "pending" in response.json()["detail"].lower()

    async def test_register_verify_auto_approval(self, client: AsyncClient, db_session):
        """Test that users from accepted domains are auto-approved."""
        # approved-domain.com is in the test settings' accepted_domains
        email = "autouser@approved-domain.com"

        # Start registration
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": email},
        )
        assert response.status_code == 200

        # Get OTP from database
        otp = await get_latest_otp(db_session, email, OTPPurpose.REGISTER)
        assert otp is not None

        # Verify registration
        response = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": email, "code": otp},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Registration successful"
        assert data["user"] is not None
        assert data["user"]["email"] == email
        # Should get a session cookie
        assert "session" in response.cookies

    async def test_register_verify_pending_approval(self, client: AsyncClient, db_session):
        """Test that users from non-accepted domains require approval."""
        email = "pendinguser@unknown-domain.com"

        # Start registration
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": email},
        )
        assert response.status_code == 200

        # Get OTP from database
        otp = await get_latest_otp(db_session, email, OTPPurpose.REGISTER)
        assert otp is not None

        # Verify registration
        response = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": email, "code": otp},
        )

        assert response.status_code == 200
        data = response.json()
        assert "pending" in data["message"].lower()
        assert data["user"] is None
        # Should NOT get a session cookie
        assert "session" not in response.cookies

    async def test_register_verify_invalid_otp(self, client: AsyncClient, db_session):
        """Test that invalid OTP is rejected."""
        email = "newuser2@test.com"

        # Start registration
        await client.post(
            "/api/v1/auth/register",
            json={"email": email},
        )

        # Try to verify with wrong code
        response = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": email, "code": "000000"},
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()


class TestSignIn:
    """Tests for the sign-in flow."""

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

    async def test_signin_nonexistent_user_fails(self, client: AsyncClient):
        """Test that sign-in fails for non-existent user."""
        response = await client.post(
            "/api/v1/auth/signin",
            json={"email": "nonexistent@test.com"},
        )

        assert response.status_code == 400
        assert "no account" in response.json()["detail"].lower()

    async def test_signin_pending_user_fails(self, client: AsyncClient, db_session):
        """Test that sign-in fails for pending users."""
        await create_test_user(db_session, "pendingsignin@test.com", UserStatus.PENDING)

        response = await client.post(
            "/api/v1/auth/signin",
            json={"email": "pendingsignin@test.com"},
        )

        assert response.status_code == 400
        assert "pending" in response.json()["detail"].lower()

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
        for i in range(5):
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
        # Create user and sign in
        email = "metest@approved-domain.com"

        # Register and auto-approve
        await client.post(
            "/api/v1/auth/register",
            json={"email": email},
        )
        otp = await get_latest_otp(db_session, email, OTPPurpose.REGISTER)

        register_response = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": email, "code": otp},
        )

        # Use the session cookie from registration
        cookies = register_response.cookies

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

        # Register
        await client.post(
            "/api/v1/auth/register",
            json={"email": email},
        )
        otp = await get_latest_otp(db_session, email, OTPPurpose.REGISTER)

        register_response = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": email, "code": otp},
        )

        cookies = register_response.cookies

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
            "/api/v1/auth/register",
            json={"email": email},
        )
        otp = await get_latest_otp(db_session, email, OTPPurpose.REGISTER)

        register_response = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": email, "code": otp},
        )

        cookies = register_response.cookies

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
