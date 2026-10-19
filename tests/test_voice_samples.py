"""Voice samples: stored on the profile and fed to the prompt."""

from app.prompts import build_prompt


async def test_profile_saves_sample_posts(client, auth_headers):
    resp = await client.put(
        "/profile", json={"name": "T", "sample_posts": "My old post"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert (await client.get("/profile", headers=auth_headers)).json()["sample_posts"] == "My old post"


async def test_profile_rejects_oversized_sample_posts(client, auth_headers):
    resp = await client.put(
        "/profile", json={"name": "T", "sample_posts": "x" * 6001}, headers=auth_headers
    )
    assert resp.status_code == 422
