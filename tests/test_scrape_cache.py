"""Scrape cache: reuse a user's previously scraped content for the same URL."""

from unittest import mock

from app.repositories.generation_repo import create_generation


async def _save(user_id, url, raw):
    await create_generation(
        user_id=user_id, source_url=url, source_type="article", raw_content=raw,
        creative_direction=None, generated_post="p", model_used="m",
    )


async def test_scrape_returns_cached_content_without_scraping(client, auth_headers, test_user):
    url = "https://example.com/cached-article"
    await _save(str(test_user["id"]), url, "previously scraped text")

    with mock.patch("main.article_scraper.scrape", side_effect=AssertionError("should not scrape")):
        resp = await client.post("/api/scrape", json={"url": url}, headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json() == {
        "content": "previously scraped text", "source_type": "article", "metadata": {"cached": True}
    }


async def test_scrape_ignores_truncated_cached_content(client, auth_headers, test_user):
    url = "https://example.com/long-article"
    await _save(str(test_user["id"]), url, "x" * 50000)

    with mock.patch("main.article_scraper.scrape", return_value="fresh text"):
        resp = await client.post("/api/scrape", json={"url": url}, headers=auth_headers)

    assert resp.json()["content"] == "fresh text"
