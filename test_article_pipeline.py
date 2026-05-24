"""Quick smoke test for the article scraper pipeline and URL routing."""
from main import determine_source_type
from app.scrapers import ArticleScraper, PdfScraper, MarkdownScraper

# ── 1. Routing logic ─────────────────────────────────────────────
cases = [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
    ("https://youtu.be/dQw4w9WgXcQ", "youtube"),
    ("https://en.wikipedia.org/wiki/Python_(programming_language)", "article"),
    ("https://arxiv.org/pdf/2401.00001", "article"),   # .pdf URL still goes through HTTP
    ("/home/user/doc.pdf", "pdf"),
    ("C:\\Users\\user\\doc.md", "markdown"),
    ("notes.markdown", "markdown"),
    ("garbage123", "unknown"),
]

print("=== Routing ===")
for source, expected in cases:
    result = determine_source_type(source)
    status = "OK" if result == expected else "FAIL"
    print(f"  {status} {source!r:60} -> {result!r}  (expected {expected!r})")

# ── 2. Article scrape ────────────────────────────────────────────
print("\n=== Article Scrape (Wikipedia) ===")
scraper = ArticleScraper()
md = scraper.scrape("https://en.wikipedia.org/wiki/Python_(programming_language)")
if md:
    print(f"  OK Got {len(md)} chars of Markdown")
    print("  Preview:", md[:200].replace("\n", " "))
else:
    print("  FAIL Empty result")
