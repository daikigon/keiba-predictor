import time
from abc import ABC, abstractmethod
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.config import settings


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
    
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update(self.HEADERS)
        self._last_request_time: float = 0
    
    def _wait_for_rate_limit(self) -> None:
        """Wait to respect rate limit"""
        elapsed = time.time() - self._last_request_time
        if elapsed < settings.SCRAPE_INTERVAL:
            time.sleep(settings.SCRAPE_INTERVAL - elapsed)
    
    def fetch(self, url: str) -> str:
        """Fetch URL with rate limiting and retry logic"""
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
                return response.text
                
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
