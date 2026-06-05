"""pytest fixtures for the poster API test suite.

Provides:
- db_pool: session-scoped database connection pool
- client:  httpx.AsyncClient wired to the FastAPI app
- test_user: temporary user inserted into the DB, cleaned up after each test
- auth_headers: valid JWT Authorization headers for the test user
"""

import os
os.environ.setdefault(
    "JWT_SECRET",
    "test-secret-key-that-is-at-least-32-characters-long",
)

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_jwt, hash_password
from db.connection import close_pool, get_pool
from main import app


# ---------------------------------------------------------------------------
# db_pool
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
async def db_pool():
    """Initialise the asyncpg connection pool for the test session.

    The pool is created once and shared by all tests.  It is closed
    automatically when the session ends.
    """
    pool = await get_pool()
    yield pool
    await close_pool()


# ---------------------------------------------------------------------------
# client
# ---------------------------------------------------------------------------
@pytest.fixture
async def client():
    """Return an ``httpx.AsyncClient`` that speaks ASGI directly to the app.

    Usage::

        async def test_health(client):
            resp = await client.get("/health")
            assert resp.status_code == 200
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# test_user
# ---------------------------------------------------------------------------
@pytest.fixture
async def test_user(db_pool):
    """Create a temporary user, yield its row dict, then delete it.

    The returned dict contains the keys returned by the database
    (``id``, ``email``, ``created_at``) plus ``plain_password`` so
    that tests can log in as this user if needed.
    """
    from app.repositories.user_repo import create_user

    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    password = "test-password-123"
    hashed = hash_password(password)

    user = await create_user(email, hashed)
    user["plain_password"] = password

    yield user

    conn = await db_pool.acquire()
    try:
        await conn.execute("DELETE FROM users WHERE id = $1::uuid", user["id"])
    finally:
        await db_pool.release(conn)


# ---------------------------------------------------------------------------
# auth_headers
# ---------------------------------------------------------------------------
@pytest.fixture
async def auth_headers(test_user):
    """Return ``{"Authorization": "Bearer <valid-JWT-for-test_user>"}``."""
    token = create_jwt(str(test_user["id"]))
    return {"Authorization": f"Bearer {token}"}
