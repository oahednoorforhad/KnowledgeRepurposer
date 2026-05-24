import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware
import urllib.parse
import re
from app.scrapers import YouTubeScraper, ArticleScraper, PdfScraper, MarkdownScraper
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
    creative_direction: str | None = None  # Optional user guidance, appended to the transcript message
    api_key: str | None = None


class GeneratePostResponse(BaseModel):
    post: str


def determine_source_type(source: str) -> str:
    """Determine the source type from the input string (URL or path).

    Returns:
        "youtube" - for YouTube URLs
        "article" - for standard web URLs
        "pdf" - for PDF files
        "markdown" - for markdown files
        "unknown" - fallback
    """
    source = source.strip()

    # Try parsing as a URL
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in ("http", "https"):
        if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"):
            return "youtube"
        return "article"

    # Check for bare YouTube 11-char video ID
    if re.match(r"^[A-Za-z0-9_-]{11}$", source):
        return "youtube"

    # Check for PDF extension or pattern
    if source.lower().endswith(".pdf"):
        return "pdf"

    # Check for Markdown extension
    if source.lower().endswith((".md", ".markdown")):
        return "markdown"

    return "unknown"


@app.post("/api/scrape", response_model=ScrapeResponse)
def scrape_source(request: ScrapeRequest):
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
            return ScrapeResponse(
                content=content,
                source_type="article"
            )
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
            return ScrapeResponse(
                content=content,
                source_type="pdf"
            )
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
            return ScrapeResponse(
                content=content,
                source_type="markdown"
            )
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
def scrape_youtube(request: YouTubeUrlRequest):
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
def health():
    return {"status": "ok"}


@app.post("/api/scrape/pdf-upload", response_model=ScrapeResponse)
async def scrape_pdf_upload(file: UploadFile = File(...)):
    """Accept a PDF file upload and extract its text content."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are accepted.")
    try:
        data = await file.read()
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
