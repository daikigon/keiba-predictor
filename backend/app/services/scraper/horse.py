import re
from typing import Optional

from app.services.scraper.base import BaseScraper


class HorseScraper(BaseScraper):
    """Scraper for horse detail page

    Note: netkeiba changed their page structure around August 2025.
    - Race results are now at /horse/result/{horse_id}
    - Pedigree info is at /horse/ped/{horse_id}/
    """

    BASE_URL = "https://db.netkeiba.com/horse"
    HTML_SUBDIR = "horses"

    def scrape(self, horse_id: str) -> dict:
        """
        Scrape horse detail including course aptitude.

        Args:
            horse_id: Horse ID

        Returns:
            Horse info dictionary
        """
        # Fetch main page for basic info
        url = f"{self.BASE_URL}/{horse_id}/"
        html = self.fetch(url, identifier=horse_id)
        soup = self.parse_html(html)

        horse_info = {"horse_id": horse_id}

        title_elem = soup.select_one(".horse_title h1")
        if title_elem:
            horse_info["name"] = title_elem.get_text(strip=True)

        profile_table = soup.select_one(".db_prof_table")
        if profile_table:
            horse_info.update(self._parse_profile(profile_table))

        # Fetch blood/pedigree data from dedicated page
        pedigree_url = f"{self.BASE_URL}/ped/{horse_id}/"
        try:
            pedigree_html = self.fetch(pedigree_url, identifier=f"{horse_id}_ped")
            pedigree_soup = self.parse_html(pedigree_html)
            blood_table = pedigree_soup.select_one(".blood_table")
            if blood_table:
                horse_info.update(self._parse_blood(blood_table))
        except Exception:
            pass

        # Parse course aptitude from main page
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
        html = self.fetch(url, identifier=horse_id)
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
        Scrape horse's past race results from /horse/result/{horse_id}

        Args:
            horse_id: Horse ID

        Returns:
            List of past race results
        """
        results = []

        # Fetch results from dedicated result page (new structure since Aug 2025)
        result_url = f"{self.BASE_URL}/result/{horse_id}"
        try:
            results_html = self.fetch(result_url, identifier=f"{horse_id}_result")
        except Exception:
            return results

        if not results_html:
            return results

        soup = self.parse_html(results_html)

        # Try multiple table selectors
        result_table = soup.select_one(".db_h_race_results")
        if not result_table:
            result_table = soup.select_one("table.nk_tb_common")
        if not result_table:
            result_table = soup.select_one("table")

        if not result_table:
            return results

        rows = result_table.select("tbody tr")
        if not rows:
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
        """Parse a single past result row from horse page race history table

        AJAX endpoint column order (29 columns):
        0: 日付, 1: 開催, 2: 天気, 3: R, 4: レース名, 5: 映像, 6: 頭数, 7: 枠番, 8: 馬番,
        9: オッズ, 10: 人気, 11: 着順, 12: 騎手, 13: 斤量, 14: 距離, 15: 水分量(hidden),
        16: 馬場, 17: 馬場指数, 18: タイム, 19: 着差, 20: ペース指数, 21: 通過, 22: ペース,
        23: 上り, 24: 馬体重, 25: 脚舎ペース, 26: 備考, 27: 勝ち馬, 28: 賞金
        """
        cells = row.select("td")

        if len(cells) < 20:
            return None

        result = {}

        # Cell 0: 日付
        date_elem = cells[0].select_one("a")
        if date_elem:
            result["date"] = date_elem.get_text(strip=True)

        # Cell 1: 開催
        try:
            result["venue_detail"] = cells[1].get_text(strip=True)
        except IndexError:
            pass

        # Cell 2: 天気
        try:
            weather_text = cells[2].get_text(strip=True)
            if weather_text:
                result["weather"] = weather_text
        except IndexError:
            pass

        # Cell 3: R (レース番号)
        try:
            r_text = cells[3].get_text(strip=True)
            if r_text.isdigit():
                result["race_number"] = int(r_text)
        except (ValueError, IndexError):
            pass

        # Cell 4: レース名
        race_link = cells[4].select_one("a")
        if race_link:
            href = race_link.get("href", "")
            race_id_match = re.search(r"/race/(\d+)", href)
            if race_id_match:
                result["race_id"] = race_id_match.group(1)
            result["race_name"] = race_link.get_text(strip=True)

        # Cell 5: 映像 (skip)

        # Cell 6: 頭数
        try:
            num_text = cells[6].get_text(strip=True)
            if num_text.isdigit():
                result["num_horses"] = int(num_text)
        except (ValueError, IndexError):
            pass

        # Cell 7: 枠番
        try:
            frame_text = cells[7].get_text(strip=True)
            if frame_text.isdigit():
                result["frame_number"] = int(frame_text)
        except (ValueError, IndexError):
            pass

        # Cell 8: 馬番
        try:
            horse_num_text = cells[8].get_text(strip=True)
            if horse_num_text.isdigit():
                result["horse_number"] = int(horse_num_text)
        except (ValueError, IndexError):
            pass

        # Cell 9: オッズ
        try:
            odds_text = cells[9].get_text(strip=True)
            if odds_text:
                result["odds"] = float(odds_text)
        except (ValueError, IndexError):
            pass

        # Cell 10: 人気
        try:
            pop_text = cells[10].get_text(strip=True)
            if pop_text.isdigit():
                result["popularity"] = int(pop_text)
        except (ValueError, IndexError):
            pass

        # Cell 11: 着順
        try:
            result_text = cells[11].get_text(strip=True)
            if result_text.isdigit():
                result["result"] = int(result_text)
        except (ValueError, IndexError):
            pass

        # Cell 12: 騎手
        jockey_link = cells[12].select_one("a")
        if jockey_link:
            href = jockey_link.get("href", "")
            jockey_id_match = re.search(r"/jockey/(?:result/recent/)?(\d+)", href)
            if jockey_id_match:
                result["jockey_id"] = jockey_id_match.group(1)
            result["jockey_name"] = jockey_link.get_text(strip=True)

        # Cell 13: 斤量
        try:
            weight_text = cells[13].get_text(strip=True)
            if weight_text:
                result["weight"] = float(weight_text)
        except (ValueError, IndexError):
            pass

        # Cell 14: 距離 (e.g., "ダ1800")
        try:
            distance_text = cells[14].get_text(strip=True)
            if distance_text:
                result["distance_str"] = distance_text
                # Parse track type and distance
                if distance_text.startswith("芝"):
                    result["track_type"] = "芝"
                    dist_match = re.search(r"(\d+)", distance_text)
                    if dist_match:
                        result["distance"] = int(dist_match.group(1))
                elif distance_text.startswith("ダ"):
                    result["track_type"] = "ダート"
                    dist_match = re.search(r"(\d+)", distance_text)
                    if dist_match:
                        result["distance"] = int(dist_match.group(1))
        except IndexError:
            pass

        # Cell 15: 水分量 (hidden, skip)

        # Cell 16: 馬場
        try:
            condition_text = cells[16].get_text(strip=True)
            if condition_text:
                result["condition"] = condition_text
        except IndexError:
            pass

        # Cell 17: 馬場指数 (skip)

        # Cell 18: タイム
        try:
            time_text = cells[18].get_text(strip=True)
            if time_text:
                result["finish_time"] = time_text
        except IndexError:
            pass

        # Cell 19: 着差
        try:
            margin_text = cells[19].get_text(strip=True)
            if margin_text:
                result["margin"] = margin_text
        except IndexError:
            pass

        # Cell 20: ペース指数 (skip)

        # Cell 21: 通過
        try:
            corner_text = cells[21].get_text(strip=True)
            if corner_text:
                result["corner_position"] = corner_text
        except IndexError:
            pass

        # Cell 22: ペース
        try:
            pace_text = cells[22].get_text(strip=True)
            if pace_text:
                result["pace"] = pace_text
        except IndexError:
            pass

        # Cell 23: 上り
        try:
            last3f_text = cells[23].get_text(strip=True)
            if last3f_text:
                result["last_3f"] = float(last3f_text)
        except (ValueError, IndexError):
            pass

        # Cell 24: 馬体重
        try:
            hw_text = cells[24].get_text(strip=True)
            if hw_text:
                # Parse "450(-2)" format
                hw_match = re.match(r"(\d+)\(([+-]?\d+)\)", hw_text)
                if hw_match:
                    result["horse_weight"] = int(hw_match.group(1))
                    result["weight_diff"] = int(hw_match.group(2))
                elif hw_text.isdigit():
                    result["horse_weight"] = int(hw_text)
        except (ValueError, IndexError):
            pass

        # Cell 25: 脚舎ペース (skip)
        # Cell 26: 備考 (skip)

        # Cell 27: 勝ち馬(2着馬)
        try:
            if len(cells) > 27:
                winner_link = cells[27].select_one("a")
                if winner_link:
                    result["winner_or_second"] = winner_link.get_text(strip=True)
        except IndexError:
            pass

        # Cell 28: 賞金
        try:
            if len(cells) > 28:
                prize_text = cells[28].get_text(strip=True).replace(",", "")
                if prize_text and prize_text.replace(".", "").isdigit():
                    result["prize_money"] = int(float(prize_text))
        except (ValueError, IndexError):
            pass

        return result if result.get("race_id") else None
