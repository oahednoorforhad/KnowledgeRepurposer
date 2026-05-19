import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware
from app.scrapers.youtube import YouTubeScraper
from app.services.llm import LLMService

load_dotenv()

app = FastAPI(title="AI Knowledge-to-LinkedIn Content Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    creative_direction: str | None = None  # Optional user guidance, appended to the transcript message
    api_key: str | None = None


class GeneratePostResponse(BaseModel):
    post: str


@app.post("/api/scrape/youtube", response_model=YouTubeTranscriptResponse)
def scrape_youtube(request: YouTubeUrlRequest):
    try:
        video_id = scraper.extract_video_id(request.url)
        result = scraper.get_transcript(video_id)
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
            creative_direction=request.creative_direction,
            api_key=request.api_key,
        )
        return GeneratePostResponse(post=post)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
