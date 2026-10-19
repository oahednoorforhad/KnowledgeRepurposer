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


async def test_profile_rejects_non_string_field(client, auth_headers):
    resp = await client.put("/profile", json={"name": 5}, headers=auth_headers)
    assert resp.status_code == 422


def test_prompt_includes_sample_posts_as_voice_guide():
    prompt = build_prompt({"name": "T", "sample_posts": "  Shipped it.\nLearned a lot.  "})
    assert "EXAMPLES OF MY PAST POSTS" in prompt
    assert "Shipped it.\nLearned a lot." in prompt
    assert "Never reuse their topics" in prompt


def test_prompt_omits_section_without_samples():
    assert "EXAMPLES OF MY PAST POSTS" not in build_prompt({"name": "T", "sample_posts": "  "})
