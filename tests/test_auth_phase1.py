"""Phase 1 tests: JWT validation, scrape auth, rate limits, input validation."""

import uuid
from unittest import mock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import _validate_jwt_secret
from app.services.rate_limiter import _requests
from main import app

# ---------------------------------------------------------------------------
# Helpers
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


# ===================================================================
# JWT secret validation
# ===================================================================


class TestJWTSecretValidation:
    """Direct unit tests of ``_validate_jwt_secret()``."""

    def test_valid_secret_does_not_raise(self):
        """A secret of 32+ characters should pass without error."""
        with mock.patch("app.auth.JWT_SECRET", "a" * 32):
            _validate_jwt_secret()  # no raise

    def test_missing_secret_raises(self):
        """An empty ``JWT_SECRET`` must raise ``RuntimeError``."""
        with mock.patch("app.auth.JWT_SECRET", ""):
            with pytest.raises(RuntimeError, match="JWT_SECRET.*not set"):
                _validate_jwt_secret()

    def test_short_secret_raises(self):
        """A secret shorter than 32 characters must raise ``RuntimeError``."""
        with mock.patch("app.auth.JWT_SECRET", "too-short"):
            with pytest.raises(RuntimeError, match="JWT_SECRET.*too short"):
                _validate_jwt_secret()


# ===================================================================
# Scrape endpoint authentication
# ===================================================================


class TestScrapeAuth:
    """``/api/scrape`` must reject unauthenticated requests."""

    async def test_returns_401_without_token(self, client):
        """Without a Bearer token the endpoint should respond 401."""
        resp = await client.post("/api/scrape", json={"url": "https://example.com"})
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["detail"]

    async def test_returns_200_with_valid_token(self, client, auth_headers):
        """With a valid JWT the endpoint passes auth; mock scraper + user repo."""
        user_dict = {
            "id": "00000000-0000-0000-0000-000000000000",
            "email": "mock@test.com",
            "created_at": None,
        }
        with (
            mock.patch("main.article_scraper.scrape", return_value="mock content"),
            mock.patch("app.auth.get_user_by_id", return_value=user_dict),
        ):
            resp = await client.post(
                "/api/scrape",
                json={"url": "https://example.com/article"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "mock content"
        assert data["source_type"] == "article"


# ---------------------------------------------------------------------------
# Module-level autouse fixture: reset rate-limit state before every test
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Clear all in-memory rate-limit state before each test."""
    _requests.clear()


# ===================================================================
# Login rate limit (5 attempts per 15 minutes)
# ===================================================================


class TestLoginRateLimit:
    """Login endpoint: 5 failed attempts allowed, the 6th returns 429."""

    IP = "10.0.0.10"

    @pytest.fixture(autouse=True)
    def _cleanup_key(self):
        """Remove any pre-existing rate-limit state for our test IP."""
        key = f"auth:login:{self.IP}"
        _requests.pop(key, None)
        yield

    async def test_login_exhaustion(self):
        client = _make_client(self.IP)
        payload = {"email": "nobody@never.com", "password": "does-not-matter-123"}

        for i in range(5):
            resp = await client.post("/auth/login", json=payload)
            assert resp.status_code == 401, (
                f"attempt {i + 1} should be 401 (invalid creds), "
                f"got {resp.status_code}"
            )

        # 6th attempt — rate limited
        resp = await client.post("/auth/login", json=payload)
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers


# ===================================================================
# Register rate limit (3 attempts per 15 minutes)
# ===================================================================


class TestRegisterRateLimit:
    """Register endpoint: 3 attempts allowed, the 4th returns 429."""

    IP = "10.0.0.11"

    @pytest.fixture(autouse=True)
    def _cleanup_key(self):
        key = f"auth:register:{self.IP}"
        _requests.pop(key, None)
        yield

    async def test_register_exhaustion(self):
        client = _make_client(self.IP)

        for i in range(3):
            email = f"pytest-ratelimit-{uuid.uuid4().hex[:8]}@test.com"
            resp = await client.post(
                "/auth/register",
                json={"email": email, "password": "test-password-ok"},
            )
            assert resp.status_code == 201, (
                f"attempt {i + 1} should be 201, got {resp.status_code}"
            )

        # 4th attempt — rate limited (unique email so we don't hit 409)
        email = f"pytest-ratelimit-{uuid.uuid4().hex[:8]}@test.com"
        resp = await client.post(
            "/auth/register",
            json={"email": email, "password": "test-password-ok"},
        )
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers


# ===================================================================
# Input validation
# ===================================================================


class TestInputValidation:
    """Pydantic ``AuthRequest`` rejects malformed email and short passwords."""

    @pytest.mark.parametrize("endpoint", ["/auth/register", "/auth/login"])
    async def test_invalid_email_returns_422(self, client, endpoint):
        resp = await client.post(
            endpoint,
            json={"email": "not-an-email", "password": "test-pass-12345"},
        )
        assert resp.status_code == 422

    async def test_register_short_password_returns_422(self, client):
        resp = await client.post(
            "/auth/register",
            json={"email": "pytest-valid@test.com", "password": "short"},
        )
        assert resp.status_code == 422

    async def test_login_short_password_reaches_verification(self, client, db_pool):
        """Accounts created before the 10-char minimum must still be able to log in."""
        from app.auth import hash_password
        from app.repositories.user_repo import create_user

        _requests.clear()
        email = f"pytest-legacy-{uuid.uuid4().hex[:8]}@example.com"
        user = await create_user(email, hash_password("short1"))
        try:
            ok = await client.post("/auth/login", json={"email": email, "password": "short1"})
            bad = await client.post("/auth/login", json={"email": email, "password": "wrong"})
            assert ok.status_code == 200
            assert bad.status_code == 401
        finally:
            async with db_pool.acquire() as conn:
                await conn.execute("DELETE FROM users WHERE id = $1::uuid", user["id"])


# ===================================================================
# Email normalization (strip → lowercase)
# ===================================================================


class TestEmailNormalization:
    """``AuthRequest.normalize_email`` strips whitespace and lowercases.

    Uses isolated client IPs so auth rate-limit state from other tests does
    not interfere.
    """

    IP = "10.0.0.20"

    @pytest.fixture(autouse=True)
    def _cleanup_keys(self):
        for endpoint in ("login", "register"):
            _requests.pop(f"auth:{endpoint}:{self.IP}", None)
        yield

    async def test_register_upper_then_login_lower(self):
        """Register with mixed-case email, then login with lowercased version."""
        client = _make_client(self.IP)
        email = f"pytest-EmailCase-{uuid.uuid4().hex[:8]}@Test.COM"
        password = "test-password-ok"

        resp = await client.post(
            "/auth/register",
            json={"email": email, "password": password},
        )
        assert resp.status_code == 201

        # Login with the lowercased email — should match the stored record
        resp = await client.post(
            "/auth/login",
            json={"email": email.lower(), "password": password},
        )
        assert resp.status_code == 200
        assert "message" in resp.json()

    async def test_login_upper_with_existing_user(self):
        """Login with uppercase form of an existing user's email should work.

        We create the user directly via ``create_user`` (no API call) so the
        register rate limit is not consumed.  Then we attempt login with the
        uppercased email.
        """
        from app.auth import hash_password
        from app.repositories.user_repo import create_user

        client = _make_client(self.IP)
        email = f"pytest-EmailUpperTest-{uuid.uuid4().hex[:8]}@Example.COM"
        password = "test-password-ok"

        user = await create_user(email, hash_password(password))

        # Login with uppercase email — normalization will lower it
        resp = await client.post(
            "/auth/login",
            json={"email": email.upper(), "password": password},
        )
        assert resp.status_code == 200
        assert "message" in resp.json()

        # Manual cleanup
        from db.connection import get_pool

        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM users WHERE id = $1::uuid", user["id"])
