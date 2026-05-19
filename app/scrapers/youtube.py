import re
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi


@dataclass
class YouTubeTranscriptResult:
    video_id: str
    title: str
    duration_seconds: int | None
    transcript: str
    language: str


class YouTubeScraper:
    def __init__(self) -> None:
        self._api = YouTubeTranscriptApi()

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

        transcript_list = self._api.list(video_id)
        transcript = transcript_list.find_transcript(lang_codes)
        entries = transcript.fetch()

        transcript_text = " ".join(entry.text for entry in entries)

        return YouTubeTranscriptResult(
            video_id=video_id,
            title="",
            duration_seconds=None,
            transcript=transcript_text,
            language=transcript.language,
        )
