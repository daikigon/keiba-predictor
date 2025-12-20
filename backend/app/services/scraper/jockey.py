import re
from typing import Optional

from app.services.scraper.base import BaseScraper


class JockeyScraper(BaseScraper):
    """Scraper for jockey detail page"""

    BASE_URL = "https://db.netkeiba.com/jockey"
    HTML_SUBDIR = "jockeys"

    def scrape(self, jockey_id: str) -> dict:
        """
        Scrape jockey detail including win rate, place rate, etc.

        Args:
            jockey_id: Jockey ID

        Returns:
            Jockey info dictionary
        """
        url = f"{self.BASE_URL}/{jockey_id}/"
        html = self.fetch(url, identifier=jockey_id)
        soup = self.parse_html(html)

        jockey_info = {"jockey_id": jockey_id}

        # Get jockey name from .Name h1 element
        # Format on netkeiba: "岩田康誠　(イワタヤスナリ)"
        name_elem = soup.select_one(".Name h1")
        if name_elem:
            name_text = name_elem.get_text(strip=True)
            # Remove furigana in parentheses: "岩田康誠　(イワタヤスナリ)" -> "岩田康誠"
            if "(" in name_text:
                name_text = name_text.split("(")[0]
            # Clean up whitespace (including &nbsp;)
            name_text = name_text.strip().replace("\u00a0", "").strip()
            if name_text:
                jockey_info["name"] = name_text

        # Parse performance stats from table
        stats = self._parse_stats(soup)
        jockey_info.update(stats)

        return jockey_info

    def _parse_stats(self, soup) -> dict:
        """Parse jockey performance statistics"""
        stats = {}

        # Look for the stats table (年度別成績)
        tables = soup.select("table")

        for table in tables:
            # Find the header to identify the right table
            headers = table.select("th")
            header_text = " ".join(h.get_text(strip=True) for h in headers)

            # Look for 年度 (year) performance table
            if "1着" in header_text or "勝率" in header_text:
                rows = table.select("tr")

                for row in rows:
                    cells = row.select("td")
                    row_header = row.select_one("th")

                    if not row_header:
                        continue

                    row_label = row_header.get_text(strip=True)

                    # Get current year or total stats
                    if "通算" in row_label or "2024" in row_label or "2025" in row_label:
                        stats.update(self._parse_stat_row(cells))
                        break

        # If no stats found, try alternative parsing
        if not stats:
            stats = self._parse_stats_alternative(soup)

        return stats

    def _parse_stat_row(self, cells) -> dict:
        """Parse a single stats row"""
        stats = {}

        if len(cells) < 5:
            return stats

        try:
            # Typical column order: 年度, 1着, 2着, 3着, 着外, 勝率, 連対率, 複勝率
            # Or: 1着, 2着, 3着, 着外, 勝率, 連対率, 複勝率

            # Find columns with percentages (勝率, 連対率, 複勝率)
            for i, cell in enumerate(cells):
                text = cell.get_text(strip=True)

                # Check if it's a percentage
                if "%" in text or self._is_percentage(text):
                    pct = self._parse_percentage(text)

                    # Assign based on position (typically last 3 columns are rates)
                    remaining = len(cells) - i
                    if remaining == 3:
                        stats["win_rate"] = pct
                    elif remaining == 2:
                        stats["place_rate"] = pct
                    elif remaining == 1:
                        stats["show_rate"] = pct

        except (ValueError, IndexError):
            pass

        return stats

    def _parse_stats_alternative(self, soup) -> dict:
        """Alternative method to parse stats from page"""
        stats = {}

        # Look for text patterns like "勝率 15.2%"
        text = soup.get_text()

        # Win rate pattern
        win_match = re.search(r"勝率[:\s]*(\d+\.?\d*)%?", text)
        if win_match:
            stats["win_rate"] = float(win_match.group(1))

        # Place rate pattern (連対率)
        place_match = re.search(r"連対率[:\s]*(\d+\.?\d*)%?", text)
        if place_match:
            stats["place_rate"] = float(place_match.group(1))

        # Show rate pattern (複勝率)
        show_match = re.search(r"複勝率[:\s]*(\d+\.?\d*)%?", text)
        if show_match:
            stats["show_rate"] = float(show_match.group(1))

        return stats

    def _is_percentage(self, text: str) -> bool:
        """Check if text looks like a percentage"""
        try:
            val = float(text.replace("%", "").strip())
            return 0 <= val <= 100
        except ValueError:
            return False

    def _parse_percentage(self, text: str) -> float:
        """Parse percentage from text"""
        cleaned = text.replace("%", "").strip()
        return float(cleaned)
