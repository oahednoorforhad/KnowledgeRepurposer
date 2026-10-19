"""Streaming generation: model fallback in LLMService and the NDJSON endpoint."""

import json
from types import SimpleNamespace
from unittest import mock

import httpx
import openai

from app.services import llm
from app.services.llm import VARIANT_SEPARATOR


def _chunk(text=None, usage=None):
    choices = [SimpleNamespace(delta=SimpleNamespace(content=text))] if text is not None else []
    return SimpleNamespace(choices=choices, usage=usage)


async def _aiter(items):
    for item in items:
        yield item


async def test_stream_post_falls_back_when_primary_unavailable():
    not_found = openai.NotFoundError(
        "gone", response=httpx.Response(404, request=httpx.Request("POST", "http://x")), body=None
    )
    fallback_chunks = [
        _chunk("Hello "),
        _chunk("world"),
        _chunk(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2)),
    ]

    async def fake_open(client, model, messages, temperature):
        if model == llm.PRIMARY_MODEL:
            raise not_found
        return _aiter(fallback_chunks)

    with mock.patch.object(llm, "_open_stream_with_retry", fake_open):
        events = [e async for e in llm.LLMService("k").stream_post([])]

    assert events == [
        {"delta": "Hello "},
        {"delta": "world"},
        {"model_used": llm.FALLBACK_MODEL, "usage": {"input_tokens": 10, "output_tokens": 2}},
    ]


async def test_generate_endpoint_streams_ndjson_and_saves(client, auth_headers):
    async def fake_stream(messages, api_key=None):
        yield {"delta": "Post "}
        yield {"delta": "body"}
        yield {"model_used": "m", "usage": {"input_tokens": 1, "output_tokens": 2}}

    with (
        mock.patch("main.get_profile", return_value={"name": "Tester"}),
        mock.patch("main.llm_service.stream_post", fake_stream),
    ):
        resp = await client.post(
            "/api/generate/linkedin-post",
            json={"transcript": "some source text"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(line) for line in resp.text.splitlines()]
    assert [e["delta"] for e in events[:-1]] == ["Post ", "body"]
    assert events[-1]["done"] is True and events[-1]["model_used"] == "m"
    assert len(events[-1]["generation_ids"]) == 1

    gen = await client.get(f"/generations/{events[-1]['generation_ids'][0]}", headers=auth_headers)
    assert gen.json()["generated_post"] == "Post body"


async def test_generate_endpoint_saves_each_variant(client, auth_headers):
    async def fake_stream(messages, api_key=None):
        assert "Write 2 distinct versions" in messages[1]["content"]
        yield {"delta": f"One\n{VARIANT_SEPARATOR}\nTwo"}
        yield {"model_used": "m", "usage": {"input_tokens": 5, "output_tokens": 6}}

    with (
        mock.patch("main.get_profile", return_value={"name": "Tester"}),
        mock.patch("main.llm_service.stream_post", fake_stream),
    ):
        resp = await client.post(
            "/api/generate/linkedin-post",
            json={"transcript": "src", "variants": 2},
            headers=auth_headers,
        )

    ids = json.loads(resp.text.splitlines()[-1])["generation_ids"]
    gens = [(await client.get(f"/generations/{i}", headers=auth_headers)).json() for i in ids]
    assert [g["generated_post"] for g in gens] == ["One", "Two"]
    assert [g["input_tokens"] for g in gens] == [5, None]


async def test_generate_endpoint_rejects_too_many_variants(client, auth_headers):
    resp = await client.post(
        "/api/generate/linkedin-post",
        json={"transcript": "src", "variants": 4},
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_generate_endpoint_reports_llm_error_in_stream(client, auth_headers):
    async def failing_stream(messages, api_key=None):
        raise RuntimeError("All models are currently unavailable")
        yield  # pragma: no cover

    with (
        mock.patch("main.get_profile", return_value={"name": "Tester"}),
        mock.patch("main.llm_service.stream_post", failing_stream),
    ):
        resp = await client.post(
            "/api/generate/linkedin-post",
            json={"transcript": "x"},
            headers=auth_headers,
        )

    assert [json.loads(line) for line in resp.text.splitlines()] == [
        {"error": "All models are currently unavailable"}
    ]


async def _failing_aiter(items, exc):
    for item in items:
        yield item
    raise exc


def _status_error(cls, code):
    return cls("err", response=httpx.Response(code, request=httpx.Request("POST", "http://x")), body=None)


async def test_stream_post_falls_back_when_stream_fails_before_text():
    async def fake_open(client, model, messages, temperature):
        if model == llm.PRIMARY_MODEL:
            return _failing_aiter([_chunk("")], _status_error(openai.InternalServerError, 500))
        return _aiter([_chunk("ok")])

    with mock.patch.object(llm, "_open_stream_with_retry", fake_open):
        events = [e async for e in llm.LLMService("k").stream_post([])]

    assert events[0] == {"delta": "ok"}
    assert events[-1]["model_used"] == llm.FALLBACK_MODEL


async def test_stream_post_propagates_error_after_text():
    boom = _status_error(openai.InternalServerError, 500)

    async def fake_open(client, model, messages, temperature):
        return _failing_aiter([_chunk("partial")], boom)

    events = []
    with mock.patch.object(llm, "_open_stream_with_retry", fake_open):
        try:
            async for e in llm.LLMService("k").stream_post([]):
                events.append(e)
        except openai.InternalServerError as e:
            assert e is boom
        else:
            raise AssertionError("expected the mid-stream error to propagate")

    assert events == [{"delta": "partial"}]


async def test_stream_post_invalid_key_raises_without_fallback():
    calls = []

    async def fake_open(client, model, messages, temperature):
        calls.append(model)
        raise _status_error(openai.AuthenticationError, 401)

    with mock.patch.object(llm, "_open_stream_with_retry", fake_open):
        try:
            [e async for e in llm.LLMService("bad").stream_post([])]
        except ValueError as e:
            assert str(e) == "Invalid API key."
        else:
            raise AssertionError("expected ValueError")

    assert calls == [llm.PRIMARY_MODEL]
