"""Tests for scraper functions"""
import pytest
from unittest.mock import Mock, patch
from datetime import date

from app.services.scraper.base import BaseScraper, ScraperError, PageNotFoundError
from app.services.scraper.race import RaceListScraper, RaceDetailScraper


class TestBaseScraper:
    """Tests for BaseScraper"""

    def test_headers_set(self):
        """Test that headers are set correctly"""
        scraper = RaceListScraper()
        assert "User-Agent" in scraper.session.headers

    def test_parse_html(self):
        """Test HTML parsing"""
        scraper = RaceListScraper()
        html = "<html><body><h1>Test</h1></body></html>"
        soup = scraper.parse_html(html)

        assert soup.h1.text == "Test"


class TestRaceListScraper:
    """Tests for RaceListScraper"""

    def test_scrape_returns_list(self):
        """Test that scrape returns a list"""
        scraper = RaceListScraper()

        # Mock the fetch method
        with patch.object(scraper, "fetch") as mock_fetch:
            mock_fetch.return_value = """
            <html>
            <body>
                <a href="/race/202406050601/">レース1</a>
                <a href="/race/202406050602/">レース2</a>
            </body>
            </html>
            """

            result = scraper.scrape(date(2024, 6, 5))

            assert isinstance(result, list)
            assert len(result) == 2
            assert result[0]["race_id"] == "202406050601"
            assert result[1]["race_id"] == "202406050602"


class TestRaceDetailScraper:
    """Tests for RaceDetailScraper"""

    def test_get_course_from_id(self):
        """Test extracting course from race_id"""
        scraper = RaceDetailScraper()

        assert scraper._get_course_from_id("202405050811") == "東京"
        assert scraper._get_course_from_id("202406050811") == "中山"
        assert scraper._get_course_from_id("202409050811") == "阪神"

    def test_get_race_number_from_id(self):
        """Test extracting race number from race_id"""
        scraper = RaceDetailScraper()

        assert scraper._get_race_number_from_id("202405050801") == 1
        assert scraper._get_race_number_from_id("202405050811") == 11
        assert scraper._get_race_number_from_id("202405050812") == 12


class TestScraperErrors:
    """Tests for scraper error handling"""

    def test_page_not_found_error(self):
        """Test PageNotFoundError"""
        with pytest.raises(PageNotFoundError):
            raise PageNotFoundError("Page not found")

    def test_scraper_error(self):
        """Test ScraperError"""
        with pytest.raises(ScraperError):
            raise ScraperError("General error")
