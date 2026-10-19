"""YouTube scraping: a cloud-IP block becomes a clear 422, and a proxy can be configured."""

from unittest import mock

from youtube_transcript_api import IpBlocked

from app.scrapers.youtube import BLOCKED_MESSAGE, YouTubeScraper


async def test_blocked_youtube_returns_clear_422(client, auth_headers):
    with mock.patch("main.youtube_scraper._api.list", side_effect=IpBlocked("scwlR0QHGOk")):
        resp = await client.post(
            "/api/scrape",
            json={"url": "https://www.youtube.com/watch?v=scwlR0QHGOk"},
            headers=auth_headers,
        )
    assert resp.status_code == 422
    assert resp.json()["detail"] == BLOCKED_MESSAGE


def test_proxy_url_env_configures_proxy(monkeypatch):
    monkeypatch.setenv("YOUTUBE_PROXY_URL", "http://user:pass@proxy.example:8080")
    assert YouTubeScraper()._api._fetcher._proxy_config is not None
    monkeypatch.delenv("YOUTUBE_PROXY_URL")
    assert YouTubeScraper()._api._fetcher._proxy_config is None
