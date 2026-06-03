import logging

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

# Primary: NVIDIA Nemotron 3 Super 120B (1M ctx, 120B params) — confirmed live.
# Fallback: GPT-OSS 120B (131K ctx, GPT-class quality) — confirmed live.
PRIMARY_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
FALLBACK_MODEL = "openai/gpt-oss-120b:free"


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
def _call_with_retry(client, model: str, messages: list[dict], temperature: float):
    """Call the OpenRouter API with exponential backoff retry on transient errors."""
    return client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )


class LLMService:
    def __init__(self, api_key: str | None = None):
        self.default_api_key = api_key

    @traceable(name="Generate LinkedIn Post")
    def generate_linkedin_post(
        self,
        transcript: str,
        creative_direction: str | None = None,
        api_key: str | None = None,
        profile: dict | None = None,
    ) -> tuple[str, str, dict]:
        key = api_key or self.default_api_key
        if not key:
            raise ValueError("OpenAI API key is required")

        client = wrappers.wrap_openai(openai.OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1"
        ))

        system_content = build_prompt(profile)

        # ── User message ────────────────────────────────────────────────────
        # Contains the raw transcript the model must transform.
        # Optional creative_direction is APPENDED as additive guidance —
        # it can add constraints (e.g. "keep under 8 lines") but cannot
        # override or replace any rule in the system prompt.
        user_content = (
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

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user",   "content": user_content},
        ]

        usage: dict = {"input_tokens": None, "output_tokens": None}

        # Try primary model, fall back gracefully on endpoint errors.
        for model in (PRIMARY_MODEL, FALLBACK_MODEL):
            try:
                response = _call_with_retry(client, model, messages, temperature=0.7)
                try:
                    content = response.choices[0].message.content
                except (IndexError, AttributeError, TypeError):
                    continue
                if not content or not content.strip():
                    continue
                # Capture token usage if provided by OpenRouter
                if response.usage:
                    usage = {
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens,
                    }
                return content, model, usage
            except (openai.NotFoundError, openai.RateLimitError, openai.BadRequestError):
                continue

        raise RuntimeError(
            "All models are currently unavailable or rate-limited. "
            "Please retry in a moment."
        )
