import re
from typing import Optional

from app.services.scraper.base import BaseScraper


class TrainingScraper(BaseScraper):
    """Scraper for training (調教) data"""

    # Training data page for a race
    BASE_URL = "https://race.netkeiba.com/race/oikiri.html"
    HTML_SUBDIR = "training"

    def scrape(self, race_id: str) -> list[dict]:
        """
        Scrape training data for all horses in a race.

        Args:
            race_id: Race ID

        Returns:
            List of training data dictionaries for each horse
        """
        url = f"{self.BASE_URL}?race_id={race_id}"
        html = self.fetch(url, identifier=race_id)
        soup = self.parse_html(html)

        training_data = []

        # Find the training table
        table = soup.select_one(".OikiriTable, .HorseList, table.race_table_01")
        if not table:
            # Try alternative selector
            tables = soup.select("table")
            for t in tables:
                if "調教" in t.get_text() or "追切" in t.get_text():
                    table = t
                    break

        if not table:
            return training_data

        rows = table.select("tr")

        for row in rows[1:]:  # Skip header
            try:
                data = self._parse_training_row(row)
                if data:
                    training_data.append(data)
            except Exception:
                continue

        return training_data

    def _parse_training_row(self, row) -> Optional[dict]:
        """Parse a single training data row"""
        cells = row.select("td")

        if len(cells) < 3:
            return None

        data = {}

        # Try to get horse number
        for i, cell in enumerate(cells):
            text = cell.get_text(strip=True)

            # Horse number (usually first column with just a number)
            if i == 0 and text.isdigit():
                data["horse_number"] = int(text)
                continue

            # Horse name with link
            horse_link = cell.select_one("a[href*='/horse/']")
            if horse_link:
                href = horse_link.get("href", "")
                horse_id_match = re.search(r"/horse/(\d+)", href)
                if horse_id_match:
                    data["horse_id"] = horse_id_match.group(1)
                data["horse_name"] = horse_link.get_text(strip=True)
                continue

            # Training course (栗東坂路, 美浦南W, etc.)
            if any(course in text for course in ["栗東", "美浦", "坂路", "ウッド", "ポリ", "ダート", "芝"]):
                data["training_course"] = text
                continue

            # Training time (looks like XX.X or X:XX.X format)
            time_match = re.search(r"(\d{1,2}):?(\d{1,2}\.\d)", text)
            if time_match:
                data["training_time"] = text
                continue

            # Training evaluation (A, B, C, etc.)
            if text in ["A", "B", "C", "D", "E", "S"]:
                data["training_rank"] = text
                continue

            # Lap times (like 12.3-11.8-12.0)
            lap_match = re.search(r"(\d{1,2}\.\d)-(\d{1,2}\.\d)", text)
            if lap_match:
                data["lap_times"] = text
                continue

        return data if data.get("horse_number") or data.get("horse_id") else None

    def scrape_horse_training(self, horse_id: str) -> list[dict]:
        """
        Scrape training history for a specific horse.

        Args:
            horse_id: Horse ID

        Returns:
            List of training records
        """
        url = f"https://db.netkeiba.com/horse/{horse_id}/"
        html = self.fetch(url, identifier=f"horse_{horse_id}")
        soup = self.parse_html(html)

        training_records = []

        # Find training table in horse page
        tables = soup.select("table")
        for table in tables:
            caption = table.select_one("caption")
            if caption and "調教" in caption.get_text():
                rows = table.select("tr")
                for row in rows[1:]:
                    try:
                        record = self._parse_horse_training_row(row)
                        if record:
                            training_records.append(record)
                    except Exception:
                        continue
                break

        return training_records

    def _parse_horse_training_row(self, row) -> Optional[dict]:
        """Parse training row from horse detail page"""
        cells = row.select("td")

        if len(cells) < 4:
            return None

        record = {}

        for i, cell in enumerate(cells):
            text = cell.get_text(strip=True)

            # Date
            date_match = re.search(r"(\d{1,2})/(\d{1,2})", text)
            if date_match and "date" not in record:
                record["date"] = text
                continue

            # Course
            if any(c in text for c in ["栗東", "美浦", "坂路", "ウッド", "ポリ"]):
                record["course"] = text
                continue

            # Time
            time_match = re.search(r"(\d{1,2}\.\d)", text)
            if time_match and "time" not in record:
                record["time"] = text
                continue

            # Evaluation
            if text in ["A", "B", "C", "D", "E", "S"]:
                record["rank"] = text
                continue

        return record if record else None
