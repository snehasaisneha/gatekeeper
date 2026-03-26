"""
Tests for multi-app functionality.
"""

from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gatekeeper.models.app import App, UserAppAccess
from gatekeeper.models.otp import OTPPurpose
from gatekeeper.models.session import Session
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
    is_app_admin: bool = False,
) -> UserAppAccess:
    """Grant a user access to an app."""
    access = UserAppAccess(
        user_id=user_id,
        app_id=app_id,
        role=role,
        is_app_admin=is_app_admin,
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
        await client.post("/api/v1/auth/signin", json={"email": email})
        otp = await get_latest_otp(db_session, email, OTPPurpose.SIGNIN)

        response = await client.post(
            "/api/v1/auth/signin/verify",
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
        await client.post("/api/v1/auth/signin", json={"email": email})
        otp = await get_latest_otp(db_session, email, OTPPurpose.SIGNIN)

        response = await client.post(
            "/api/v1/auth/signin/verify",
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
        """Test that registered apps deny access to external users without grants."""
        # Create app
        await create_test_app(db_session, "restricted-app", "Restricted App")

        # Create and sign in user from non-approved domain (external user)
        # First create them directly as approved to avoid the pending flow
        user = await create_test_user(
            db_session, "no-access@external-domain.com", UserStatus.APPROVED
        )

        await client.post("/api/v1/auth/signin", json={"email": user.email})
        otp = await get_latest_otp(db_session, user.email, OTPPurpose.SIGNIN)

        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": user.email, "code": otp},
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
        """Test that X-Auth-Role is returned when role is set for external users."""
        # Create app
        app = await create_test_app(db_session, "role-app", "Role App")

        # Create external user (not from approved domain) - manually approved
        user = await create_test_user(
            db_session, "has-role@external-domain.com", UserStatus.APPROVED
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
        """Test that X-Auth-Role is not returned when no role is set for external users."""
        # Create app
        app = await create_test_app(db_session, "no-role-app", "No Role App")

        # Create external user (not from approved domain) - manually approved
        user = await create_test_user(
            db_session, "no-role@external-domain.com", UserStatus.APPROVED
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
        # Create regular user and sign in
        email = "regular@approved-domain.com"
        await client.post("/api/v1/auth/signin", json={"email": email})
        otp = await get_latest_otp(db_session, email, OTPPurpose.SIGNIN)

        response = await client.post(
            "/api/v1/auth/signin/verify",
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

    async def test_create_app_rejects_reserved_auth_slug(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that admins cannot create an app using the auth host slug."""
        admin = await create_test_user(
            db_session, "reserved-admin@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )

        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)

        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": admin.email, "code": otp},
        )
        cookies = response.cookies

        with patch("gatekeeper.api.v1.admin.get_settings") as mock_get_settings:
            mock_get_settings.return_value.app_url = "https://auth.example.com"
            create_response = await client.post(
                "/api/v1/admin/apps",
                json={"slug": "auth", "name": "Auth Collision"},
                cookies=cookies,
            )

        assert create_response.status_code == 400
        assert "reserved for the auth host" in create_response.json()["detail"].lower()

    async def test_lookup_existing_user_by_email(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await create_test_user(
            db_session, "lookup-admin@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )
        existing_user = await create_test_user(
            db_session, "existing@approved-domain.com", UserStatus.APPROVED
        )

        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)
        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": admin.email, "code": otp},
        )
        cookies = response.cookies

        lookup_response = await client.get(
            "/api/v1/admin/users/lookup",
            params={"email": existing_user.email},
            cookies=cookies,
        )

        assert lookup_response.status_code == 200
        data = lookup_response.json()
        assert data["exists"] is True
        assert data["user"]["email"] == existing_user.email

    async def test_lookup_missing_user_by_email(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await create_test_user(
            db_session, "lookup-admin-2@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )

        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)
        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": admin.email, "code": otp},
        )
        cookies = response.cookies

        lookup_response = await client.get(
            "/api/v1/admin/users/lookup",
            params={"email": "missing@approved-domain.com"},
            cookies=cookies,
        )

        assert lookup_response.status_code == 200
        assert lookup_response.json() == {"exists": False, "user": None}

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

    async def test_app_admin_sees_only_scoped_apps_and_scope_in_me(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        app_admin = await create_test_user(
            db_session, "scoped-admin@approved-domain.com", UserStatus.APPROVED
        )
        scoped_app = await create_test_app(db_session, "scoped-app", "Scoped App")
        other_app = await create_test_app(db_session, "other-app", "Other App")
        await grant_app_access(
            db_session, app_admin.id, scoped_app.id, role="owner", is_app_admin=True
        )

        await client.post("/api/v1/auth/signin", json={"email": app_admin.email})
        otp = await get_latest_otp(db_session, app_admin.email, OTPPurpose.SIGNIN)
        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": app_admin.email, "code": otp},
        )
        cookies = response.cookies

        me_response = await client.get("/api/v1/auth/me", cookies=cookies)
        assert me_response.status_code == 200
        assert me_response.json()["app_admin_apps"] == [
            {
                "app_id": str(scoped_app.id),
                "app_slug": "scoped-app",
                "app_name": "Scoped App",
                "app_description": None,
                "app_url": None,
            }
        ]

        list_response = await client.get("/api/v1/admin/apps", cookies=cookies)
        assert list_response.status_code == 200
        assert [app["slug"] for app in list_response.json()["apps"]] == ["scoped-app"]
        assert other_app.slug not in [app["slug"] for app in list_response.json()["apps"]]

    async def test_app_admin_api_key_can_manage_access_and_is_audited(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        app_admin = await create_test_user(
            db_session, "api-key-admin@approved-domain.com", UserStatus.APPROVED
        )
        target_user = await create_test_user(
            db_session, "api-key-user@approved-domain.com", UserStatus.APPROVED
        )
        app = await create_test_app(db_session, "key-managed-app", "Key Managed App")
        await grant_app_access(db_session, app_admin.id, app.id, role="owner", is_app_admin=True)

        await client.post("/api/v1/auth/signin", json={"email": app_admin.email})
        otp = await get_latest_otp(db_session, app_admin.email, OTPPurpose.SIGNIN)
        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": app_admin.email, "code": otp},
        )
        cookies = response.cookies

        key_response = await client.post(
            f"/api/v1/admin/apps/{app.slug}/api-keys",
            json={"name": "CI key"},
            cookies=cookies,
        )
        assert key_response.status_code == 201
        plain_text_key = key_response.json()["plain_text_key"]

        grant_response = await client.post(
            f"/api/v1/admin/apps/{app.slug}/grant",
            json={"email": target_user.email, "role": "editor"},
            headers={"Authorization": f"Bearer {plain_text_key}"},
        )
        assert grant_response.status_code == 200

        audit_response = await client.get(
            f"/api/v1/admin/apps/{app.slug}/audit-logs",
            headers={"Authorization": f"Bearer {plain_text_key}"},
        )
        assert audit_response.status_code == 200
        assert any(
            log["actor_email"] == "api-key:CI key" and log["event_type"] == "admin.access.granted"
            for log in audit_response.json()["logs"]
        )

    async def test_app_admin_scope_is_derived_from_admin_roles(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await create_test_user(
            db_session, "mapped-admin@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )
        user = await create_test_user(
            db_session, "mapped-user@approved-domain.com", UserStatus.APPROVED
        )

        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)
        response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": admin.email, "code": otp},
        )
        cookies = response.cookies

        create_response = await client.post(
            "/api/v1/admin/apps",
            json={
                "slug": "mapped-admin-app",
                "name": "Mapped Admin App",
                "roles": "viewer,owner",
                "admin_roles": "owner",
            },
            cookies=cookies,
        )
        assert create_response.status_code == 201
        assert create_response.json()["admin_roles"] == "owner"

        grant_response = await client.post(
            "/api/v1/admin/apps/mapped-admin-app/grant",
            json={"email": user.email, "role": "owner"},
            cookies=cookies,
        )
        assert grant_response.status_code == 200

        await client.post("/api/v1/auth/signin", json={"email": user.email})
        user_otp = await get_latest_otp(db_session, user.email, OTPPurpose.SIGNIN)
        user_response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": user.email, "code": user_otp},
        )
        user_cookies = user_response.cookies

        me_response = await client.get("/api/v1/auth/me", cookies=user_cookies)
        assert me_response.status_code == 200
        assert [app["app_slug"] for app in me_response.json()["app_admin_apps"]] == [
            "mapped-admin-app"
        ]

    async def test_user_investigation_returns_access_sessions_and_activity(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await create_test_user(
            db_session,
            "investigation-admin@approved-domain.com",
            UserStatus.APPROVED,
            is_admin=True,
        )
        user = await create_test_user(
            db_session, "investigation-user@external-domain.com", UserStatus.APPROVED
        )
        app = await create_test_app(db_session, "investigation-app", "Investigation App")
        await grant_app_access(db_session, user.id, app.id, role="viewer")

        await client.post("/api/v1/auth/signin", json={"email": user.email})
        user_otp = await get_latest_otp(db_session, user.email, OTPPurpose.SIGNIN)
        await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": user.email, "code": user_otp},
            headers={"user-agent": "InvestigationBrowser/1.0"},
        )

        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        admin_otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)
        admin_response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": admin.email, "code": admin_otp},
        )
        cookies = admin_response.cookies

        response = await client.get(f"/api/v1/admin/users/{user.id}/investigation", cookies=cookies)

        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == user.email
        assert data["app_access"][0]["app_slug"] == app.slug
        assert data["app_access"][0]["role"] == "viewer"
        assert data["active_sessions"][0]["auth_method"] == "otp"
        assert data["recent_audit_logs"]
        assert data["last_auth_method"] == "otp"

    async def test_admin_can_revoke_user_session(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        admin = await create_test_user(
            db_session, "session-admin@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )
        user = await create_test_user(
            db_session, "session-user@approved-domain.com", UserStatus.APPROVED
        )

        await client.post("/api/v1/auth/signin", json={"email": user.email})
        user_otp = await get_latest_otp(db_session, user.email, OTPPurpose.SIGNIN)
        await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": user.email, "code": user_otp},
        )

        session_result = await db_session.execute(select(Session).where(Session.user_id == user.id))
        session = session_result.scalar_one()

        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        admin_otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)
        admin_response = await client.post(
            "/api/v1/auth/signin/verify",
            json={"email": admin.email, "code": admin_otp},
        )
        cookies = admin_response.cookies

        revoke_response = await client.delete(
            f"/api/v1/admin/users/{user.id}/sessions/{session.id}",
            cookies=cookies,
        )
        assert revoke_response.status_code == 200

        session_result = await db_session.execute(select(Session).where(Session.id == session.id))
        assert session_result.scalar_one_or_none() is None
