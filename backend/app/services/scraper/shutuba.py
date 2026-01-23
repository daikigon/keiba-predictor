"""
Scraper for race.netkeiba.com (race cards / 出馬表)
Used for getting today's and upcoming races before they run.
"""

import re
from datetime import date
from typing import Optional

from app.services.scraper.base import BaseScraper, ScraperError
from app.constants import (
    CENTRAL_COURSE_CODES,
    LOCAL_COURSE_CODES,
    BANEI_COURSE_CODES,
    ALL_COURSE_CODES,
    get_race_type_from_course_code,
    RACE_TYPE_CENTRAL,
    RACE_TYPE_LOCAL,
    RACE_TYPE_BANEI,
)


class RaceCardListScraper(BaseScraper):
    """Scraper for today's race list from race.netkeiba.com"""

    # Use the sub endpoint which contains the actual race data (main page loads via AJAX)
    BASE_URL = "https://race.netkeiba.com/top/race_list_sub.html"
    HTML_SUBDIR = "shutuba_lists"

    # Course codes by racing type
    COURSE_CODES_BY_TYPE = {
        RACE_TYPE_CENTRAL: set(CENTRAL_COURSE_CODES.keys()),
        RACE_TYPE_LOCAL: set(LOCAL_COURSE_CODES.keys()),
        RACE_TYPE_BANEI: set(BANEI_COURSE_CODES.keys()),
    }

    def scrape(
        self,
        target_date: date,
        jra_only: bool = False,
        race_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Scrape race list for a given date from race.netkeiba.com

        Args:
            target_date: Target date to scrape
            jra_only: If True, only return JRA (central racing) races (deprecated, use race_type)
            race_type: Filter by race type: "central", "local", "banei", or None for all

        Returns:
            List of race info dictionaries with race_id and basic info
        """
        date_str = target_date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}?kaisai_date={date_str}"

        html = self.fetch(url, identifier=date_str)
        soup = self.parse_html(html)

        races = []
        seen_ids = set()

        # Determine which race types to include
        if race_type:
            allowed_codes = self.COURSE_CODES_BY_TYPE.get(race_type, set())
        elif jra_only:
            allowed_codes = self.COURSE_CODES_BY_TYPE[RACE_TYPE_CENTRAL]
        else:
            allowed_codes = None  # Allow all

        # Find all race links - look for shutuba.html links with race_id
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")

            # Match pattern like shutuba.html?race_id=202512200101
            race_id_match = re.search(r"race_id=(\d{12})", href)
            if race_id_match:
                race_id = race_id_match.group(1)
                if race_id not in seen_ids:
                    # Filter by race type if requested
                    course_code = race_id[4:6] if len(race_id) >= 6 else ""
                    if allowed_codes is not None:
                        if course_code not in allowed_codes:
                            continue
                    seen_ids.add(race_id)

                    # Extract race info from link text or parent elements
                    race_name = link.get_text(strip=True)

                    # Get course from race_id (positions 4-6)
                    course = self._get_course_from_id(race_id)
                    race_number = self._get_race_number_from_id(race_id)

                    races.append({
                        "race_id": race_id,
                        "race_type": get_race_type_from_course_code(course_code),
                        "date": target_date,
                        "course": course,
                        "race_number": race_number,
                        "race_name": race_name if race_name else f"{race_number}R",
                    })

        # Sort by course and race number
        races.sort(key=lambda x: (x["course"], x["race_number"]))
        return races

    # Course code mapping (centralized)
    COURSE_CODES = ALL_COURSE_CODES

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
    HTML_SUBDIR = "shutuba"

    # Course code mapping (centralized)
    COURSE_CODES = ALL_COURSE_CODES

    def scrape(self, race_id: str) -> dict:
        """
        Scrape race card from race.netkeiba.com

        Args:
            race_id: Race ID (12 digits)

        Returns:
            Race detail dictionary with entries
        """
        url = f"{self.BASE_URL}?race_id={race_id}"
        html = self.fetch(url, identifier=race_id)
        soup = self.parse_html(html)

        race_info = self._parse_race_info(soup, race_id)
        entries = self._parse_entries(soup)

        race_info["entries"] = entries
        return race_info

    def _parse_race_info(self, soup, race_id: str) -> dict:
        """Parse race info from shutuba page"""
        course_code = race_id[4:6] if len(race_id) >= 6 else ""
        race_data = {
            "race_id": race_id,
            "race_type": get_race_type_from_course_code(course_code),
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

        # Get grade（より具体的なパターンを先に検索）
        race_data_02 = soup.select_one(".RaceData02")
        if race_data_02:
            text = race_data_02.get_text()
            grade_patterns = [
                "(G1)", "(G2)", "(G3)", "GI", "GII", "GIII", "G1", "G2", "G3",
                "(L)", "オープン", "OP",
                "3勝クラス", "3勝", "1600万下",
                "2勝クラス", "2勝", "1000万下",
                "1勝クラス", "1勝", "500万下",
                "新馬", "未勝利"
            ]
            for grade in grade_patterns:
                if grade in text:
                    # 正規化: カッコ除去、クラス付きを略称に統一
                    normalized = grade.replace("(", "").replace(")", "")
                    if "クラス" in normalized:
                        normalized = normalized.replace("クラス", "")
                    race_data["grade"] = normalized
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
