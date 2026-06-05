"""Phase 4 tests: change password flow."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import (
    create_refresh_token_value,
    hash_refresh_token,
    verify_password,
)
from app.repositories.refresh_token_repo import create_refresh_token
from app.services.rate_limiter import _requests
from main import app

# ---------------------------------------------------------------------------
# Helpers (reused from Phase 1 tests for rate-limit isolation)
# ---------------------------------------------------------------------------


class _ClientIPTransport(ASGITransport):
    """ASGI transport that overrides the remote client IP address.

    FastAPI's ``request.client.host`` reads from ``scope["client"]``, which is
    set by the ASGI server.  This transport lets us control it so that rate-
    limit tests can use distinct IP addresses without cross-test interference.
    """

    def __init__(self, app, client_host: str) -> None:
        super().__init__(app=app)
        self.client_host = client_host

    async def __call__(self, scope, receive, send):
        scope["client"] = (self.client_host, 8000)
        return await super().__call__(scope, receive, send)


def _make_client(client_host: str = "test-client") -> AsyncClient:
    """Return an ``AsyncClient`` whose requests appear to come from *client_host*."""
    transport = _ClientIPTransport(app=app, client_host=client_host)
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Module-level rate-limit cleanup
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Clear all in-memory rate-limit state before each test."""
    _requests.clear()


# ===================================================================
# /auth/change-password — unauthenticated
# ===================================================================


class TestChangePasswordUnauthenticated:
    """``/auth/change-password`` must reject unauthenticated requests."""

    async def test_without_auth_returns_401(self, client):
        """Without a valid JWT the endpoint should respond 401."""
        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "whatever", "new_password": "new-password-123"},
        )
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["detail"]


# ===================================================================
# /auth/change-password — wrong current password
# ===================================================================


class TestChangePasswordWrongPassword:
    """``/auth/change-password`` with an incorrect current password."""

    async def test_wrong_current_password_returns_401(self, client, auth_headers):
        """Sending a wrong ``current_password`` should return 401."""
        resp = await client.post(
            "/auth/change-password",
            json={
                "current_password": "this-is-the-wrong-password",
                "new_password": "new-password-123",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 401
        assert "Current password is incorrect" in resp.json()["detail"]


# ===================================================================
# /auth/change-password — valid change
# ===================================================================


class TestChangePasswordValid:
    """Valid change-password flow — DB update, token revocation, login."""

    async def test_valid_change_updates_db_and_revokes_refresh_tokens(
        self, client, auth_headers, test_user, db_pool
    ):
        """A valid change-password request updates the password hash in the
        database and revokes all existing refresh tokens for the user."""
        new_password = "brand-new-password-456"

        # Create a refresh token so we can verify it gets revoked
        raw = create_refresh_token_value()
        token_hash = hash_refresh_token(raw)
        expiry = datetime.now(timezone.utc) + timedelta(days=1)
        await create_refresh_token(str(test_user["id"]), token_hash, expiry)

        # Send the change-password request
        resp = await client.post(
            "/auth/change-password",
            json={
                "current_password": test_user["plain_password"],
                "new_password": new_password,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Password changed successfully"

        # --- Verify password hash updated in DB ---
        conn = await db_pool.acquire()
        try:
            row = await conn.fetchrow(
                "SELECT hashed_password FROM users WHERE id = $1::uuid",
                test_user["id"],
            )
        finally:
            await db_pool.release(conn)

        assert row is not None
        new_hashed = row["hashed_password"]
        assert verify_password(new_password, new_hashed), (
            "New password should be verifiable against stored hash"
        )
        assert not verify_password(test_user["plain_password"], new_hashed), (
            "Old password should NOT be verifiable against stored hash"
        )

        # --- Verify refresh tokens were revoked ---
        conn2 = await db_pool.acquire()
        try:
            revoked = await conn2.fetchrow(
                "SELECT revoked_at FROM refresh_tokens "
                "WHERE token_hash = $1 AND revoked_at IS NOT NULL",
                token_hash,
            )
        finally:
            await db_pool.release(conn2)

        assert revoked is not None, (
            "Refresh token should have been revoked after password change"
        )

    async def test_new_password_works_for_login(self, test_user):
        """After changing the password, the new password must be accepted by
        ``/auth/login`` while the old password is rejected."""
        new_password = "login-test-new-pw-789"
        ip_suffix = uuid.uuid4().hex[:8]

        # Use an isolated client for the entire flow so rate-limit state
        # from other tests does not interfere.
        client = _make_client(f"change-pw-{ip_suffix}")

        # --- Log in with the original password to obtain a real JWT ---
        login_resp = await client.post(
            "/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["plain_password"],
            },
        )
        assert login_resp.status_code == 200, (
            "Initial login with original password should succeed"
        )

        # Build auth headers from cookies returned by the login request
        token = client.cookies.get("access_token")
        assert token is not None, "Login should have set an access_token cookie"
        auth_headers = {"Authorization": f"Bearer {token}"}

        # --- Change password ---
        resp = await client.post(
            "/auth/change-password",
            json={
                "current_password": test_user["plain_password"],
                "new_password": new_password,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # --- Login with the new password should succeed ---
        # (Use a fresh client so cookie state from previous calls does not
        # interfere with the login response)
        fresh_client = _make_client(f"change-pw-{ip_suffix}-fresh")

        login2 = await fresh_client.post(
            "/auth/login",
            json={"email": test_user["email"], "password": new_password},
        )
        assert login2.status_code == 200
        assert login2.json()["message"] == "success"

        # --- Login with the old password must fail ---
        old_login = await fresh_client.post(
            "/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["plain_password"],
            },
        )
        assert old_login.status_code == 401
        assert "Invalid email or password" in old_login.json()["detail"]
