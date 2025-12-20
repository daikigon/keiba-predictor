import re
from datetime import date, datetime
from typing import Optional

from app.services.scraper.base import BaseScraper, ScraperError


class RaceListScraper(BaseScraper):
    """Scraper for race list page using db.netkeiba"""

    BASE_URL = "https://db.netkeiba.com/race/list"

    def scrape(self, target_date: date) -> list[dict]:
        """
        Scrape race list for a given date

        Args:
            target_date: Target date to scrape

        Returns:
            List of race info dictionaries
        """
        date_str = target_date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}/{date_str}/"

        html = self.fetch(url)
        soup = self.parse_html(html)

        races = []
        seen_ids = set()

        # Find all race links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            # Match pattern like /race/202406050601/
            race_id_match = re.search(r"/race/(\d{12})/", href)
            if race_id_match:
                race_id = race_id_match.group(1)
                if race_id not in seen_ids:
                    seen_ids.add(race_id)
                    race_name = link.get_text(strip=True)
                    races.append({
                        "race_id": race_id,
                        "date": target_date,
                        "race_name": race_name,
                    })

        return races


class RaceDetailScraper(BaseScraper):
    """Scraper for race detail page using db.netkeiba"""

    BASE_URL = "https://db.netkeiba.com/race"

    # Course code mapping
    COURSE_CODES = {
        "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
        "05": "東京", "06": "中山", "07": "中京", "08": "京都",
        "09": "阪神", "10": "小倉",
    }

    def scrape(self, race_id: str) -> dict:
        """
        Scrape race detail from db.netkeiba

        Args:
            race_id: Race ID

        Returns:
            Race detail dictionary with entries
        """
        url = f"{self.BASE_URL}/{race_id}/"
        html = self.fetch(url)
        soup = self.parse_html(html)

        race_info = self._parse_race_info(soup, race_id)
        entries = self._parse_entries(soup)

        race_info["entries"] = entries
        return race_info

    def _parse_race_info(self, soup, race_id: str) -> dict:
        """Parse race info from db.netkeiba page"""
        race_data = {
            "race_id": race_id,
            "course": self._get_course_from_id(race_id),
            "race_number": self._get_race_number_from_id(race_id),
        }

        # Get race name from h1
        title_elem = soup.select_one(".racedata h1, .data_intro h1")
        if title_elem:
            race_data["race_name"] = title_elem.get_text(strip=True)

        # Get race data (distance, condition, etc.)
        race_data_elem = soup.select_one(".racedata, .data_intro")
        if race_data_elem:
            text = race_data_elem.get_text()

            # Distance
            distance_match = re.search(r"(\d+)m", text)
            if distance_match:
                race_data["distance"] = int(distance_match.group(1))

            # Track type
            if "芝" in text:
                race_data["track_type"] = "芝"
            elif "ダート" in text or "ダ" in text:
                race_data["track_type"] = "ダート"

            # Condition
            condition_match = re.search(r"(芝|ダ)\s*:\s*(良|稍重|重|不良)", text)
            if condition_match:
                race_data["condition"] = condition_match.group(2)

            # Grade
            grade_patterns = ["(G1)", "(G2)", "(G3)", "(L)", "オープン", "3勝", "2勝", "1勝", "新馬", "未勝利"]
            for grade in grade_patterns:
                if grade in text:
                    race_data["grade"] = grade.replace("(", "").replace(")", "")
                    break

        return race_data

    def _parse_entries(self, soup) -> list[dict]:
        """Parse entry table from db.netkeiba"""
        entries = []

        table = soup.select_one("table.race_table_01")
        if not table:
            return entries

        rows = table.select("tr")

        for row in rows[1:]:  # Skip header row
            try:
                entry = self._parse_entry_row(row)
                if entry:
                    entries.append(entry)
            except Exception:
                continue

        return entries

    def _parse_entry_row(self, row) -> Optional[dict]:
        """Parse a single entry row from db.netkeiba"""
        cells = row.select("td")
        if len(cells) < 10:
            return None

        entry = {}

        # Cell 0: Result (着順)
        try:
            result_text = cells[0].get_text(strip=True)
            if result_text.isdigit():
                entry["result"] = int(result_text)
        except (ValueError, IndexError):
            pass

        # Cell 1: Frame number (枠番)
        try:
            entry["frame_number"] = int(cells[1].get_text(strip=True))
        except (ValueError, IndexError):
            pass

        # Cell 2: Horse number (馬番)
        try:
            entry["horse_number"] = int(cells[2].get_text(strip=True))
        except (ValueError, IndexError):
            return None

        # Cell 3: Horse name and ID
        horse_link = cells[3].select_one("a")
        if horse_link:
            href = horse_link.get("href", "")
            horse_id_match = re.search(r"/horse/(\d+)", href)
            if horse_id_match:
                entry["horse_id"] = horse_id_match.group(1)
            entry["horse_name"] = horse_link.get_text(strip=True)

        # Cell 4: Sex and age
        try:
            sex_age = cells[4].get_text(strip=True)
            if sex_age:
                entry["sex"] = sex_age[0] if sex_age else ""
                age_match = re.search(r"(\d+)", sex_age)
                if age_match:
                    entry["age"] = int(age_match.group(1))
        except (ValueError, IndexError):
            pass

        # Cell 5: Weight (斤量)
        try:
            entry["weight"] = float(cells[5].get_text(strip=True))
        except (ValueError, IndexError):
            pass

        # Cell 6: Jockey
        jockey_link = cells[6].select_one("a")
        if jockey_link:
            href = jockey_link.get("href", "")
            jockey_id_match = re.search(r"/jockey/(\d+)", href)
            if jockey_id_match:
                entry["jockey_id"] = jockey_id_match.group(1)
            entry["jockey_name"] = jockey_link.get_text(strip=True)

        # Cell 7: Time (走破タイム)
        try:
            time_text = cells[7].get_text(strip=True)
            if time_text:
                entry["finish_time"] = time_text
        except IndexError:
            pass

        # Cell 10: Odds (単勝オッズ) - may vary by table structure
        try:
            if len(cells) > 12:
                odds_text = cells[12].get_text(strip=True)
                if odds_text:
                    entry["odds"] = float(odds_text)
        except (ValueError, IndexError):
            pass

        # Cell 11: Popularity (人気)
        try:
            if len(cells) > 13:
                pop_text = cells[13].get_text(strip=True)
                if pop_text.isdigit():
                    entry["popularity"] = int(pop_text)
        except (ValueError, IndexError):
            pass

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
