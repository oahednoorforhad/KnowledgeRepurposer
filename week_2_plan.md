Current State
A working MVP that extracts content from YouTube, articles, and PDFs, then generates personalized LinkedIn posts. Auth, user profiles, and generation history are functional. The system demos well but is not production-hardened for real user load.

Goal
Transform the MVP into a scalable, reliable, cost-controlled system that survives 100+ concurrent users without timeouts, runaway costs, or broken UX.

🔴 Phase 1: Critical Reliability (Week 1)
1.1 — Streaming Generation with SSE
Replace blocking POST endpoint with Server-Sent Events to stream tokens in real-time.

Why: LinkedIn post generation takes 10–30s. Users currently stare at a spinner. Streaming gives instant feedback.

Tasks:

Add sse-starlette dependency
Refactor /generate endpoint to use StreamingResponse
Update frontend to consume SSE via EventSource
Stream tokens from OpenRouter to client
Send final "done" event with generation ID for history
Files to change:

generation_router.py
app/services/generation_service.py
frontend/app/generate/page.tsx
1.2 — Async Job Queue (Celery + Redis)
Move LLM generation off the FastAPI request lifecycle.

Why: A 30s blocking request holds a worker hostage. With 10 concurrent users, the entire API freezes. A queue decouples request from work.

Tasks:

Add celery, redis, flower to dependencies
Create app/workers/celery_app.py
Create app/workers/generation_worker.py
Refactor /generate to enqueue job and return job_id
Add /jobs/{job_id}/status endpoint for polling (or pair with SSE)
Update frontend to poll or listen for job completion
Add docker-compose.yml with Redis service
Files to change:

app/services/generation_service.py
generation_router.py (new)
app/workers/ (new directory)
docker-compose.yml (new)
1.3 — Retry Logic for LLM Calls
Wrap all OpenRouter calls with exponential backoff.

Why: OpenRouter rate-limits, times out, returns 502. One failure = user sees error. Retries make it invisible.

Tasks:

Add tenacity dependency
Create app/services/llm_service.py with retry decorator
Apply @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
Catch specific exceptions: RateLimitError, Timeout, APIConnectionError
Log every retry attempt
Files to change:

app/services/llm_service.py (new)
app/services/generation_service.py (refactor to use LLMService)
1.4 — Input Size Limits
Prevent abuse and OOM crashes.

Tasks:

PDF upload: max 10MB, reject larger with 413
Extracted text: truncate to 50,000 chars before sending to LLM
Add token counting with tiktoken before LLM call
Reject requests where input + expected output > 8,000 tokens (for gpt-4o-mini context)
Files to change:

app/extractors/pdf_extractor.py
app/services/generation_service.py
🟡 Phase 2: Cost Control (Week 2)
2.1 — Per-User Rate Limiting
Add slowapi to limit generations per user per day.

Tasks:

Add slowapi dependency
Apply 20 generations/day limit per authenticated user
Use Redis as the storage backend (shared across workers)
Return 429 Too Many Requests with Retry-After header
Add /usage/me endpoint to show user's current usage
Files to change:

app/main.py
generation_router.py
app/services/usage_service.py (new)
2.2 — Cost Tracking Per Generation
Log token usage and estimated cost for every generation.

Tasks:

Capture prompt_tokens, completion_tokens from OpenRouter response
Store in generations table (add columns: input_tokens, output_tokens, estimated_cost_usd)
Create app/services/cost_calculator.py with model-specific pricing
Add aggregate query in /admin/usage (optional admin endpoint)
Files to change:

schema.sql (add columns)
generation_repo.py
app/services/cost_calculator.py (new)
2.3 — Per-User Cost Cap
Hard ceiling on monthly spend per user.

Tasks:

Add user_quotas table: user_id, month, tokens_used, cost_usd
Check quota before enqueuing generation job
Increment on job completion
Reject new jobs if over cap (configurable, default $5/month)
Files to change:

schema.sql (new table)
app/repositories/quota_repo.py (new)
app/services/quota_service.py (new)
🟠 Phase 3: Architecture Cleanup (Week 3)
3.1 — Unified Extractor Interface
All extractors share a common base class.

Tasks:

Create app/extractors/base.py with BaseExtractor ABC
Define ExtractedContent Pydantic model: text, metadata, source_type
Refactor youtube_extractor.py, article_extractor.py, pdf_extractor.py to extend base
Create ExtractorService that routes by source type
Files to change:

app/extractors/base.py (new)
app/extractors/youtube_extractor.py
app/extractors/article_extractor.py
app/extractors/pdf_extractor.py
app/services/extractor_service.py (new)
3.2 — Service Layer Split
Break up generation_service.py into single-responsibility services.

Current: generation_service does extract → fetch user → build prompt → call LLM → save → return.

Target:

ExtractorService — picks and runs the right extractor
PromptBuilder — constructs prompt from user profile + content
LLMService — calls OpenRouter (with retries)
GenerationService — orchestrates the above + saves result
Files to change:

app/services/generation_service.py (slim down to orchestration)
app/services/prompt_builder.py (new)
app/services/llm_service.py (from 1.3)
3.3 — Dependency Injection
Use FastAPI's Depends() for DB connections, current user, config.

Tasks:

Add app/dependencies/db.py → get_db_connection
Add app/dependencies/auth.py → get_current_user
Replace global imports in routers with Depends(...)
Refactor auth_router.py as the template
Files to change:

app/dependencies/ (new directory)
auth_router.py
generation_router.py
profile_router.py
🔵 Phase 4: UX & Performance (Week 4)
4.1 — Generation History with Search, Filter, Pagination
Upgrade from simple list to a real history view.

Tasks:

Add GET /generations?search=foo&source_type=youtube&page=1&limit=20 endpoint
Add full-text search index on generated_post (PostgreSQL tsvector)
Add GET /generations/{id} for detail view
Add DELETE /generations/{id} for cleanup
Frontend: replace flat list with paginated, filterable table
Files to change:

schema.sql (add tsvector index)
generation_router.py
generation_repo.py
frontend/app/history/page.tsx
4.2 — Transcript/Content Caching
Avoid re-extracting the same YouTube video or article.

Tasks:

Create extraction_cache table: source_url, content_hash, extracted_text, created_at
Check cache before extracting
TTL: 30 days for articles, 7 days for YouTube (transcripts can change)
Add admin endpoint to clear cache
Files to change:

schema.sql (new table)
app/repositories/cache_repo.py (new)
app/services/extractor_service.py
4.3 — Health Check & Observability
Make the system debuggable in production.

Tasks:

Add GET /health returning DB + Redis + OpenRouter status
Replace print() with loguru structured logging
Log every request with: user_id, endpoint, duration_ms, status
Log every LLM call with: model, tokens, cost, latency
Add request ID middleware for tracing
Files to change:

app/main.py
app/middleware/logging.py (new)
All services (replace print with logger)
🟢 Phase 5: Testing & Deployment (Week 5)
5.1 — Integration Test Suite
Test the full HTTP → DB → LLM flow with mocks.

Tasks:

Add pytest, pytest-asyncio, httpx, pytest-mock to dev deps
Create tests/conftest.py with test DB fixture
Test: register → login → generate (mocked LLM) → fetch history
Test: rate limit triggers 429
Test: invalid input returns 422
Add make test target
Files to change:

tests/ (new directory)
pyproject.toml (test config)
Makefile (new)
5.2 — Docker & Production Setup
Make it deployable.

Tasks:

Create Dockerfile for FastAPI app
Create docker-compose.yml with: api, worker, redis, postgres
Add gunicorn with uvicorn.workers.UvicornWorker (4 workers)
Add .dockerignore
Add nginx config for SSE support (long-lived connections)
Document env vars in README.md
Files to change:

Dockerfile (new)
docker-compose.yml (new)
nginx.conf (new)
README.md
5.3 — Feedback Loop
Let users rate generated posts.

Tasks:

Add feedback table: generation_id, rating (1–5), comment, created_at
Add POST /generations/{id}/feedback endpoint
Store rating with generation for future personalization
Add thumbs up/down UI in frontend
Files to change:

schema.sql (new table)
generation_router.py
app/repositories/feedback_repo.py (new)
frontend/app/history/page.tsx
Summary: Priority Order
#	Task	Impact	Effort
1	SSE streaming	🔥 Huge UX win	Medium
2	Celery job queue	🔥 Reliability	High
3	Retry logic	Reliability	Low
4	Input size limits	Cost + stability	Low
5	Per-user rate limiting	Cost control	Low
6	Cost tracking	Visibility	Medium
7	Cost caps	Business survival	Medium
8	Unified extractor interface	Maintainability	Medium
9	Service layer split	Testability	High
10	Dependency injection	Testability	Medium
11	History search/filter/pagination	UX at scale	Medium
12	Content caching	Cost + speed	Medium
13	Health check + logging	Debuggability	Low
14	Integration tests	Confidence	High
15	Docker setup	Deployability	Medium
16	Feedback loop	Future ML	Low