import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.config import settings

# HTML保存ディレクトリ
HTML_STORAGE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "html"


class ScraperError(Exception):
    """Base scraper exception"""
    pass


class RateLimitError(ScraperError):
    """Rate limit exceeded"""
    pass


class PageNotFoundError(ScraperError):
    """Page not found"""
    pass


class BaseScraper(ABC):
    """Base class for all scrapers"""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    }

    # サブクラスでオーバーライド: "races", "jockeys", "horses" など
    HTML_SUBDIR: str = "misc"

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        save_html: bool = True,
    ):
        self.session = session or requests.Session()
        self.session.headers.update(self.HEADERS)
        self._last_request_time: float = 0
        self._save_html = save_html
    
    def _wait_for_rate_limit(self) -> None:
        """Wait to respect rate limit"""
        elapsed = time.time() - self._last_request_time
        if elapsed < settings.SCRAPE_INTERVAL:
            time.sleep(settings.SCRAPE_INTERVAL - elapsed)

    def _get_html_path(self, identifier: str) -> Path:
        """Get file path for HTML storage"""
        return HTML_STORAGE_DIR / self.HTML_SUBDIR / f"{identifier}.html"

    def save_html(self, identifier: str, html: str) -> Path:
        """Save HTML to file"""
        path = self._get_html_path(identifier)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return path

    def load_html(self, identifier: str) -> Optional[str]:
        """Load HTML from file if exists"""
        path = self._get_html_path(identifier)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def html_exists(self, identifier: str) -> bool:
        """Check if HTML file exists"""
        return self._get_html_path(identifier).exists()

    def fetch(self, url: str, identifier: Optional[str] = None) -> str:
        """Fetch URL with rate limiting and retry logic

        Args:
            url: URL to fetch
            identifier: Optional identifier for HTML storage (e.g., race_id, jockey_id)
        """
        self._wait_for_rate_limit()

        for attempt in range(settings.SCRAPE_MAX_RETRIES):
            try:
                response = self.session.get(
                    url, timeout=settings.SCRAPE_TIMEOUT
                )
                self._last_request_time = time.time()

                if response.status_code == 404:
                    raise PageNotFoundError(f"Page not found: {url}")
                elif response.status_code == 429:
                    wait_time = settings.SCRAPE_INTERVAL * (attempt + 2)
                    time.sleep(wait_time)
                    continue
                elif response.status_code == 503:
                    time.sleep(settings.SCRAPE_INTERVAL * 2)
                    continue

                response.raise_for_status()
                # Handle EUC-JP encoding from netkeiba
                if "EUC-JP" in response.text[:500] or "euc-jp" in response.text[:500].lower():
                    response.encoding = "euc-jp"
                else:
                    response.encoding = response.apparent_encoding or "utf-8"

                html = response.text

                # Save HTML if identifier is provided and save_html is enabled
                if self._save_html and identifier:
                    self.save_html(identifier, html)

                return html

            except requests.RequestException as e:
                if attempt == settings.SCRAPE_MAX_RETRIES - 1:
                    raise ScraperError(f"Failed to fetch {url}: {e}")
                time.sleep(settings.SCRAPE_INTERVAL)

        raise ScraperError(f"Max retries exceeded for {url}")
    
    def parse_html(self, html: str) -> BeautifulSoup:
        """Parse HTML string"""
        return BeautifulSoup(html, "lxml")
    
    @abstractmethod
    def scrape(self, *args, **kwargs) -> dict:
        """Scrape data - to be implemented by subclasses"""
        raise NotImplementedError
