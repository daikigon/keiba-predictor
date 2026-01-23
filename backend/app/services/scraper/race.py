import re
import logging
from datetime import date, datetime
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

logger = logging.getLogger(__name__)


class RaceListScraper(BaseScraper):
    """Scraper for race list page using multiple sources"""

    # db.netkeiba.com - for central racing and banei
    BASE_URL = "https://db.netkeiba.com/race/list"

    # nar.netkeiba.com - for local (NAR) racing (includes all tracks like 園田)
    NAR_BASE_URL = "https://nar.netkeiba.com/top/race_list_sub.html"

    HTML_SUBDIR = "race_lists"

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
        Scrape race list for a given date

        Args:
            target_date: Target date to scrape
            jra_only: If True, only return JRA (central racing) races (deprecated, use race_type)
            race_type: Filter by race type: "central", "local", "banei", or None for all

        Returns:
            List of race info dictionaries
        """
        races = []
        seen_ids = set()

        # Determine which race types to fetch
        if race_type == RACE_TYPE_LOCAL:
            # Use nar.netkeiba.com for local races (faster and complete)
            races = self._scrape_nar(target_date, seen_ids)
        elif race_type == RACE_TYPE_CENTRAL or jra_only:
            # Use db.netkeiba.com for central races
            races = self._scrape_db_netkeiba(target_date, seen_ids, central_only=True)
        elif race_type == RACE_TYPE_BANEI:
            # Use nar.netkeiba.com for banei races (code 65)
            races = self._scrape_banei(target_date, seen_ids)
        else:
            # Fetch all race types
            # 1. Local races from nar.netkeiba.com (excludes Banei)
            local_races = self._scrape_nar(target_date, seen_ids)
            races.extend(local_races)

            # 2. Banei races from nar.netkeiba.com (code 65)
            banei_races = self._scrape_banei(target_date, seen_ids)
            races.extend(banei_races)

            # 3. Central races from db.netkeiba.com
            central_races = self._scrape_db_netkeiba(target_date, seen_ids, central_only=True)
            races.extend(central_races)

        return races

    # nar.netkeiba.comでばんえいに使用されるコード（地方競馬取得時にスキップ）
    NAR_BANEI_CODES = {"65"}

    def _scrape_nar(self, target_date: date, seen_ids: set) -> list[dict]:
        """
        Scrape local (NAR) race list from nar.netkeiba.com
        This includes all local tracks including 園田, 門別, etc.
        Note: Banei races (code 65) are excluded - use separate Banei scraper.

        Args:
            target_date: Target date to scrape
            seen_ids: Set of already seen race IDs

        Returns:
            List of race info dictionaries
        """
        date_str = target_date.strftime("%Y%m%d")
        url = f"{self.NAR_BASE_URL}?kaisai_date={date_str}"

        try:
            html = self.fetch(url, identifier=f"nar_{date_str}")
            soup = self.parse_html(html)
        except Exception as e:
            logger.warning(f"Failed to fetch NAR race list: {e}")
            return []

        races = []

        # Find all race links with race_id parameter
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            # Match pattern like race_id=202550120201
            race_id_match = re.search(r"race_id=(\d{12})", href)
            if race_id_match:
                race_id = race_id_match.group(1)
                if race_id not in seen_ids:
                    course_code = race_id[4:6] if len(race_id) >= 6 else ""

                    # Skip Banei races (code 65) - handled separately
                    if course_code in self.NAR_BANEI_CODES:
                        continue

                    seen_ids.add(race_id)
                    race_name = link.get_text(strip=True)
                    races.append({
                        "race_id": race_id,
                        "race_type": RACE_TYPE_LOCAL,
                        "date": target_date,
                        "race_name": race_name if race_name else f"{self._get_race_number(race_id)}R",
                    })

        logger.info(f"Found {len(races)} NAR races for {target_date}")
        return races

    def _scrape_banei(self, target_date: date, seen_ids: set) -> list[dict]:
        """
        Scrape Banei race list from nar.netkeiba.com (code 65)

        Args:
            target_date: Target date to scrape
            seen_ids: Set of already seen race IDs

        Returns:
            List of Banei race info dictionaries
        """
        date_str = target_date.strftime("%Y%m%d")
        url = f"{self.NAR_BASE_URL}?kaisai_date={date_str}"

        try:
            html = self.fetch(url, identifier=f"nar_{date_str}")
            soup = self.parse_html(html)
        except Exception as e:
            logger.warning(f"Failed to fetch Banei race list: {e}")
            return []

        races = []

        # Find all race links with race_id parameter
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            # Match pattern like race_id=202565120101
            race_id_match = re.search(r"race_id=(\d{12})", href)
            if race_id_match:
                race_id = race_id_match.group(1)
                if race_id not in seen_ids:
                    course_code = race_id[4:6] if len(race_id) >= 6 else ""

                    # Only include Banei races (code 65)
                    if course_code not in self.NAR_BANEI_CODES:
                        continue

                    seen_ids.add(race_id)
                    race_name = link.get_text(strip=True)
                    races.append({
                        "race_id": race_id,
                        "race_type": RACE_TYPE_BANEI,
                        "date": target_date,
                        "race_name": race_name if race_name else f"{self._get_race_number(race_id)}R",
                    })

        logger.info(f"Found {len(races)} Banei races for {target_date}")
        return races

    def _scrape_db_netkeiba(
        self,
        target_date: date,
        seen_ids: set,
        central_only: bool = False,
        banei_only: bool = False,
        exclude_local: bool = False,
    ) -> list[dict]:
        """
        Scrape race list from db.netkeiba.com

        Args:
            target_date: Target date to scrape
            seen_ids: Set of already seen race IDs
            central_only: Only return central racing
            banei_only: Only return banei racing
            exclude_local: Exclude local racing (already fetched from NAR)

        Returns:
            List of race info dictionaries
        """
        date_str = target_date.strftime("%Y%m%d")
        url = f"{self.BASE_URL}/{date_str}/"

        try:
            html = self.fetch(url, identifier=date_str)
            soup = self.parse_html(html)
        except Exception as e:
            logger.warning(f"Failed to fetch db.netkeiba race list: {e}")
            return []

        races = []

        # Determine allowed course codes
        if central_only:
            allowed_codes = self.COURSE_CODES_BY_TYPE[RACE_TYPE_CENTRAL]
        elif banei_only:
            allowed_codes = self.COURSE_CODES_BY_TYPE[RACE_TYPE_BANEI]
        elif exclude_local:
            allowed_codes = (
                self.COURSE_CODES_BY_TYPE[RACE_TYPE_CENTRAL] |
                self.COURSE_CODES_BY_TYPE[RACE_TYPE_BANEI]
            )
        else:
            allowed_codes = None

        # Find all race links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            # Match pattern like /race/202406050601/
            race_id_match = re.search(r"/race/(\d{12})/", href)
            if race_id_match:
                race_id = race_id_match.group(1)
                if race_id not in seen_ids:
                    course_code = race_id[4:6] if len(race_id) >= 6 else ""

                    # Filter by allowed codes
                    if allowed_codes is not None and course_code not in allowed_codes:
                        continue

                    seen_ids.add(race_id)
                    race_name = link.get_text(strip=True)
                    races.append({
                        "race_id": race_id,
                        "race_type": get_race_type_from_course_code(course_code),
                        "date": target_date,
                        "race_name": race_name,
                    })

        logger.info(f"Found {len(races)} races from db.netkeiba for {target_date}")
        return races

    def _get_race_number(self, race_id: str) -> int:
        """Extract race number from race_id"""
        if len(race_id) >= 12:
            try:
                return int(race_id[10:12])
            except ValueError:
                pass
        return 0


class RaceDetailScraper(BaseScraper):
    """Scraper for race detail page using db.netkeiba"""

    BASE_URL = "https://db.netkeiba.com/race"
    HTML_SUBDIR = "races"

    # Course code mapping (centralized)
    COURSE_CODES = ALL_COURSE_CODES

    def scrape(self, race_id: str) -> dict:
        """
        Scrape race detail from db.netkeiba

        Args:
            race_id: Race ID

        Returns:
            Race detail dictionary with entries
        """
        url = f"{self.BASE_URL}/{race_id}/"
        html = self.fetch(url, identifier=race_id)
        soup = self.parse_html(html)

        race_info = self._parse_race_info(soup, race_id)
        entries = self._parse_entries(soup)

        race_info["entries"] = entries
        return race_info

    def _parse_race_info(self, soup, race_id: str) -> dict:
        """Parse race info from db.netkeiba page"""
        course_code = race_id[4:6] if len(race_id) >= 6 else ""
        race_data = {
            "race_id": race_id,
            "race_type": get_race_type_from_course_code(course_code),
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

            # Grade（より具体的なパターンを先に検索）
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

            # Weather (天気)
            weather_match = re.search(r"天候\s*:\s*(晴|曇|雨|小雨|小雪|雪)", text)
            if weather_match:
                race_data["weather"] = weather_match.group(1)

            # Number of horses (頭数)
            num_horses_match = re.search(r"(\d+)頭", text)
            if num_horses_match:
                race_data["num_horses"] = int(num_horses_match.group(1))

        # Venue detail (開催) - e.g., "1回京都2日目"
        venue_elem = soup.select_one(".mainrace_data .racedata p, .data_intro .smalltxt, .race_otherdata p")
        if venue_elem:
            venue_text = venue_elem.get_text(strip=True)
            venue_match = re.search(r"(\d+)回(\S+?)(\d+)日", venue_text)
            if venue_match:
                race_data["venue_detail"] = f"{venue_match.group(1)}{venue_match.group(2)}{venue_match.group(3)}"

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
            # Match all ID formats: numeric, Banei (B+digits), or other alphanumeric
            horse_id_match = re.search(r"/horse/([a-zA-Z0-9]+)", href)
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
            # Match all ID formats: numeric, Banei (B+digits), local (alphanumeric like a05dd)
            jockey_id_match = re.search(r"/jockey/(?:result/recent/)?([a-zA-Z0-9]+)", href)
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

        # Cell 8: Margin (着差)
        try:
            if len(cells) > 8:
                margin_text = cells[8].get_text(strip=True)
                if margin_text:
                    entry["margin"] = margin_text
        except IndexError:
            pass

        # Cell 10: Corner position (通過)
        try:
            if len(cells) > 10:
                corner_text = cells[10].get_text(strip=True)
                if corner_text and re.match(r"[\d\-]+", corner_text):
                    entry["corner_position"] = corner_text
        except IndexError:
            pass

        # Cell 11: Pace (ペース)
        try:
            if len(cells) > 11:
                pace_text = cells[11].get_text(strip=True)
                if pace_text and "-" in pace_text:
                    entry["pace"] = pace_text
        except IndexError:
            pass

        # Cell 17: Last 3F (上がり3F)
        try:
            if len(cells) > 17:
                last3f_text = cells[17].get_text(strip=True)
                if last3f_text:
                    entry["last_3f"] = float(last3f_text)
        except (ValueError, IndexError):
            pass

        # Cell 12: Odds (単勝オッズ) - may vary by table structure
        try:
            if len(cells) > 12:
                odds_text = cells[12].get_text(strip=True)
                if odds_text:
                    entry["odds"] = float(odds_text)
        except (ValueError, IndexError):
            pass

        # Cell 13: Popularity (人気)
        try:
            if len(cells) > 13:
                pop_text = cells[13].get_text(strip=True)
                if pop_text.isdigit():
                    entry["popularity"] = int(pop_text)
        except (ValueError, IndexError):
            pass

        # Cell 14: Horse weight (馬体重)
        try:
            if len(cells) > 14:
                weight_text = cells[14].get_text(strip=True)
                if weight_text:
                    weight_match = re.match(r"(\d+)\(([+-]?\d+)\)", weight_text)
                    if weight_match:
                        entry["horse_weight"] = int(weight_match.group(1))
                        entry["weight_diff"] = int(weight_match.group(2))
                    elif weight_text.isdigit():
                        entry["horse_weight"] = int(weight_text)
        except (ValueError, IndexError):
            pass

        # Cell 20: Prize money (賞金)
        try:
            if len(cells) > 20:
                prize_text = cells[20].get_text(strip=True).replace(",", "")
                if prize_text and prize_text.replace(".", "").isdigit():
                    entry["prize_money"] = int(float(prize_text))
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
