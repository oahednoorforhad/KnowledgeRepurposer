import openai
from langsmith import wrappers, traceable

from app.prompts import DEFAULT_LINKEDIN_PROMPT

# Primary: NVIDIA Nemotron 3 Super 120B (1M ctx, 120B params) — confirmed live.
# Fallback: GPT-OSS 120B (131K ctx, GPT-class quality) — confirmed live.
PRIMARY_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
FALLBACK_MODEL = "openai/gpt-oss-120b:free"


class LLMService:
    def __init__(self, api_key: str | None = None):
        self.default_api_key = api_key

    @traceable(name="Generate LinkedIn Post")
    def generate_linkedin_post(
        self,
        transcript: str,
        creative_direction: str | None = None,
        api_key: str | None = None,
    ) -> str:
        key = api_key or self.default_api_key
        if not key:
            raise ValueError("OpenAI API key is required")

        client = wrappers.wrap_openai(openai.OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1"
        ))

        # ── System prompt ───────────────────────────────────────────────────
        # DEFAULT_LINKEDIN_PROMPT contains the full persona, writing rules,
        # examples, and formatting constraints for Oahed Noor Forhad.
        # This is the authoritative instruction layer. It is NEVER overwritten.
        system_content = DEFAULT_LINKEDIN_PROMPT

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

        # Try primary model, fall back gracefully on endpoint errors.
        for model in (PRIMARY_MODEL, FALLBACK_MODEL):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                )
                try:
                    content = response.choices[0].message.content
                except (IndexError, AttributeError, TypeError):
                    # Malformed response (empty choices, None message, etc.) — try next.
                    continue
                if not content or not content.strip():
                    # Empty generation — try next.
                    continue
                return content
            except (openai.NotFoundError, openai.RateLimitError, openai.BadRequestError):
                # Model unavailable, rate-limited, or request rejected — try next.
                continue

        # If both failed, surface a clear error.
        raise RuntimeError(
            "All models are currently unavailable or rate-limited. "
            "Please retry in a moment."
        )
