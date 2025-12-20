import re
from typing import Optional

from app.services.scraper.base import BaseScraper


class HorseScraper(BaseScraper):
    """Scraper for horse detail page"""

    BASE_URL = "https://db.netkeiba.com/horse"

    def scrape(self, horse_id: str) -> dict:
        """
        Scrape horse detail including course aptitude.

        Args:
            horse_id: Horse ID

        Returns:
            Horse info dictionary
        """
        url = f"{self.BASE_URL}/{horse_id}/"
        html = self.fetch(url)
        soup = self.parse_html(html)

        horse_info = {"horse_id": horse_id}

        title_elem = soup.select_one(".horse_title h1")
        if title_elem:
            horse_info["name"] = title_elem.get_text(strip=True)

        profile_table = soup.select_one(".db_prof_table")
        if profile_table:
            horse_info.update(self._parse_profile(profile_table))

        blood_table = soup.select_one(".blood_table")
        if blood_table:
            horse_info.update(self._parse_blood(blood_table))

        # Parse course aptitude
        course_aptitude = self._parse_course_aptitude(soup)
        if course_aptitude:
            horse_info["course_aptitude"] = course_aptitude

        return horse_info

    def scrape_course_aptitude(self, horse_id: str) -> dict:
        """
        Scrape course aptitude data for a horse.

        Args:
            horse_id: Horse ID

        Returns:
            Course aptitude dictionary
        """
        url = f"{self.BASE_URL}/{horse_id}/"
        html = self.fetch(url)
        soup = self.parse_html(html)

        return self._parse_course_aptitude(soup)

    def _parse_course_aptitude(self, soup) -> dict:
        """Parse course aptitude tables from horse page"""
        aptitude = {
            "track": {},      # 芝/ダート別成績
            "distance": {},   # 距離別成績
            "course": {},     # 競馬場別成績
            "condition": {},  # 馬場状態別成績
        }

        # Find performance summary tables
        tables = soup.select("table")

        for table in tables:
            # Check table headers to identify the type
            headers = table.select("th")
            if not headers:
                continue

            header_text = " ".join(h.get_text(strip=True) for h in headers)

            # Track type (芝/ダート)
            if "芝" in header_text and "ダ" in header_text:
                aptitude["track"] = self._parse_aptitude_table(table)

            # Distance
            elif any(d in header_text for d in ["1000", "1200", "1400", "1600", "1800", "2000"]):
                aptitude["distance"] = self._parse_aptitude_table(table)

            # Course (競馬場)
            elif any(c in header_text for c in ["東京", "中山", "阪神", "京都", "中京"]):
                aptitude["course"] = self._parse_aptitude_table(table)

            # Condition (馬場状態)
            elif "良" in header_text and ("稍" in header_text or "重" in header_text):
                aptitude["condition"] = self._parse_aptitude_table(table)

        return aptitude

    def _parse_aptitude_table(self, table) -> dict:
        """Parse an aptitude summary table"""
        result = {}

        rows = table.select("tr")
        if len(rows) < 2:
            return result

        # Get headers
        header_row = rows[0]
        headers = [th.get_text(strip=True) for th in header_row.select("th, td")]

        # Get data rows
        for row in rows[1:]:
            cells = row.select("td")
            if not cells:
                continue

            # First cell might be row header
            row_header = row.select_one("th")
            if row_header:
                category = row_header.get_text(strip=True)
            else:
                category = "total"

            stats = {}
            for i, cell in enumerate(cells):
                text = cell.get_text(strip=True)
                if i < len(headers):
                    header = headers[i] if i < len(headers) else f"col_{i}"

                    # Parse wins/races format like "2-1-0-3" (1着-2着-3着-着外)
                    race_match = re.search(r"(\d+)-(\d+)-(\d+)-(\d+)", text)
                    if race_match:
                        stats["wins"] = int(race_match.group(1))
                        stats["seconds"] = int(race_match.group(2))
                        stats["thirds"] = int(race_match.group(3))
                        stats["others"] = int(race_match.group(4))
                        total = sum([stats["wins"], stats["seconds"], stats["thirds"], stats["others"]])
                        if total > 0:
                            stats["win_rate"] = round(stats["wins"] / total * 100, 1)
                            stats["place_rate"] = round((stats["wins"] + stats["seconds"]) / total * 100, 1)
                            stats["show_rate"] = round((stats["wins"] + stats["seconds"] + stats["thirds"]) / total * 100, 1)
                        continue

                    # Try to parse as number
                    try:
                        if "%" in text:
                            stats[header] = float(text.replace("%", ""))
                        elif text.replace(".", "").isdigit():
                            stats[header] = float(text)
                    except ValueError:
                        stats[header] = text

            if stats:
                result[category] = stats

        return result
    
    def scrape_past_results(self, horse_id: str) -> list[dict]:
        """
        Scrape horse's past race results
        
        Args:
            horse_id: Horse ID
            
        Returns:
            List of past race results
        """
        url = f"{self.BASE_URL}/{horse_id}/"
        html = self.fetch(url)
        soup = self.parse_html(html)
        
        results = []
        result_table = soup.select_one(".db_h_race_results")
        
        if not result_table:
            return results
        
        rows = result_table.select("tr")[1:]  # Skip header
        
        for row in rows:
            try:
                result = self._parse_past_result_row(row)
                if result:
                    results.append(result)
            except Exception:
                continue
        
        return results
    
    def _parse_profile(self, table) -> dict:
        """Parse horse profile table"""
        profile = {}
        
        rows = table.select("tr")
        for row in rows:
            th = row.select_one("th")
            td = row.select_one("td")
            
            if not th or not td:
                continue
            
            label = th.get_text(strip=True)
            value = td.get_text(strip=True)
            
            if "生年月日" in label:
                year_match = re.search(r"(\d{4})年", value)
                if year_match:
                    profile["birth_year"] = int(year_match.group(1))
            
            elif "性" in label:
                if "牡" in value:
                    profile["sex"] = "牡"
                elif "牝" in value:
                    profile["sex"] = "牝"
                elif "セ" in value:
                    profile["sex"] = "セ"
            
            elif "調教師" in label:
                trainer_link = td.select_one("a")
                if trainer_link:
                    profile["trainer"] = trainer_link.get_text(strip=True)
            
            elif "馬主" in label:
                owner_link = td.select_one("a")
                if owner_link:
                    profile["owner"] = owner_link.get_text(strip=True)
        
        return profile
    
    def _parse_blood(self, table) -> dict:
        """Parse blood (pedigree) table"""
        blood = {}
        
        father_elem = table.select_one("tr:nth-child(1) td:nth-child(1) a")
        if father_elem:
            blood["father"] = father_elem.get_text(strip=True)
        
        mother_elem = table.select_one("tr:nth-child(3) td:nth-child(1) a")
        if mother_elem:
            blood["mother"] = mother_elem.get_text(strip=True)
        
        mother_father_elem = table.select_one("tr:nth-child(3) td:nth-child(2) a")
        if mother_father_elem:
            blood["mother_father"] = mother_father_elem.get_text(strip=True)
        
        return blood
    
    def _parse_past_result_row(self, row) -> Optional[dict]:
        """Parse a single past result row"""
        cells = row.select("td")
        
        if len(cells) < 10:
            return None
        
        result = {}
        
        date_elem = cells[0].select_one("a")
        if date_elem:
            result["date"] = date_elem.get_text(strip=True)
        
        race_link = cells[4].select_one("a")
        if race_link:
            href = race_link.get("href", "")
            race_id_match = re.search(r"/race/(\d+)", href)
            if race_id_match:
                result["race_id"] = race_id_match.group(1)
            result["race_name"] = race_link.get_text(strip=True)
        
        try:
            result["result"] = int(cells[11].get_text(strip=True))
        except (ValueError, IndexError):
            pass
        
        try:
            result["finish_time"] = cells[17].get_text(strip=True)
        except IndexError:
            pass
        
        return result
