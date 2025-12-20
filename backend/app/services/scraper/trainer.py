import re
from typing import Optional

from app.services.scraper.base import BaseScraper


class TrainerScraper(BaseScraper):
    """Scraper for trainer detail page"""

    BASE_URL = "https://db.netkeiba.com/trainer"
    HTML_SUBDIR = "trainers"

    def scrape(self, trainer_id: str) -> dict:
        """
        Scrape trainer detail including win rate, place rate, etc.

        Args:
            trainer_id: Trainer ID

        Returns:
            Trainer info dictionary
        """
        url = f"{self.BASE_URL}/{trainer_id}/"
        html = self.fetch(url, identifier=trainer_id)
        soup = self.parse_html(html)

        trainer_info = {"trainer_id": trainer_id}

        # Get trainer name
        title_elem = soup.select_one(".Name_En, .trainer_title h1, h1")
        if title_elem:
            name_jp = soup.select_one(".Name_Jp")
            if name_jp:
                trainer_info["name"] = name_jp.get_text(strip=True)
            else:
                trainer_info["name"] = title_elem.get_text(strip=True)

        # Get affiliation (所属: 栗東/美浦)
        profile_table = soup.select_one(".db_prof_table, .profile_table")
        if profile_table:
            trainer_info.update(self._parse_profile(profile_table))

        # Parse performance stats
        stats = self._parse_stats(soup)
        trainer_info.update(stats)

        return trainer_info

    def _parse_profile(self, table) -> dict:
        """Parse trainer profile table"""
        profile = {}

        rows = table.select("tr")
        for row in rows:
            th = row.select_one("th")
            td = row.select_one("td")

            if not th or not td:
                continue

            label = th.get_text(strip=True)
            value = td.get_text(strip=True)

            if "所属" in label:
                if "栗東" in value:
                    profile["affiliation"] = "栗東"
                elif "美浦" in value:
                    profile["affiliation"] = "美浦"
                else:
                    profile["affiliation"] = value

        return profile

    def _parse_stats(self, soup) -> dict:
        """Parse trainer performance statistics"""
        stats = {}

        tables = soup.select("table")

        for table in tables:
            headers = table.select("th")
            header_text = " ".join(h.get_text(strip=True) for h in headers)

            if "1着" in header_text or "勝率" in header_text:
                rows = table.select("tr")

                for row in rows:
                    cells = row.select("td")
                    row_header = row.select_one("th")

                    if not row_header:
                        continue

                    row_label = row_header.get_text(strip=True)

                    if "通算" in row_label or "2024" in row_label or "2025" in row_label:
                        stats.update(self._parse_stat_row(cells))
                        break

        if not stats:
            stats = self._parse_stats_alternative(soup)

        return stats

    def _parse_stat_row(self, cells) -> dict:
        """Parse a single stats row"""
        stats = {}

        if len(cells) < 5:
            return stats

        try:
            for i, cell in enumerate(cells):
                text = cell.get_text(strip=True)

                if "%" in text or self._is_percentage(text):
                    pct = self._parse_percentage(text)

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
        """Alternative method to parse stats"""
        stats = {}

        text = soup.get_text()

        win_match = re.search(r"勝率[:\s]*(\d+\.?\d*)%?", text)
        if win_match:
            stats["win_rate"] = float(win_match.group(1))

        place_match = re.search(r"連対率[:\s]*(\d+\.?\d*)%?", text)
        if place_match:
            stats["place_rate"] = float(place_match.group(1))

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
