import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

import requests
from youtube_transcript_api import RequestBlocked, YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig

BLOCKED_MESSAGE = (
    "YouTube is blocking transcript requests from this server. "
    "Paste the transcript as text instead."
)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_PROMPT = (
    "Transcribe the spoken content of this video verbatim as plain text. "
    "No timestamps, speaker labels, headings or commentary."
)


def gemini_transcript(video_id: str, api_key: str) -> str:
    """Google fetches the video itself, so YouTube's cloud-IP block does not apply. Public videos only."""
    resp = requests.post(
        GEMINI_URL,
        headers={"x-goog-api-key": api_key},
        json={
            "contents": [{"parts": [
                {"file_data": {"file_uri": f"https://www.youtube.com/watch?v={video_id}"}},
                {"text": GEMINI_PROMPT},
            ]}],
            # Low resolution cuts video tokens ~3x; the frames barely matter for a transcript.
            "generationConfig": {"mediaResolution": "MEDIA_RESOLUTION_LOW"},
        },
        timeout=240,
    )
    if not resp.ok:
        raise RuntimeError(f"Gemini could not transcribe this video ({resp.status_code}). {BLOCKED_MESSAGE}")
    parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise RuntimeError(f"Gemini returned no transcript. {BLOCKED_MESSAGE}")
    return text



@dataclass
class YouTubeTranscriptResult:
    video_id: str
    title: str
    duration_seconds: int | None
    transcript: str
    language: str


class YouTubeScraper:
    def __init__(self) -> None:
        # YouTube blocks most cloud-provider IPs (Vercel included); a residential proxy avoids that.
        proxy = os.getenv("YOUTUBE_PROXY_URL")
        self._api = YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(http_url=proxy, https_url=proxy) if proxy else None
        )

    @staticmethod
    def extract_video_id(url: str) -> str:
        """Extract video ID from a YouTube URL or bare video ID string.

        Supports:
          - https://www.youtube.com/watch?v=VIDEO_ID
          - https://youtu.be/VIDEO_ID
          - https://www.youtube.com/embed/VIDEO_ID
          - Bare video IDs (e.g. "dQw4w9WgXcQ")
        """
        url = url.strip()

        # Try parsing as a URL first
        parsed = urlparse(url)

        if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
            if parsed.path == "/watch":
                qs = parse_qs(parsed.query)
                if "v" in qs:
                    return qs["v"][0]
            elif parsed.path.startswith("/embed/"):
                return parsed.path.split("/embed/")[1].split("/")[0].split("?")[0]
            elif parsed.path.startswith("/shorts/"):
                return parsed.path.split("/shorts/")[1].split("/")[0].split("?")[0]

        if parsed.hostname in ("youtu.be",):
            return parsed.path.lstrip("/").split("/")[0].split("?")[0]

        # Fallback: treat the whole string as a bare video ID if it looks like one
        bare_id = re.match(r"^[A-Za-z0-9_-]{11}$", url)
        if bare_id:
            return url

        raise ValueError(f"Could not extract a video ID from: {url}")

    def get_transcript(
        self,
        video_id: str,
        languages: list[str] | None = None,
    ) -> YouTubeTranscriptResult:
        lang_codes = languages or ["en"]

        try:
            transcript_list = self._api.list(video_id)
            transcript = transcript_list.find_transcript(lang_codes)
            entries = transcript.fetch()
        except RequestBlocked as e:  # IpBlocked is a subclass
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError(BLOCKED_MESSAGE) from e
            return YouTubeTranscriptResult(
                video_id=video_id,
                title="",
                duration_seconds=None,
                transcript=gemini_transcript(video_id, api_key),
                language="",
            )

        transcript_text = " ".join(entry.text for entry in entries)

        return YouTubeTranscriptResult(
            video_id=video_id,
            title="",
            duration_seconds=None,
            transcript=transcript_text,
            language=transcript.language,
        )
