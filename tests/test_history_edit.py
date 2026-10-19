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
    other = await create_user(f"pytest-other-{uuid.uuid4().hex[:8]}@example.com", "x")
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


async def _refine_events(client, auth_headers, generation, deltas):
    import json
    from unittest import mock

    async def fake_stream(messages, api_key=None):
        for d in deltas:
            yield {"delta": d}
        yield {"model_used": "m", "usage": {}}

    with (
        mock.patch("main.get_profile", return_value={"name": "Tester"}),
        mock.patch("main.llm_service.stream_post", fake_stream),
    ):
        resp = await client.post(
            f"/generations/{generation['id']}/refine",
            json={"instruction": "x"},
            headers=auth_headers,
        )
    return [json.loads(line) for line in resp.text.splitlines()]


async def test_refine_empty_output_reports_error_and_keeps_post(client, auth_headers, generation):
    events = await _refine_events(client, auth_headers, generation, ["  ", "\n"])
    assert "error" in events[-1] and "done" not in events[-1]
    saved = await client.get(f"/generations/{generation['id']}", headers=auth_headers)
    assert saved.json()["generated_post"] == "Original post"


async def test_refine_save_failure_reports_error(client, auth_headers, generation):
    from unittest import mock

    with mock.patch("main.update_post", side_effect=RuntimeError("db down")):
        events = await _refine_events(client, auth_headers, generation, ["New post"])
    assert "couldn't be saved" in events[-1]["error"]


async def test_refine_of_deleted_generation_reports_error(client, auth_headers, generation):
    from unittest import mock

    with mock.patch("main.update_post", return_value=None):
        events = await _refine_events(client, auth_headers, generation, ["New post"])
    assert "deleted" in events[-1]["error"]


async def test_invalid_generation_id_returns_422(client, auth_headers):
    resp = await client.patch(
        "/generations/not-a-uuid", json={"generated_post": "x"}, headers=auth_headers
    )
    assert resp.status_code == 422
    resp = await client.post(
        "/generations/not-a-uuid/refine", json={"instruction": "x"}, headers=auth_headers
    )
    assert resp.status_code == 422


async def test_history_list_omits_raw_content(client, auth_headers, generation):
    rows = (await client.get("/generations", headers=auth_headers)).json()
    assert rows and "raw_content" not in rows[0]
    assert rows[0]["generated_post"] == "Original post"
