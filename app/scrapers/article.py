import logging
import requests
from html_to_markdown import convert

logger = logging.getLogger(__name__)


class ArticleScraper:
    def __init__(self) -> None:
        # Browser mimic headers to prevent automated traffic blocks
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    def scrape(self, url: str) -> str:
        """Fetch article HTML and convert it to structural Markdown.

        Returns an empty string if fetching or conversion fails.
        """
        try:
            logger.info(f"Fetching article: {url}")
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            html_content = response.text
            if not html_content:
                logger.warning(f"Empty content returned for URL: {url}")
                return ""

            # Convert HTML to Markdown using html-to-markdown convert
            result = convert(html_content)
            
            # Access content attribute from ConversionResult
            if hasattr(result, "content"):
                markdown_content = result.content
            else:
                markdown_content = str(result)

            return markdown_content.strip()

        except Exception as e:
            logger.error(f"Error scraping article from {url}: {e}", exc_info=True)
            return ""
