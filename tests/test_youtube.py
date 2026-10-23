"""YouTube: links skip transcription and go straight to Gemini; the transcript endpoint reports blocks clearly."""

import json
from unittest import mock

import httpx
from youtube_transcript_api import IpBlocked

from app.scrapers.youtube import BLOCKED_MESSAGE, YouTubeScraper
from app.services import llm

VIDEO = "https://www.youtube.com/watch?v=scwlR0QHGOk"


async def test_blocked_transcript_endpoint_returns_clear_422(client, auth_headers):
    with mock.patch("main.youtube_scraper._api.list", side_effect=IpBlocked("scwlR0QHGOk")):
        resp = await client.post("/api/scrape/youtube", json={"url": VIDEO}, headers=auth_headers)
    assert resp.status_code == 422
    assert resp.json()["detail"] == BLOCKED_MESSAGE


def test_proxy_url_env_configures_proxy(monkeypatch):
    monkeypatch.setenv("YOUTUBE_PROXY_URL", "http://user:pass@proxy.example:8080")
    assert YouTubeScraper()._api._fetcher._proxy_config is not None
    monkeypatch.delenv("YOUTUBE_PROXY_URL")
    assert YouTubeScraper()._api._fetcher._proxy_config is None


async def test_scrape_youtube_skips_transcription(client, auth_headers):
    with mock.patch("main.youtube_scraper._api.list") as transcript_api:
        resp = await client.post("/api/scrape", json={"url": "https://youtu.be/scwlR0QHGOk"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"content": "", "source_type": "youtube", "metadata": {"video_id": "scwlR0QHGOk"}}
    transcript_api.assert_not_called()


async def test_generate_sends_youtube_video_to_gemini(client, auth_headers):
    seen = {}

    async def fake_stream(messages, api_key=None, video_url=None):
        seen["video_url"] = video_url
        yield {"delta": "post"}
        yield {"model_used": "m", "usage": {}}

    with (
        mock.patch("main.get_profile", return_value={"name": "Tester"}),
        mock.patch("main.llm_service.stream_post", fake_stream),
    ):
        resp = await client.post(
            "/api/generate/linkedin-post",
            json={"transcript": "", "source_url": "https://youtu.be/scwlR0QHGOk", "source_type": "youtube"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert '"done": true' in resp.text
    assert seen["video_url"] == VIDEO


def _sse(*chunks):
    return "".join(f"data: {json.dumps(c)}\r\n\r\n" for c in chunks)


def _patched_client(handler):
    real = httpx.AsyncClient
    return mock.patch.object(llm.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


async def test_stream_video_falls_through_rate_limited_model():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if llm.MODELS[0] in request.url.path:
            return httpx.Response(429, json={"error": {"message": "quota"}})
        body = json.loads(request.content)
        assert body["contents"][0]["parts"][0]["file_data"]["file_uri"] == VIDEO
        return httpx.Response(200, text=_sse(
            {"candidates": [{"content": {"parts": [{"text": "thinking", "thought": True}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "Hello "}]}}]},
            {"candidates": [{"content": {"parts": [{"text": "world"}]}}],
             "usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 2}},
        ))

    with _patched_client(handler):
        events = [e async for e in llm.LLMService("k").stream_post(
            [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}], video_url=VIDEO,
        )]

    assert events == [
        {"delta": "Hello "},
        {"delta": "world"},
        {"model_used": llm.MODELS[1], "usage": {"input_tokens": 9, "output_tokens": 2}},
    ]
    assert len(calls) == 2


async def test_stream_video_reports_gemini_rejection():
    def handler(request):
        return httpx.Response(400, json={"error": {"message": "Video is private"}})

    with _patched_client(handler):
        try:
            [e async for e in llm.LLMService("k").stream_post([], video_url=VIDEO)]
        except ValueError as e:
            assert "Video is private" in str(e)
        else:
            raise AssertionError("expected ValueError")
