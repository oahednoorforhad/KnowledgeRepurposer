import openai

class LLMService:
    def __init__(self, api_key: str | None = None):
        self.default_api_key = api_key

    def generate_linkedin_post(self, transcript: str, prompt: str, api_key: str | None = None) -> str:
        key = api_key or self.default_api_key
        if not key:
            raise ValueError("OpenAI API key is required")

        client = openai.OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1"
        )

        # We construct the messages for the LLM
        # The user's prompt acts as the system instruction or user instruction
        messages = [
            {"role": "system", "content": "You are an expert content creator specializing in high-quality LinkedIn posts. "
                                          "Follow the user's prompt closely to generate the post based on the provided transcript."},
            {"role": "user", "content": f"{prompt}\n\nHere is the transcript:\n\n{transcript}"}
        ]

        response = client.chat.completions.create(
            model="openai/gpt-4o",
            messages=messages,
            temperature=0.7,
        )

        return response.choices[0].message.content
