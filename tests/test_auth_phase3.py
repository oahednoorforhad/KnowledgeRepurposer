"""Phase 3 tests: cookie authentication.

The ``access_token`` cookie can be used in place of the ``Authorization``
header for authenticated endpoints.  Tests verify that ``/api/scrape``
accepts a valid JWT sent as ``access_token`` cookie, rejects an invalid
cookie, and continues to reject unauthenticated requests.
"""

from unittest import mock

import pytest

from app.auth import create_jwt


# ===================================================================
# Cookie auth for /api/scrape
# ===================================================================


class TestCookieAuthScrape:
    """``/api/scrape`` must authenticate via ``access_token`` cookie."""

    async def test_cookie_allows_access(self, client):
        """Valid JWT in ``access_token`` cookie → 200 (no Authorization header)."""
        user_dict = {
            "id": "00000000-0000-0000-0000-000000000000",
            "email": "cookie@test.com",
            "created_at": None,
        }
        token = create_jwt(user_dict["id"])

        client.cookies.set("access_token", token)
        with (
            mock.patch("main.article_scraper.scrape", return_value="cookie auth content"),
            mock.patch("app.auth.get_user_by_id", return_value=user_dict),
        ):
            resp = await client.post(
                "/api/scrape",
                json={"url": "https://example.com/article"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "cookie auth content"
        assert data["source_type"] == "article"

    async def test_no_auth_returns_401(self, client):
        """Without any authentication (cookie or header) → 401."""
        resp = await client.post("/api/scrape", json={"url": "https://example.com"})
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["detail"]

    async def test_invalid_cookie_returns_401(self, client):
        """Malformed JWT in ``access_token`` cookie → 401."""
        client.cookies.set("access_token", "not-a-valid-jwt")
        resp = await client.post(
            "/api/scrape",
            json={"url": "https://example.com"},
        )
        assert resp.status_code == 401
        # decode_jwt raises "Invalid token" for any JWT-decoding failure
        assert "Invalid token" in resp.json()["detail"]

    async def test_cookie_takes_precedence_over_header(self, client):
        """When both cookie and Authorization header are present, cookie wins."""
        user_dict = {
            "id": "00000000-0000-0000-0000-000000000000",
            "email": "precedence@test.com",
            "created_at": None,
        }
        cookie_token = create_jwt(user_dict["id"])
        bad_token = create_jwt("00000000-0000-0000-0000-000000000001")

        client.cookies.set("access_token", cookie_token)
        with (
            mock.patch("main.article_scraper.scrape", return_value="precedence content"),
            mock.patch("app.auth.get_user_by_id", return_value=user_dict),
        ):
            resp = await client.post(
                "/api/scrape",
                json={"url": "https://example.com/article"},
                headers={"Authorization": f"Bearer {bad_token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "precedence content"
