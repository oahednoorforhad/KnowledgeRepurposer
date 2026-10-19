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


def test_refine_messages_include_post_and_instruction():
    from app.services.llm import build_refine_messages

    system, user = build_refine_messages("My post", "  make it shorter ", {"name": "T"})
    assert system["role"] == "system" and "T" in system["content"]
    assert "My post" in user["content"]
    assert user["content"].endswith("Instruction:\nmake it shorter")


async def test_refine_streams_and_overwrites_post(client, auth_headers, generation):
    import json
    from unittest import mock

    async def fake_stream(messages, api_key=None):
        assert "Original post" in messages[1]["content"]
        yield {"delta": "Shorter post"}
        yield {"model_used": "m", "usage": {}}

    with (
        mock.patch("main.get_profile", return_value={"name": "Tester"}),
        mock.patch("main.llm_service.stream_post", fake_stream),
    ):
        resp = await client.post(
            f"/generations/{generation['id']}/refine",
            json={"instruction": "make it shorter"},
            headers=auth_headers,
        )

    events = [json.loads(line) for line in resp.text.splitlines()]
    assert events[-1] == {"done": True, "model_used": "m", "generation_id": str(generation["id"])}
    saved = await client.get(f"/generations/{generation['id']}", headers=auth_headers)
    assert saved.json()["generated_post"] == "Shorter post"


async def test_refine_unknown_generation_returns_404(client, auth_headers):
    resp = await client.post(
        f"/generations/{uuid.uuid4()}/refine", json={"instruction": "x"}, headers=auth_headers
    )
    assert resp.status_code == 404
