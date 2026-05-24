import io
import os
import logging
import requests
from pypdf import PdfReader

logger = logging.getLogger(__name__)


class PdfScraper:
    def __init__(self) -> None:
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

    def scrape(self, source: str) -> str:
        """Read PDF from local path or fetch from URL and extract text.

        Returns extracted text, or empty string on failure.
        """
        try:
            source = source.strip()
            # If it's a URL, download it
            if source.lower().startswith(("http://", "https://")):
                logger.info(f"Downloading PDF from URL: {source}")
                response = requests.get(source, headers=self.headers, timeout=15)
                response.raise_for_status()
                pdf_file = io.BytesIO(response.content)
            else:
                logger.info(f"Reading local PDF: {source}")
                if not os.path.exists(source):
                    logger.error(f"Local PDF file not found: {source}")
                    return ""
                pdf_file = open(source, "rb")

            # Extract text
            try:
                reader = PdfReader(pdf_file)
                text_list = []
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_list.append(page_text)

                return "\n\n".join(text_list).strip()
            finally:
                if not isinstance(pdf_file, io.BytesIO):
                    pdf_file.close()

        except Exception as e:
            logger.error(f"Error scraping PDF from {source}: {e}", exc_info=True)
            return ""

    def scrape_bytes(self, data: bytes) -> str:
        """Extract text from raw PDF bytes (e.g. from a file upload).

        Returns extracted text, or empty string on failure.
        """
        try:
            pdf_file = io.BytesIO(data)
            reader = PdfReader(pdf_file)
            text_list = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_list.append(page_text)
            return "\n\n".join(text_list).strip()
        except Exception as e:
            logger.error(f"Error scraping PDF from uploaded bytes: {e}", exc_info=True)
            return ""
