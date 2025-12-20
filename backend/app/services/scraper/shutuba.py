"""
Scraper for race.netkeiba.com (race cards / 出馬表)
Used for getting today's and upcoming races before they run.
"""

import re
from datetime import date
from typing import Optional

from app.services.scraper.base import BaseScraper, ScraperError


class RaceCardListScraper(BaseScraper):
    """Scraper for today's race list from race.netkeiba.com"""

    # Use the sub endpoint which contains the actual race data (main page loads via AJAX)
    BASE_URL = "https://race.netkeiba.com/top/race_list_sub.html"

    def scrape(self, target_date: date) -> list[dict]:
        """
        Scrape race list for a given date from race.netkeiba.com

        Args:
            target_date: Target date to scrape

        Returns:
            List of race info dictionaries with race_id and basic info
        """
        date_str = target_date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}?kaisai_date={date_str}"

        html = self.fetch(url)
        soup = self.parse_html(html)

        races = []
        seen_ids = set()

        # Find all race links - look for shutuba.html links with race_id
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")

            # Match pattern like shutuba.html?race_id=202512200101
            race_id_match = re.search(r"race_id=(\d{12})", href)
            if race_id_match:
                race_id = race_id_match.group(1)
                if race_id not in seen_ids:
                    seen_ids.add(race_id)

                    # Extract race info from link text or parent elements
                    race_name = link.get_text(strip=True)

                    # Get course from race_id (positions 4-6)
                    course = self._get_course_from_id(race_id)
                    race_number = self._get_race_number_from_id(race_id)

                    races.append({
                        "race_id": race_id,
                        "date": target_date,
                        "course": course,
                        "race_number": race_number,
                        "race_name": race_name if race_name else f"{race_number}R",
                    })

        # Sort by course and race number
        races.sort(key=lambda x: (x["course"], x["race_number"]))
        return races

    # Course code mapping
    COURSE_CODES = {
        "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
        "05": "東京", "06": "中山", "07": "中京", "08": "京都",
        "09": "阪神", "10": "小倉",
    }

    def _get_course_from_id(self, race_id: str) -> str:
        """Extract course name from race_id"""
        if len(race_id) >= 6:
            course_code = race_id[4:6]
            return self.COURSE_CODES.get(course_code, "")
        return ""

    def _get_race_number_from_id(self, race_id: str) -> int:
        """Extract race number from race_id"""
        if len(race_id) >= 12:
            try:
                return int(race_id[10:12])
            except ValueError:
                pass
        return 0


class RaceCardScraper(BaseScraper):
    """Scraper for race card (shutuba/出馬表) from race.netkeiba.com"""

    BASE_URL = "https://race.netkeiba.com/race/shutuba.html"

    # Course code mapping
    COURSE_CODES = {
        "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
        "05": "東京", "06": "中山", "07": "中京", "08": "京都",
        "09": "阪神", "10": "小倉",
    }

    def scrape(self, race_id: str) -> dict:
        """
        Scrape race card from race.netkeiba.com

        Args:
            race_id: Race ID (12 digits)

        Returns:
            Race detail dictionary with entries
        """
        url = f"{self.BASE_URL}?race_id={race_id}"
        html = self.fetch(url)
        soup = self.parse_html(html)

        race_info = self._parse_race_info(soup, race_id)
        entries = self._parse_entries(soup)

        race_info["entries"] = entries
        return race_info

    def _parse_race_info(self, soup, race_id: str) -> dict:
        """Parse race info from shutuba page"""
        race_data = {
            "race_id": race_id,
            "course": self._get_course_from_id(race_id),
            "race_number": self._get_race_number_from_id(race_id),
        }

        # Extract date from race_id (first 8 digits: YYYYMMDD)
        try:
            year = int(race_id[0:4])
            month = int(race_id[4:6])
            # Note: race_id format might have course info in middle
            # Typically: YYYYCCRRNNNRR where CC=course, RR=round, NNN=day, RR=race
            race_data["date"] = date.today()  # Use today as fallback
        except (ValueError, IndexError):
            race_data["date"] = date.today()

        # Get race name from title
        title_elem = soup.select_one(".RaceName")
        if title_elem:
            race_data["race_name"] = title_elem.get_text(strip=True)

        # Get race details (distance, track type, etc.)
        race_data_elem = soup.select_one(".RaceData01")
        if race_data_elem:
            text = race_data_elem.get_text()

            # Distance
            distance_match = re.search(r"(\d{3,4})m", text)
            if distance_match:
                race_data["distance"] = int(distance_match.group(1))

            # Track type
            if "芝" in text:
                race_data["track_type"] = "芝"
            elif "ダート" in text or "ダ" in text:
                race_data["track_type"] = "ダート"

            # Weather and condition
            weather_match = re.search(r"天候:(\S+)", text)
            if weather_match:
                race_data["weather"] = weather_match.group(1)

            condition_match = re.search(r"(芝|ダート?):(\S+)", text)
            if condition_match:
                race_data["condition"] = condition_match.group(2)

        # Get grade
        race_data_02 = soup.select_one(".RaceData02")
        if race_data_02:
            text = race_data_02.get_text()
            grade_patterns = ["G1", "G2", "G3", "(L)", "オープン", "3勝", "2勝", "1勝", "新馬", "未勝利"]
            for grade in grade_patterns:
                if grade in text:
                    race_data["grade"] = grade.replace("(", "").replace(")", "")
                    break

        return race_data

    def _parse_entries(self, soup) -> list[dict]:
        """Parse entry table from shutuba page"""
        entries = []

        # Find the horse table
        table = soup.select_one(".Shutuba_Table, .HorseList, table.RaceTable01")
        if not table:
            # Try alternative selectors
            table = soup.select_one("table")

        if not table:
            return entries

        rows = table.select("tr.HorseList, tr[class*='Horse']")
        if not rows:
            rows = table.select("tr")[1:]  # Skip header

        for row in rows:
            try:
                entry = self._parse_entry_row(row)
                if entry and entry.get("horse_number"):
                    entries.append(entry)
            except Exception:
                continue

        return entries

    def _parse_entry_row(self, row) -> Optional[dict]:
        """Parse a single entry row"""
        entry = {}
        cells = row.select("td")

        if len(cells) < 4:
            return None

        # Try to find horse number (馬番)
        for i, cell in enumerate(cells):
            text = cell.get_text(strip=True)
            cell_class = cell.get("class", [])

            # Frame number (枠番) - usually has Waku class
            if any("Waku" in c or "waku" in c.lower() for c in cell_class):
                try:
                    entry["frame_number"] = int(text)
                except ValueError:
                    pass
                continue

            # Horse number (馬番) - usually has Umaban class or is a small number
            if any("Umaban" in c or "umaban" in c.lower() for c in cell_class):
                try:
                    entry["horse_number"] = int(text)
                except ValueError:
                    pass
                continue

        # If we couldn't find horse_number from classes, try positional
        if "horse_number" not in entry:
            for i, cell in enumerate(cells[:4]):
                text = cell.get_text(strip=True)
                if text.isdigit() and 1 <= int(text) <= 18:
                    if "frame_number" not in entry:
                        entry["frame_number"] = int(text)
                    elif "horse_number" not in entry:
                        entry["horse_number"] = int(text)
                        break

        # Find horse link
        horse_link = row.select_one("a[href*='/horse/']")
        if horse_link:
            href = horse_link.get("href", "")
            horse_id_match = re.search(r"/horse/(\d+)", href)
            if horse_id_match:
                entry["horse_id"] = horse_id_match.group(1)
            entry["horse_name"] = horse_link.get_text(strip=True)

        # Find jockey link
        jockey_link = row.select_one("a[href*='/jockey/']")
        if jockey_link:
            href = jockey_link.get("href", "")
            jockey_id_match = re.search(r"/jockey/(?:result/recent/)?(\d+)", href)
            if jockey_id_match:
                entry["jockey_id"] = jockey_id_match.group(1)
            entry["jockey_name"] = jockey_link.get_text(strip=True)

        # Find odds
        odds_elem = row.select_one(".Odds, .Popular span, td.Odds")
        if odds_elem:
            try:
                odds_text = odds_elem.get_text(strip=True)
                odds_match = re.search(r"(\d+\.?\d*)", odds_text)
                if odds_match:
                    entry["odds"] = float(odds_match.group(1))
            except ValueError:
                pass

        # Find popularity
        pop_elem = row.select_one(".Popular, .Ninki")
        if pop_elem:
            try:
                pop_text = pop_elem.get_text(strip=True)
                pop_match = re.search(r"(\d+)", pop_text)
                if pop_match:
                    entry["popularity"] = int(pop_match.group(1))
            except ValueError:
                pass

        # Find weight (斤量)
        weight_cells = row.select("td")
        for cell in weight_cells:
            text = cell.get_text(strip=True)
            # Weight is typically a number like 54.0, 55.0, 57.0
            weight_match = re.match(r"^(\d{2}(?:\.\d)?)$", text)
            if weight_match:
                try:
                    weight = float(weight_match.group(1))
                    if 48 <= weight <= 62:  # Valid weight range
                        entry["weight"] = weight
                        break
                except ValueError:
                    pass

        # Sex and age
        for cell in cells:
            text = cell.get_text(strip=True)
            sex_age_match = re.match(r"^([牡牝セ])(\d+)$", text)
            if sex_age_match:
                entry["sex"] = sex_age_match.group(1)
                entry["age"] = int(sex_age_match.group(2))
                break

        return entry if entry.get("horse_number") else None

    def _get_course_from_id(self, race_id: str) -> str:
        """Extract course name from race_id"""
        if len(race_id) >= 6:
            course_code = race_id[4:6]
            return self.COURSE_CODES.get(course_code, "")
        return ""

    def _get_race_number_from_id(self, race_id: str) -> int:
        """Extract race number from race_id"""
        if len(race_id) >= 12:
            try:
                return int(race_id[10:12])
            except ValueError:
                pass
        return 0
