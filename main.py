import json
import os
import urllib.parse
import uuid
import re

from dotenv import load_dotenv

load_dotenv()  # before app imports: app.auth reads JWT_SECRET at import time
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.scrapers import YouTubeScraper, ArticleScraper, PdfScraper, MarkdownScraper
from app.services.llm import LLMService
from app.auth import require_current_user, _validate_jwt_secret
from app.repositories.profile_repo import get_profile
from app.repositories.generation_repo import RAW_CONTENT_LIMIT, create_generation, get_cached_source, get_generation, update_post
from app.routers.auth_router import router as auth_router
from app.routers.profile_router import router as profile_router
from app.routers.generation_router import router as generation_router
from db.connection import get_pool, close_pool
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from app.services.llm import build_messages, build_refine_messages, count_tokens, split_variants
from app.services.rate_limiter import check_rate_limit
from app.middleware.logging import LoggingMiddleware



@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_jwt_secret()
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
llm_service = LLMService(api_key=os.getenv("GEMINI_API_KEY"))


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
    variants: int = Field(1, ge=1, le=3)


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
async def scrape_source(request: ScrapeRequest, user: dict = Depends(require_current_user)):
    url = request.url.strip()
    cached = None
    if url.startswith(("http://", "https://")):
        try:
            cached = await get_cached_source(user["id"], url)
        except Exception as e:
            logger.warning(f"Scrape cache lookup failed, scraping instead: {e}")
    if cached:
        return ScrapeResponse(
            content=cached["raw_content"], source_type=cached["source_type"], metadata={"cached": True}
        )

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
async def scrape_youtube(request: YouTubeUrlRequest, user: dict = Depends(require_current_user)):
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
async def scrape_pdf_upload(file: UploadFile = File(...), user: dict = Depends(require_current_user)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are accepted.")
    _MAX_PDF_BYTES = 10 * 1024 * 1024  # 10MB
    file_size = getattr(file, "size", None)
    if file_size is not None and file_size > _MAX_PDF_BYTES:
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


async def _require_profile(user: dict) -> dict:
    profile = await get_profile(user["id"])
    if not profile or not profile.get("name"):
        raise HTTPException(
            status_code=400,
            detail="Please complete your profile (name is required) before generating posts."
        )
    return profile


def _check_generation_limits(user: dict, messages: list[dict]) -> None:
    # Pre-LLM token check — guards against unbounded context consumption
    _token_count = count_tokens(messages)
    if _token_count > 1000000:
        raise HTTPException(
            status_code=422,
            detail=f"Input too long ({_token_count} tokens). Maximum is 1000,000 tokens including the system prompt. Please shorten your content.",
        )

    # Per-user rate limit (in-memory, resets on restart)
    # ponytail: quota is charged before streaming, so failed generations still count, and a
    # client disconnect mid-stream skips saving. Upgrade: charge on first delta, save in a background task.
    _allowed, _retry_after = check_rate_limit(str(user["id"]))
    if not _allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. You can generate 20 posts per hour.",
            headers={"Retry-After": str(_retry_after)},
        )


def _stream_llm(messages: list[dict], api_key: str | None, save) -> StreamingResponse:
    """Stream NDJSON: {"delta": text}* then {"done": true, "model_used", **await save(post, final)}
    or {"error": message}. Errors after streaming starts can't change the HTTP status."""
    async def events():
        post, final = "", {}
        try:
            async for event in llm_service.stream_post(messages, api_key=api_key):
                if "delta" in event:
                    post += event["delta"]
                    yield _ndjson(event)
                else:
                    final = event
        except (ValueError, RuntimeError) as e:
            yield _ndjson({"error": str(e)})
            return
        except Exception as e:
            logger.exception(f"Generation failed: {e}")
            yield _ndjson({"error": "Generation failed. Please retry."})
            return

        try:
            saved = await save(post, final)
        except ValueError as e:  # save() rejected the output
            yield _ndjson({"error": str(e)})
            return
        except Exception as e:
            logger.warning(f"Failed to save generation to DB: {e}")
            yield _ndjson({"error": "The post was written but couldn't be saved. Please retry."})
            return
        yield _ndjson({"done": True, "model_used": final.get("model_used"), **saved})

    return StreamingResponse(events(), media_type="application/x-ndjson")


def _ndjson(obj: dict) -> str:
    return json.dumps(obj) + "\n"


@app.post("/api/generate/linkedin-post")
async def generate_linkedin_post(request: GeneratePostRequest, user: dict = Depends(require_current_user)):
    profile = await _require_profile(user)
    messages = build_messages(request.transcript, request.creative_direction, profile, request.variants)
    _check_generation_limits(user, messages)

    async def save(post: str, final: dict) -> dict:
        usage = final.get("usage", {})
        generation_ids = []
        if request.variants > 1:
            posts = split_variants(post)
            if len(posts) != request.variants:
                logger.warning(f"Requested {request.variants} versions, model returned {len(posts)}")
        else:
            posts = [post.strip()] if post.strip() else []
        # One history row per version; the call's token usage is recorded on the first.
        for i, variant in enumerate(posts):
            gen = await create_generation(
                user_id=user["id"],
                source_url=request.source_url,
                source_type=request.source_type or "youtube",
                raw_content=request.transcript[:RAW_CONTENT_LIMIT],
                creative_direction=request.creative_direction,
                generated_post=variant,
                model_used=final.get("model_used"),
                input_tokens=usage.get("input_tokens") if i == 0 else None,
                output_tokens=usage.get("output_tokens") if i == 0 else None,
            )
            generation_ids.append(str(gen["id"]))
        return {"generation_ids": generation_ids}

    return _stream_llm(messages, request.api_key, save)


class RefineRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=1000)
    api_key: str | None = None


@app.post("/generations/{generation_id}/refine")
async def refine_generation(generation_id: uuid.UUID, request: RefineRequest, user: dict = Depends(require_current_user)):
    generation_id = str(generation_id)
    gen = await get_generation(generation_id, user["id"])
    if gen is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    profile = await _require_profile(user)
    messages = build_refine_messages(gen["generated_post"], request.instruction, profile)
    _check_generation_limits(user, messages)

    async def save(post: str, final: dict) -> dict:
        post = post.strip()
        if not post or len(post) > 10000:  # same bounds as PATCH /generations/{id}
            raise ValueError("The refined post was empty or too long, so it wasn't saved. Please retry.")
        if await update_post(generation_id, user["id"], post) is None:
            raise ValueError("This post was deleted while refining, so the result wasn't saved.")
        return {"generation_id": generation_id}

    return _stream_llm(messages, request.api_key, save)
