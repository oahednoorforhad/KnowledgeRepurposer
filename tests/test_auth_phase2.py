"""Phase 2 tests: refresh token flow."""

import uuid

import pytest

from app.auth import hash_refresh_token
from app.repositories.refresh_token_repo import get_refresh_token_by_hash
from app.services.rate_limiter import _requests


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    _requests.clear()


class TestLoginSetsCookies:
    """Login and register must set access_token and refresh_token httponly cookies."""

    async def test_login_sets_cookies(self, client, test_user):
        resp = await client.post(
            "/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["plain_password"],
            },
        )
        assert resp.status_code == 200
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

        set_cookie = resp.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower()

    async def test_register_sets_cookies(self, client):
        email = f"reg-cookie-{uuid.uuid4().hex[:8]}@test.com"
        resp = await client.post(
            "/auth/register",
            json={"email": email, "password": "test-password-ok"},
        )
        assert resp.status_code == 201
        assert "access_token" in resp.cookies
        assert "refresh_token" in resp.cookies

        set_cookie = resp.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower()


class TestRefreshFlow:
    """Test the refresh token rotation and revocation flow."""

    async def test_refresh_with_valid_cookie(self, client, test_user):
        login_resp = await client.post(
            "/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["plain_password"],
            },
        )
        assert login_resp.status_code == 200
        original_refresh = login_resp.cookies["refresh_token"]

        refresh_resp = await client.post("/auth/refresh")
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.cookies
        assert "refresh_token" in refresh_resp.cookies
        assert (
            refresh_resp.cookies["refresh_token"] != original_refresh
        ), "refresh token was not rotated"

    async def test_reused_refresh_token_returns_401(self, client, test_user, db_pool):
        login_resp = await client.post(
            "/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["plain_password"],
            },
        )
        assert login_resp.status_code == 200
        old_refresh = login_resp.cookies["refresh_token"]

        logout_resp = await client.post("/auth/logout")
        assert logout_resp.status_code == 200

        client.cookies.clear()
        client.cookies.set("refresh_token", old_refresh)

        resp = await client.post("/auth/refresh")
        assert resp.status_code == 401
        assert "reused" in resp.json()["detail"].lower()

        token_hash = hash_refresh_token(old_refresh)
        revoked = await get_refresh_token_by_hash(token_hash)
        assert revoked is not None, "old token should still exist in DB"
        assert revoked["revoked_at"] is not None

        conn = await db_pool.acquire()
        try:
            rows = await conn.fetch(
                "SELECT * FROM refresh_tokens "
                "WHERE user_id = $1::uuid AND revoked_at IS NULL AND expires_at > now()",
                test_user["id"],
            )
            assert len(rows) == 0
        finally:
            await db_pool.release(conn)

    async def test_refresh_without_token_returns_401(self, client):
        client.cookies.clear()
        resp = await client.post("/auth/refresh")
        assert resp.status_code == 401
        assert "missing" in resp.json()["detail"].lower()


class TestLogoutClearsCookies:
    """Logout must clear access and refresh cookies."""

    async def test_logout_clears_cookies(self, client, test_user):
        login_resp = await client.post(
            "/auth/login",
            json={
                "email": test_user["email"],
                "password": test_user["plain_password"],
            },
        )
        assert login_resp.status_code == 200
        assert "access_token" in login_resp.cookies
        assert "refresh_token" in login_resp.cookies

        logout_resp = await client.post("/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.json()["message"] == "success"

        set_cookie_raw = logout_resp.headers.get("set-cookie", "").lower()
        assert "access_token=" in set_cookie_raw
        assert "refresh_token=" in set_cookie_raw

    async def test_unauthenticated_logout_returns_401(self, client):
        client.cookies.clear()
        resp = await client.post("/auth/logout")
        assert resp.status_code == 401
