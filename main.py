import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.prompts import DEFAULT_LINKEDIN_PROMPT
from app.scrapers.youtube import YouTubeScraper
from app.services.llm import LLMService

load_dotenv()

app = FastAPI(title="AI Knowledge-to-LinkedIn Content Engine")

scraper = YouTubeScraper()
llm_service = LLMService(api_key=os.getenv("OPENAI_API_KEY"))

class YouTubeUrlRequest(BaseModel):
    url: str


class YouTubeTranscriptResponse(BaseModel):
    video_id: str
    title: str
    duration_seconds: int | None
    transcript: str
    language: str


class GeneratePostRequest(BaseModel):
    transcript: str
    prompt: str | None = DEFAULT_LINKEDIN_PROMPT
    api_key: str | None = None


class GeneratePostResponse(BaseModel):
    post: str


HARDCODED_VIDEO_ID = "nWzXyjXCoCE"


@app.get("/api/scrape/youtube", response_model=YouTubeTranscriptResponse)
def scrape_youtube():
    try:
        result = scraper.get_transcript(HARDCODED_VIDEO_ID)
        return YouTubeTranscriptResponse(
            video_id=result.video_id,
            title=result.title,
            duration_seconds=result.duration_seconds,
            transcript=result.transcript,
            language=result.language,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/generate/linkedin-post", response_model=GeneratePostResponse)
def generate_linkedin_post(request: GeneratePostRequest):
    try:
        post = llm_service.generate_linkedin_post(
            transcript=request.transcript,
            prompt=request.prompt,
            api_key=request.api_key
        )
        return GeneratePostResponse(post=post)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
