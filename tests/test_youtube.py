"""YouTube scraping: a cloud-IP block becomes a clear 422, and a proxy can be configured."""

from unittest import mock

from youtube_transcript_api import IpBlocked

from app.scrapers.youtube import BLOCKED_MESSAGE, YouTubeScraper


async def test_blocked_youtube_returns_clear_422(client, auth_headers, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
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


def _gemini_reply(status=200, text="hello from gemini"):
    resp = mock.Mock(ok=status == 200, status_code=status)
    resp.json.return_value = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return resp


async def test_blocked_youtube_falls_back_to_gemini(client, auth_headers, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with mock.patch("main.youtube_scraper._api.list", side_effect=IpBlocked("scwlR0QHGOk")),          mock.patch("app.scrapers.youtube.requests.post", return_value=_gemini_reply()) as post:
        resp = await client.post(
            "/api/scrape",
            json={"url": "https://www.youtube.com/watch?v=scwlR0QHGOk"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert "hello from gemini" in resp.text
    body = post.call_args.kwargs["json"]
    assert body["contents"][0]["parts"][0]["file_data"]["file_uri"].endswith("v=scwlR0QHGOk")


async def test_gemini_failure_returns_422(client, auth_headers, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with mock.patch("main.youtube_scraper._api.list", side_effect=IpBlocked("scwlR0QHGOk")),          mock.patch("app.scrapers.youtube.requests.post", return_value=_gemini_reply(status=429)):
        resp = await client.post(
            "/api/scrape",
            json={"url": "https://www.youtube.com/watch?v=scwlR0QHGOk"},
            headers=auth_headers,
        )
    assert resp.status_code == 422
    assert BLOCKED_MESSAGE in resp.json()["detail"]
