"""
Tests for multi-app functionality.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.models.app import App, UserAppAccess
from gatekeeper.models.otp import OTPPurpose
from gatekeeper.models.user import UserStatus

from .conftest import create_test_user, get_latest_otp


async def create_test_app(db_session: AsyncSession, slug: str, name: str) -> App:
    """Create a test app directly in the database."""
    app = App(slug=slug, name=name)
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    return app


async def grant_app_access(
    db_session: AsyncSession,
    user_id,
    app_id,
    role: str | None = None,
) -> UserAppAccess:
    """Grant a user access to an app."""
    access = UserAppAccess(
        user_id=user_id,
        app_id=app_id,
        role=role,
        granted_by="test",
    )
    db_session.add(access)
    await db_session.commit()
    await db_session.refresh(access)
    return access


class TestValidateEndpoint:
    """Tests for the /auth/validate endpoint."""

    async def test_validate_unauthenticated_returns_401(self, client: AsyncClient):
        """Test that unauthenticated requests return 401."""
        response = await client.get("/api/v1/auth/validate")
        assert response.status_code == 401

    async def test_validate_authenticated_no_app_returns_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that authenticated requests without X-GK-App return user info."""
        # Create and sign in user
        email = "validate-test@approved-domain.com"
        await client.post("/api/v1/auth/register", json={"email": email})
        otp = await get_latest_otp(db_session, email, OTPPurpose.REGISTER)

        response = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": email, "code": otp},
        )
        cookies = response.cookies

        # Call validate without X-GK-App
        validate_response = await client.get(
            "/api/v1/auth/validate",
            cookies=cookies,
        )

        assert validate_response.status_code == 200
        assert validate_response.headers.get("X-Auth-User") == email

    async def test_validate_unregistered_app_allows_by_default(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that unregistered apps allow access by default."""
        # Create and sign in user
        email = "unregistered-app@approved-domain.com"
        await client.post("/api/v1/auth/register", json={"email": email})
        otp = await get_latest_otp(db_session, email, OTPPurpose.REGISTER)

        response = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": email, "code": otp},
        )
        cookies = response.cookies

        # Call validate with unregistered app
        validate_response = await client.get(
            "/api/v1/auth/validate",
            cookies=cookies,
            headers={"X-GK-App": "nonexistent-app"},
        )

        assert validate_response.status_code == 200
        assert validate_response.headers.get("X-Auth-User") == email

    async def test_validate_registered_app_without_access_returns_403(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that registered apps deny access to users without grants."""
        # Create app (needed to establish app in DB, but not referenced directly)
        await create_test_app(db_session, "restricted-app", "Restricted App")

        # Create and sign in user (no app access granted)
        email = "no-access@approved-domain.com"
        await client.post("/api/v1/auth/register", json={"email": email})
        otp = await get_latest_otp(db_session, email, OTPPurpose.REGISTER)

        response = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": email, "code": otp},
        )
        cookies = response.cookies

        # Call validate with registered app
        validate_response = await client.get(
            "/api/v1/auth/validate",
            cookies=cookies,
            headers={"X-GK-App": "restricted-app"},
        )

        assert validate_response.status_code == 403

    async def test_validate_registered_app_with_access_returns_200(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that registered apps allow access to users with grants."""
        # Create app
        app = await create_test_app(db_session, "granted-app", "Granted App")

        # Create user
        user = await create_test_user(
            db_session, "has-access@approved-domain.com", UserStatus.APPROVED
        )

        # Grant access
        await grant_app_access(db_session, user.id, app.id)

        # Sign in
        await client.post(
            "/api/v1/auth/signin",
            json={"email": user.email},
        )
        otp = await get_latest_otp(db_session, user.email, OTPPurpose.SIGNIN)

        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": user.email, "code": otp},
        )
        cookies = response.cookies

        # Call validate
        validate_response = await client.get(
            "/api/v1/auth/validate",
            cookies=cookies,
            headers={"X-GK-App": "granted-app"},
        )

        assert validate_response.status_code == 200
        assert validate_response.headers.get("X-Auth-User") == user.email

    async def test_validate_returns_role_when_set(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that X-Auth-Role is returned when role is set."""
        # Create app
        app = await create_test_app(db_session, "role-app", "Role App")

        # Create user
        user = await create_test_user(
            db_session, "has-role@approved-domain.com", UserStatus.APPROVED
        )

        # Grant access with role
        await grant_app_access(db_session, user.id, app.id, role="admin")

        # Sign in
        await client.post(
            "/api/v1/auth/signin",
            json={"email": user.email},
        )
        otp = await get_latest_otp(db_session, user.email, OTPPurpose.SIGNIN)

        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": user.email, "code": otp},
        )
        cookies = response.cookies

        # Call validate
        validate_response = await client.get(
            "/api/v1/auth/validate",
            cookies=cookies,
            headers={"X-GK-App": "role-app"},
        )

        assert validate_response.status_code == 200
        assert validate_response.headers.get("X-Auth-User") == user.email
        assert validate_response.headers.get("X-Auth-Role") == "admin"

    async def test_validate_no_role_header_when_role_not_set(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that X-Auth-Role is not returned when no role is set."""
        # Create app
        app = await create_test_app(db_session, "no-role-app", "No Role App")

        # Create user
        user = await create_test_user(
            db_session, "no-role@approved-domain.com", UserStatus.APPROVED
        )

        # Grant access without role
        await grant_app_access(db_session, user.id, app.id, role=None)

        # Sign in
        await client.post(
            "/api/v1/auth/signin",
            json={"email": user.email},
        )
        otp = await get_latest_otp(db_session, user.email, OTPPurpose.SIGNIN)

        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": user.email, "code": otp},
        )
        cookies = response.cookies

        # Call validate
        validate_response = await client.get(
            "/api/v1/auth/validate",
            cookies=cookies,
            headers={"X-GK-App": "no-role-app"},
        )

        assert validate_response.status_code == 200
        assert validate_response.headers.get("X-Auth-User") == user.email
        assert validate_response.headers.get("X-Auth-Role") is None


class TestAdminAppEndpoints:
    """Tests for admin app management endpoints."""

    async def test_list_apps_requires_admin(self, client: AsyncClient, db_session: AsyncSession):
        """Test that listing apps requires admin access."""
        # Create regular user
        email = "regular@approved-domain.com"
        await client.post("/api/v1/auth/register", json={"email": email})
        otp = await get_latest_otp(db_session, email, OTPPurpose.REGISTER)

        response = await client.post(
            "/api/v1/auth/register/verify",
            json={"email": email, "code": otp},
        )
        cookies = response.cookies

        # Try to list apps
        list_response = await client.get("/api/v1/admin/apps", cookies=cookies)
        assert list_response.status_code == 403

    async def test_create_app_as_admin(self, client: AsyncClient, db_session: AsyncSession):
        """Test that admins can create apps."""
        # Create admin user
        admin = await create_test_user(
            db_session, "app-admin@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )

        # Sign in
        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)

        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": admin.email, "code": otp},
        )
        cookies = response.cookies

        # Create app
        create_response = await client.post(
            "/api/v1/admin/apps",
            json={"slug": "test-app", "name": "Test App"},
            cookies=cookies,
        )

        assert create_response.status_code == 201
        data = create_response.json()
        assert data["slug"] == "test-app"
        assert data["name"] == "Test App"

    async def test_grant_and_revoke_access(self, client: AsyncClient, db_session: AsyncSession):
        """Test granting and revoking app access."""
        # Create admin and regular user
        admin = await create_test_user(
            db_session, "grant-admin@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )
        user = await create_test_user(
            db_session, "grant-user@approved-domain.com", UserStatus.APPROVED
        )

        # Create app
        app = await create_test_app(db_session, "grant-test-app", "Grant Test App")

        # Sign in as admin
        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)

        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": admin.email, "code": otp},
        )
        cookies = response.cookies

        # Grant access
        grant_response = await client.post(
            f"/api/v1/admin/apps/{app.slug}/grant",
            json={"email": user.email, "role": "editor"},
            cookies=cookies,
        )
        assert grant_response.status_code == 200

        # Verify access was granted
        app_detail = await client.get(
            f"/api/v1/admin/apps/{app.slug}",
            cookies=cookies,
        )
        assert app_detail.status_code == 200
        users = app_detail.json()["users"]
        assert len(users) == 1
        assert users[0]["email"] == user.email
        assert users[0]["role"] == "editor"

        # Revoke access
        revoke_response = await client.delete(
            f"/api/v1/admin/apps/{app.slug}/revoke",
            params={"email": user.email},
            cookies=cookies,
        )
        assert revoke_response.status_code == 200

        # Verify access was revoked
        app_detail = await client.get(
            f"/api/v1/admin/apps/{app.slug}",
            cookies=cookies,
        )
        users = app_detail.json()["users"]
        assert len(users) == 0
