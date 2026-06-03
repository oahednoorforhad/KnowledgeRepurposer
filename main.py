import os
import urllib.parse
import re

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.scrapers import YouTubeScraper, ArticleScraper, PdfScraper, MarkdownScraper
from app.services.llm import LLMService
from app.auth import get_current_user
from app.repositories.profile_repo import get_profile
from app.repositories.generation_repo import create_generation
from app.routers.auth_router import router as auth_router
from app.routers.profile_router import router as profile_router
from app.routers.generation_router import router as generation_router
from db.connection import get_pool, close_pool
from fastapi.responses import JSONResponse
from loguru import logger
from app.services.llm import count_tokens
from app.services.rate_limiter import check_rate_limit
from app.prompts import build_prompt
from app.middleware.logging import LoggingMiddleware

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
    await close_pool()


app = FastAPI(title="AI Knowledge-to-LinkedIn Content Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "Authorization"],
)

app.add_middleware(LoggingMiddleware)

app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(generation_router)

youtube_scraper = YouTubeScraper()
article_scraper = ArticleScraper()
pdf_scraper = PdfScraper()
markdown_scraper = MarkdownScraper()
llm_service = LLMService(api_key=os.getenv("OPENAI_API_KEY"))


class YouTubeUrlRequest(BaseModel):
    url: str


class YouTubeTranscriptResponse(BaseModel):
    video_id: str
    title: str
    duration_seconds: int | None
    transcript: str
    language: str


class ScrapeRequest(BaseModel):
    url: str


class ScrapeResponse(BaseModel):
    content: str
    source_type: str
    metadata: dict | None = None


class GeneratePostRequest(BaseModel):
    transcript: str
    creative_direction: str | None = None
    api_key: str | None = None
    source_url: str | None = None
    source_type: str | None = None


class GeneratePostResponse(BaseModel):
    post: str
    generation_id: str | None = None
    model_used: str | None = None


def determine_source_type(source: str) -> str:
    source = source.strip()
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in ("http", "https"):
        if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
            return "youtube"
        return "article"
    if re.match(r"^[A-Za-z0-9_-]{11}$", source):
        return "youtube"
    if source.lower().endswith(".pdf"):
        return "pdf"
    if source.lower().endswith((".md", ".markdown")):
        return "markdown"
    return "unknown"


@app.post("/api/scrape", response_model=ScrapeResponse)
async def scrape_source(request: ScrapeRequest, user: dict | None = Depends(get_current_user)):
    source_type = determine_source_type(request.url)

    if source_type == "youtube":
        try:
            video_id = youtube_scraper.extract_video_id(request.url)
            result = youtube_scraper.get_transcript(video_id)
            return ScrapeResponse(
                content=result.transcript,
                source_type="youtube",
                metadata={
                    "video_id": result.video_id,
                    "title": result.title,
                    "duration_seconds": result.duration_seconds,
                    "language": result.language,
                }
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"YouTube extraction error: {e}")

    elif source_type == "article":
        try:
            content = article_scraper.scrape(request.url)
            if not content:
                raise HTTPException(
                    status_code=422,
                    detail="Failed to scrape readable text or convert to Markdown from the article URL."
                )
            return ScrapeResponse(content=content, source_type="article")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Article scraping error: {e}")

    elif source_type == "pdf":
        try:
            content = pdf_scraper.scrape(request.url)
            if not content:
                raise HTTPException(
                    status_code=422,
                    detail="Failed to extract text from the PDF file/URL."
                )
            return ScrapeResponse(content=content, source_type="pdf")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF extraction error: {e}")

    elif source_type == "markdown":
        try:
            content = markdown_scraper.scrape(request.url)
            if not content:
                raise HTTPException(
                    status_code=422,
                    detail="Failed to read content from the Markdown file/URL."
                )
            return ScrapeResponse(content=content, source_type="markdown")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Markdown reading error: {e}")

    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported URL/source format. Please provide a YouTube URL, an article web link, or a supported document path."
        )


@app.post("/api/scrape/youtube", response_model=YouTubeTranscriptResponse)
async def scrape_youtube(request: YouTubeUrlRequest, user: dict | None = Depends(get_current_user)):
    source_type = determine_source_type(request.url)
    if source_type != "youtube":
        raise HTTPException(
            status_code=400,
            detail="The URL provided is not a YouTube URL. Please use the general scrape endpoint for other source types."
        )
    try:
        video_id = youtube_scraper.extract_video_id(request.url)
        result = youtube_scraper.get_transcript(video_id)
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
async def health():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.warning(f"Health check DB error: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "disconnected"},
        )


@app.post("/api/scrape/pdf-upload", response_model=ScrapeResponse)
async def scrape_pdf_upload(file: UploadFile = File(...), user: dict | None = Depends(get_current_user)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are accepted.")
    _MAX_PDF_BYTES = 10 * 1024 * 1024  # 10MB
    if file.size is not None and file.size > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")
    try:
        data = await file.read(_MAX_PDF_BYTES + 1)
        if len(data) > _MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")
        content = pdf_scraper.scrape_bytes(data)
        if not content:
            raise HTTPException(
                status_code=422,
                detail="Failed to extract text from the uploaded PDF."
            )
        return ScrapeResponse(content=content, source_type="pdf", metadata={"filename": file.filename})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF upload error: {e}")


@app.post("/api/generate/linkedin-post", response_model=GeneratePostResponse)
async def generate_linkedin_post(request: GeneratePostRequest, user: dict | None = Depends(get_current_user)):
    if user:
        profile = await get_profile(user["id"])
        if not profile or not profile.get("name"):
            raise HTTPException(
                status_code=400,
                detail="Please complete your profile (name is required) before generating posts."
            )
    else:
        profile = None

    # Pre-LLM token check — guards against unbounded context consumption
    _messages_preview = [
        {"role": "system", "content": build_prompt(profile)},
        {"role": "user", "content": request.transcript},
    ]
    _token_count = count_tokens(_messages_preview)
    if _token_count > 1000000:
        raise HTTPException(
            status_code=422,
            detail=f"Input too long ({_token_count} tokens). Maximum is 1000,000 tokens including the system prompt. Please shorten your content.",
        )

    # Per-user rate limit (in-memory, resets on restart)
    if user:
        _allowed, _retry_after = check_rate_limit(str(user["id"]))
        if not _allowed:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. You can generate 20 posts per hour.",
                headers={"Retry-After": str(_retry_after)},
            )

    try:
        post, model_used, usage = llm_service.generate_linkedin_post(
            transcript=request.transcript,
            creative_direction=request.creative_direction,
            api_key=request.api_key,
            profile=profile,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

    generation_id = None
    if user:
        try:
            gen = await create_generation(
                user_id=user["id"],
                source_url=request.source_url,
                source_type=request.source_type or "youtube",
                raw_content=request.transcript[:50000],
                creative_direction=request.creative_direction,
                generated_post=post,
                model_used=model_used,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
            )
            generation_id = str(gen["id"])
        except Exception as e:
            logger.warning(f"Failed to save generation to DB: {e}")

    return GeneratePostResponse(post=post, generation_id=generation_id, model_used=model_used)
