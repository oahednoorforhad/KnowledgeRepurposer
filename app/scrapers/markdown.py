import os
import logging
import requests

logger = logging.getLogger(__name__)


class MarkdownScraper:
    def __init__(self) -> None:
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

    def scrape(self, source: str) -> str:
        """Read Markdown from local path or fetch from URL.

        Returns the markdown text, or empty string on failure.
        """
        try:
            source = source.strip()
            if source.lower().startswith(("http://", "https://")):
                logger.info(f"Fetching Markdown from URL: {source}")
                response = requests.get(source, headers=self.headers, timeout=15)
                response.raise_for_status()
                return response.text.strip()
            else:
                logger.info(f"Reading local Markdown: {source}")
                if not os.path.exists(source):
                    logger.error(f"Local Markdown file not found: {source}")
                    return ""
                with open(source, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read().strip()

        except Exception as e:
            logger.error(f"Error reading Markdown from {source}: {e}", exc_info=True)
            return ""
