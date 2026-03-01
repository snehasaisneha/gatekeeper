"""Tests for audit logging functionality."""

from httpx import AsyncClient

from gatekeeper.models.otp import OTPPurpose
from gatekeeper.models.user import UserStatus
from gatekeeper.services.audit import EventType, parse_user_agent

from .conftest import create_test_user, get_latest_otp


class TestParseUserAgent:
    """Tests for user agent parsing."""

    def test_chrome_macos(self):
        ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
        result = parse_user_agent(ua)
        assert result["browser"] == "Chrome"
        assert result["os"] == "macOS"
        assert result["type"] == "desktop"

    def test_safari_iphone(self):
        ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 Version/17.0 Mobile Safari/604.1"
        )
        result = parse_user_agent(ua)
        assert result["browser"] == "Safari"
        assert result["os"] == "iOS"
        assert result["type"] == "mobile"

    def test_firefox_linux(self):
        ua = "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"
        result = parse_user_agent(ua)
        assert result["browser"] == "Firefox"
        assert result["os"] == "Linux"
        assert result["type"] == "desktop"

    def test_edge_windows(self):
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        )
        result = parse_user_agent(ua)
        assert result["browser"] == "Edge"
        assert result["os"] == "Windows"
        assert result["type"] == "desktop"

    def test_none_user_agent(self):
        result = parse_user_agent(None)
        assert result == {}


class TestAuditLogAPI:
    """Tests for audit log API endpoints."""

    async def test_list_audit_logs_requires_admin(self, client: AsyncClient, db_session):
        """Non-admin users cannot access audit logs."""
        # Create regular user and sign in
        email = "regularuser@approved-domain.com"
        await client.post("/api/v1/auth/signin", json={"email": email})
        otp = await get_latest_otp(db_session, email, OTPPurpose.SIGNIN)
        signin_response = await client.post(
            "/api/v1/auth/signin/verify", json={"email": email, "code": otp}
        )
        cookies = signin_response.cookies

        response = await client.get("/api/v1/admin/audit-logs", cookies=cookies)
        assert response.status_code == 403

    async def test_list_audit_logs_admin_success(self, client: AsyncClient, db_session):
        """Admin can access audit logs."""
        # Create admin user and sign in
        admin = await create_test_user(
            db_session, "admin@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )
        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)
        signin_response = await client.post(
            "/api/v1/auth/signin/verify", json={"email": admin.email, "code": otp}
        )
        cookies = signin_response.cookies

        response = await client.get("/api/v1/admin/audit-logs", cookies=cookies)
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    async def test_audit_logs_pagination(self, client: AsyncClient, db_session):
        """Audit logs support pagination."""
        # Create admin user and sign in
        admin = await create_test_user(
            db_session, "admin2@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )
        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)
        signin_response = await client.post(
            "/api/v1/auth/signin/verify", json={"email": admin.email, "code": otp}
        )
        cookies = signin_response.cookies

        response = await client.get(
            "/api/v1/admin/audit-logs",
            params={"page": 1, "page_size": 10},
            cookies=cookies,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    async def test_audit_logs_filter_by_event_type(self, client: AsyncClient, db_session):
        """Audit logs can be filtered by event type prefix."""
        # Create admin user and sign in
        admin = await create_test_user(
            db_session, "admin3@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )
        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)
        signin_response = await client.post(
            "/api/v1/auth/signin/verify", json={"email": admin.email, "code": otp}
        )
        cookies = signin_response.cookies

        response = await client.get(
            "/api/v1/admin/audit-logs",
            params={"event_type": "auth.signin"},
            cookies=cookies,
        )
        assert response.status_code == 200


class TestAuditLogging:
    """Tests for audit event logging during auth flows."""

    async def test_signout_creates_audit_log(self, client: AsyncClient, db_session):
        """Signing out creates an audit log entry."""
        from sqlalchemy import select

        from gatekeeper.models.audit import AuditLog

        # Create admin user and sign in
        admin = await create_test_user(
            db_session, "admin4@approved-domain.com", UserStatus.APPROVED, is_admin=True
        )
        await client.post("/api/v1/auth/signin", json={"email": admin.email})
        otp = await get_latest_otp(db_session, admin.email, OTPPurpose.SIGNIN)
        signin_response = await client.post(
            "/api/v1/auth/signin/verify", json={"email": admin.email, "code": otp}
        )
        cookies = signin_response.cookies

        # Sign out
        response = await client.post("/api/v1/auth/signout", cookies=cookies)
        assert response.status_code == 200

        # Check that audit log was created (need fresh query)
        await db_session.commit()
        stmt = select(AuditLog).where(AuditLog.event_type == EventType.AUTH_SIGNOUT)
        result = await db_session.execute(stmt)
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.actor_email is not None
