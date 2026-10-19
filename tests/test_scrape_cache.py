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


async def test_scrape_ignores_expired_cached_content(client, auth_headers, test_user, db_pool):
    url = "https://example.com/old-article"
    await _save(str(test_user["id"]), url, "stale text")
    await db_pool.execute(
        "UPDATE generations SET created_at = now() - interval '25 hours' WHERE user_id = $1::uuid AND source_url = $2",
        str(test_user["id"]), url,
    )

    with mock.patch("main.article_scraper.scrape", return_value="fresh text"):
        resp = await client.post("/api/scrape", json={"url": url}, headers=auth_headers)

    assert resp.json()["content"] == "fresh text"


async def test_scrape_does_not_cache_non_http_sources(client, auth_headers, test_user):
    await _save(str(test_user["id"]), "report.pdf", "someone's uploaded pdf")

    with mock.patch("main.pdf_scraper.scrape", return_value="fresh pdf text"):
        resp = await client.post("/api/scrape", json={"url": "report.pdf"}, headers=auth_headers)

    assert resp.json() == {"content": "fresh pdf text", "source_type": "pdf", "metadata": None}


async def test_scrape_falls_back_when_cache_lookup_fails(client, auth_headers):
    with mock.patch("main.get_cached_source", side_effect=RuntimeError("db down")), \
            mock.patch("main.article_scraper.scrape", return_value="fresh text"):
        resp = await client.post("/api/scrape", json={"url": "https://example.com/a"}, headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["content"] == "fresh text"
