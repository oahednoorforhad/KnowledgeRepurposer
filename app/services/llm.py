import logging

import json

import httpx
import openai
import tiktoken
from langsmith import wrappers, traceable
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.prompts import build_prompt

# Gemini API, tried in order: each one that is rate-limited or unavailable falls through to the next.
MODELS = (
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3-flash-preview",
)
GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_STREAM_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse"
# Errors worth trying the next model for; anything else (bad key, private video) fails the same everywhere.
FALLBACK_STATUSES = {404, 429, 500, 503}


def count_tokens(messages: list[dict], model: str = "gpt-4o") -> int:
    """Count total tokens across all messages in the message array."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")

    total = 0
    for msg in messages:
        # 4 tokens per message overhead (role + separators)
        total += 4
        total += len(enc.encode(str(msg.get("content", ""))))
    return total


VARIANT_SEPARATOR = "---VARIANT---"
HOOK_STYLES = ("a short personal story", "a contrarian take", "a numbered list of insights")


def split_variants(text: str) -> list[str]:
    return [part.strip() for part in text.split(VARIANT_SEPARATOR) if part.strip()]


def build_messages(
    transcript: str,
    creative_direction: str | None = None,
    profile: dict | None = None,
    variants: int = 1,
    video: bool = False,
) -> list[dict]:
    # Optional creative_direction is APPENDED as additive guidance —
    # it can add constraints (e.g. "keep under 8 lines") but cannot
    # override or replace any rule in the system prompt.
    user_content = (
        "Transform the attached video into a LinkedIn post "
        "following ALL rules from your system instructions."
        if video else
        "Here is the transcript to transform into a LinkedIn post "
        "following ALL rules from your system instructions:\n\n"
        f"{transcript}"
    )
    if creative_direction and creative_direction.strip():
        user_content += (
            f"\n\n---\n"
            f"Additional creative direction (apply ON TOP of all system rules, do not relax them):\n"
            f"{creative_direction.strip()}"
        )
    if variants > 1:
        styles = "; ".join(f"{i}) {s}" for i, s in enumerate(HOOK_STYLES[:variants], 1))
        user_content += (
            f"\n\n---\n"
            f"Write {variants} distinct versions of the post. Each must follow ALL system rules, "
            f"but open with a different hook style: {styles}. "
            f"Output only the posts, separated by a line containing exactly {VARIANT_SEPARATOR}"
        )
    return [
        {"role": "system", "content": build_prompt(profile)},
        {"role": "user", "content": user_content},
    ]


def build_refine_messages(post: str, instruction: str, profile: dict | None = None) -> list[dict]:
    user_content = (
        "Here is my current LinkedIn post. Rewrite it applying the instruction below, "
        "keeping ALL rules from your system instructions. Output only the rewritten post.\n\n"
        f"{post}\n\n---\nInstruction:\n{instruction.strip()}"
    )
    return [
        {"role": "system", "content": build_prompt(profile)},
        {"role": "user", "content": user_content},
    ]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((
        openai.RateLimitError,
        openai.APIConnectionError,
        openai.InternalServerError,
    )),
    before_sleep=before_sleep_log(logging.getLogger("tenacity"), logging.WARNING),
    reraise=True,
)
async def _open_stream_with_retry(client, model: str, messages: list[dict], temperature: float):
    """Open a streaming completion, retrying transient errors before any token is sent."""
    return await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=True,
        stream_options={"include_usage": True},
    )


class LLMService:
    def __init__(self, api_key: str | None = None):
        self.default_api_key = api_key

    @traceable(name="Stream LinkedIn Post")
    async def stream_post(self, messages: list[dict], api_key: str | None = None, video_url: str | None = None):
        """Yield {"delta": text} chunks, then a final {"model_used": ..., "usage": ...}.

        Falls back to the next model only if one fails before producing any text;
        once tokens are flowing, an error propagates to the caller.
        With video_url, Gemini watches the YouTube video itself (no transcript needed).
        """
        key = api_key or self.default_api_key
        if not key:
            raise ValueError("Gemini API key is required")
        if video_url:
            async for event in _stream_video(messages, key, video_url):
                yield event
            return

        # The client stays open for the whole generator and is closed on exit.
        async with openai.AsyncOpenAI(
            api_key=key,
            base_url=GEMINI_OPENAI_URL,
        ) as raw_client:
            client = wrappers.wrap_openai(raw_client)

            for model in MODELS:
                try:
                    stream = await _open_stream_with_retry(client, model, messages, temperature=0.7)
                except openai.AuthenticationError as e:
                    # A bad key fails for every model, so don't fall back; ValueError reaches the user as-is.
                    raise ValueError("Invalid API key.") from e
                except (
                    openai.NotFoundError,
                    openai.RateLimitError,
                    openai.BadRequestError,
                    openai.InternalServerError,
                    openai.APIConnectionError,
                ):
                    continue

                usage: dict = {"input_tokens": None, "output_tokens": None}
                produced = False
                try:
                    async for chunk in stream:
                        if chunk.usage:
                            usage = {
                                "input_tokens": chunk.usage.prompt_tokens,
                                "output_tokens": chunk.usage.completion_tokens,
                            }
                        text = chunk.choices[0].delta.content if chunk.choices else None
                        if text:
                            produced = True
                            yield {"delta": text}
                except Exception:
                    # Mid-stream failure: safe to try the next model only if nothing was sent yet.
                    if produced:
                        raise
                    continue
                if produced:
                    yield {"model_used": model, "usage": usage}
                    return

        raise RuntimeError(
            "All models are currently unavailable or rate-limited. "
            "Please retry in a moment."
        )


async def _stream_video(messages: list[dict], key: str, video_url: str):
    """Same contract as stream_post, over Gemini's native API: only it accepts a YouTube URL."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    user = "\n\n".join(m["content"] for m in messages if m["role"] == "user")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"file_data": {"file_uri": video_url}}, {"text": user}]}],
        # Low resolution cuts video tokens ~3x; the post depends on what is said, not on frames.
        "generationConfig": {"temperature": 0.7, "mediaResolution": "MEDIA_RESOLUTION_LOW"},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(30, read=240)) as client:
        for model in MODELS:
            produced = False
            usage: dict = {"input_tokens": None, "output_tokens": None}
            async with client.stream(
                "POST", GEMINI_STREAM_URL.format(model=model), headers={"x-goog-api-key": key}, json=body,
            ) as resp:
                if resp.status_code in FALLBACK_STATUSES:
                    continue
                if resp.status_code != 200:
                    await resp.aread()
                    try:
                        detail = resp.json()["error"]["message"]
                    except Exception:
                        detail = f"HTTP {resp.status_code}"
                    raise ValueError(f"Gemini could not process this video: {detail}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    chunk = json.loads(line[5:])
                    meta = chunk.get("usageMetadata")
                    if meta:
                        usage = {
                            "input_tokens": meta.get("promptTokenCount"),
                            "output_tokens": meta.get("candidatesTokenCount"),
                        }
                    for part in (chunk.get("candidates") or [{}])[0].get("content", {}).get("parts", []):
                        if part.get("text") and not part.get("thought"):
                            produced = True
                            yield {"delta": part["text"]}
            if produced:
                yield {"model_used": model, "usage": usage}
                return

    raise RuntimeError(
        "All models are currently unavailable or rate-limited. "
        "Please retry in a moment."
    )
