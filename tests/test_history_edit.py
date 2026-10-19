"""Editing and refining saved generations."""

import uuid

import pytest

from app.auth import create_jwt
from app.repositories.generation_repo import create_generation
from app.repositories.user_repo import create_user


@pytest.fixture
async def generation(test_user):
    return await create_generation(
        user_id=str(test_user["id"]),
        source_url="https://example.com",
        source_type="article",
        raw_content="src",
        creative_direction=None,
        generated_post="Original post",
        model_used="m",
    )


async def test_edit_post_updates_text(client, auth_headers, generation):
    resp = await client.patch(
        f"/generations/{generation['id']}",
        json={"generated_post": "Edited post"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["generated_post"] == "Edited post"


async def test_edit_post_rejects_empty_text(client, auth_headers, generation):
    resp = await client.patch(
        f"/generations/{generation['id']}", json={"generated_post": ""}, headers=auth_headers
    )
    assert resp.status_code == 422


async def test_cannot_edit_another_users_post(client, db_pool, generation):
    other = await create_user(f"other-{uuid.uuid4().hex[:8]}@example.com", "x")
    try:
        resp = await client.patch(
            f"/generations/{generation['id']}",
            json={"generated_post": "Hijacked"},
            headers={"Authorization": f"Bearer {create_jwt(str(other['id']))}"},
        )
        assert resp.status_code == 404
    finally:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM users WHERE id = $1::uuid", other["id"])
