from dataclasses import dataclass

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
