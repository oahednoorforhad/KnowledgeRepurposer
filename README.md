# AI Knowledge-to-LinkedIn Content Engine

# System Architecture

# System Architecture

```mermaid
flowchart TD
    subgraph Frontend[Frontend (React)]
        UI[UI Components]
        Input["Input Toggle & Upload"]
        Output[Post Preview]
    end
    subgraph Backend[Backend (FastAPI)]
        API[API Endpoints]
        Scraper[Scrapers]
        LLM[LLM Service]
    end
    UI --> Input
    Input --> API
    API --> Scraper
    Scraper --> LLM
    LLM --> API
    API --> Output
    Output --> UI
```



A sleek, **single‑page web app** that extracts insights from YouTube videos, articles, PDFs or Markdown files and generates premium LinkedIn‑ready posts using LLMs.

---

## ✨ Features
- **Source flexibility** – paste a URL or upload a local PDF.
- **Fast extraction** – uses `pypdf` for PDFs, `newspaper3k` for articles, and custom YouTube transcript handling.
- **AI‑powered writing** – powered by OpenAI (or any compatible LLM service).
- **Modern UI** – glass‑morphism cards, dark theme, micro‑animations.
- **Docker‑ready** – backend (FastAPI) and frontend (Next.js) can be containerised.

---

## 🛠️ Tech Stack
| Layer | Tech |
|-------|------|
| Backend | **FastAPI** (Python) – `uvicorn` hot‑reload |
| Scrapers | `pypdf`, `requests`, `newspaper3k`, custom YouTube logic |
| LLM Service | Wrapper around OpenAI/compatible API |
| Frontend | **React** + **Tailwind‑CSS** (via Next.js) |
| Packaging | `npm` for the UI, `uv` for the Python env |

---

## 📦 Getting Started (Development)
### Prerequisites
- **Python 3.11+** and **uv** (or pip)
- **Node.js 20+** and **npm**
- An OpenAI (or compatible) API key

### Backend
```bash
# Clone the repo (already done)
cd e:/All About CSE/Oahed.ai/poster
# Install deps (using uv for fast env creation)
uv pip install -r requirements.txt
# Create a .env file
cp .env.example .env
# Fill OPENAI_API_KEY in .env
uv run uvicorn main:app --reload   # runs on http://127.0.0.1:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev   # runs on http://localhost:3000
```
Open the UI, paste a URL or click **Upload PDF**, then hit **Generate Post**.

---

## 📤 Upload PDF Flow
1. Switch the input mode to **Upload PDF** (toggle button).
2. Choose a local `.pdf` file – the UI shows the filename.
3. The file is sent as `multipart/form-data` to `/api/scrape/pdf-upload`.
4. The backend extracts the text via `PdfScraper.scrape_bytes` and returns it to the UI.
5. The content is fed into the LLM to produce a LinkedIn post.

---

## 📚 API Reference
| Endpoint | Method | Body | Returns |
|----------|--------|------|---------|
| `/api/scrape` | POST | `{ "url": "<source>" }` | `{ "content": "...", "source_type": "youtube|article|pdf|markdown" }` |
| `/api/scrape/pdf-upload` | POST (multipart) | `file` (PDF) | Same as above, `source_type` is always `pdf` |
| `/api/generate/linkedin-post` | POST | `{ "transcript": "...", "creative_direction": "optional" }` | `{ "post": "..." }` |

---

## 🐳 Docker (optional)
```dockerfile
# Dockerfile (backend)
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```
```yaml
# docker-compose.yml (backend + UI)
services:
  backend:
    build: .
    ports:
      - "8000:8000"
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
```

---

## 🙏 Contributing
Feel free to open issues or PRs. Follow the existing code‑style guidelines (KISS, SOLID, YAGNI). Tests are run via `pytest`.

---

## 📄 License
MIT – see `LICENSE` file.
