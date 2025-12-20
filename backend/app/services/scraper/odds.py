import re
from typing import Optional

from app.services.scraper.base import BaseScraper


class OddsScraper(BaseScraper):
    """Scraper for odds page"""

    BASE_URL = "https://race.netkeiba.com/odds/index.html"
    HTML_SUBDIR = "odds"

    def scrape(self, race_id: str) -> dict:
        """
        Scrape basic odds (win/place) for a race.

        Args:
            race_id: Race ID

        Returns:
            Odds dictionary
        """
        url = f"{self.BASE_URL}?race_id={race_id}"
        html = self.fetch(url, identifier=f"{race_id}_win")
        soup = self.parse_html(html)

        return {
            "race_id": race_id,
            "win": self._parse_win_odds(soup),
            "place": self._parse_place_odds(soup),
        }

    def scrape_all(self, race_id: str) -> dict:
        """
        Scrape all odds types for a race.

        Args:
            race_id: Race ID

        Returns:
            Complete odds dictionary
        """
        result = {
            "race_id": race_id,
            "win": [],
            "place": [],
            "quinella": [],       # 馬連
            "quinella_place": [], # ワイド
            "exacta": [],         # 馬単
            "trio": [],           # 三連複
            "trifecta": [],       # 三連単
        }

        # Win and Place odds
        basic = self.scrape(race_id)
        result["win"] = basic.get("win", [])
        result["place"] = basic.get("place", [])

        # Quinella (馬連)
        result["quinella"] = self._scrape_quinella(race_id)

        # Quinella Place (ワイド)
        result["quinella_place"] = self._scrape_quinella_place(race_id)

        # Exacta (馬単)
        result["exacta"] = self._scrape_exacta(race_id)

        # Trio (三連複)
        result["trio"] = self._scrape_trio(race_id)

        # Trifecta (三連単)
        result["trifecta"] = self._scrape_trifecta(race_id)

        return result

    def _scrape_quinella(self, race_id: str) -> list[dict]:
        """Scrape quinella (馬連) odds"""
        url = f"https://race.netkeiba.com/odds/index.html?type=b4&race_id={race_id}"
        html = self.fetch(url, identifier=f"{race_id}_quinella")
        soup = self.parse_html(html)

        return self._parse_combination_odds(soup, 2)

    def _scrape_quinella_place(self, race_id: str) -> list[dict]:
        """Scrape quinella place (ワイド) odds"""
        url = f"https://race.netkeiba.com/odds/index.html?type=b5&race_id={race_id}"
        html = self.fetch(url, identifier=f"{race_id}_quinella_place")
        soup = self.parse_html(html)

        return self._parse_combination_odds(soup, 2, has_range=True)

    def _scrape_exacta(self, race_id: str) -> list[dict]:
        """Scrape exacta (馬単) odds"""
        url = f"https://race.netkeiba.com/odds/index.html?type=b6&race_id={race_id}"
        html = self.fetch(url, identifier=f"{race_id}_exacta")
        soup = self.parse_html(html)

        return self._parse_combination_odds(soup, 2)

    def _scrape_trio(self, race_id: str) -> list[dict]:
        """Scrape trio (三連複) odds"""
        url = f"https://race.netkeiba.com/odds/index.html?type=b7&race_id={race_id}"
        html = self.fetch(url, identifier=f"{race_id}_trio")
        soup = self.parse_html(html)

        return self._parse_combination_odds(soup, 3)

    def _scrape_trifecta(self, race_id: str) -> list[dict]:
        """Scrape trifecta (三連単) odds"""
        url = f"https://race.netkeiba.com/odds/index.html?type=b8&race_id={race_id}"
        html = self.fetch(url, identifier=f"{race_id}_trifecta")
        soup = self.parse_html(html)

        return self._parse_combination_odds(soup, 3)

    def _parse_combination_odds(
        self, soup, num_horses: int, has_range: bool = False
    ) -> list[dict]:
        """Parse combination odds table"""
        odds_list = []

        tables = soup.select("table")
        for table in tables:
            rows = table.select("tr")

            for row in rows:
                try:
                    cells = row.select("td")
                    if len(cells) < 2:
                        continue

                    # Extract horse numbers from combination
                    combo_text = ""
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        # Look for combination pattern like "1-2" or "1-2-3"
                        combo_match = re.search(r"(\d+)\s*[-−]\s*(\d+)(?:\s*[-−]\s*(\d+))?", text)
                        if combo_match:
                            combo_text = text
                            break

                    if not combo_text:
                        continue

                    # Parse the combination
                    numbers = re.findall(r"\d+", combo_text)
                    if len(numbers) < num_horses:
                        continue

                    horses = [int(n) for n in numbers[:num_horses]]

                    # Find odds value
                    odds = None
                    odds_min = None
                    odds_max = None

                    for cell in cells:
                        text = cell.get_text(strip=True)
                        # Skip if it's the combination text
                        if "-" in text and text[0].isdigit():
                            continue

                        try:
                            if has_range and "-" in text:
                                # Range format "1.2-3.4"
                                parts = text.split("-")
                                if len(parts) == 2:
                                    odds_min = float(parts[0].replace(",", ""))
                                    odds_max = float(parts[1].replace(",", ""))
                            else:
                                val = float(text.replace(",", ""))
                                if val > 0:
                                    odds = val
                                    break
                        except ValueError:
                            continue

                    entry = {"horses": horses}
                    if has_range:
                        entry["odds_min"] = odds_min
                        entry["odds_max"] = odds_max
                    else:
                        entry["odds"] = odds

                    odds_list.append(entry)

                except Exception:
                    continue

        return odds_list
    
    def _parse_win_odds(self, soup) -> list[dict]:
        """Parse win (単勝) odds"""
        odds_list = []
        
        table = soup.select_one("#odds_tan_block table, .Odds_Table")
        if not table:
            return odds_list
        
        rows = table.select("tr")
        
        for row in rows:
            try:
                cells = row.select("td")
                if len(cells) < 2:
                    continue
                
                horse_num_elem = cells[0]
                odds_elem = cells[1] if len(cells) > 1 else None
                
                horse_num = None
                try:
                    horse_num = int(horse_num_elem.get_text(strip=True))
                except ValueError:
                    continue
                
                odds = None
                if odds_elem:
                    odds_text = odds_elem.get_text(strip=True)
                    try:
                        odds = float(odds_text.replace(",", ""))
                    except ValueError:
                        pass
                
                if horse_num:
                    odds_list.append({
                        "horse_number": horse_num,
                        "odds": odds,
                    })
                    
            except Exception:
                continue
        
        return odds_list
    
    def _parse_place_odds(self, soup) -> list[dict]:
        """Parse place (複勝) odds"""
        odds_list = []
        
        table = soup.select_one("#odds_fuku_block table")
        if not table:
            return odds_list
        
        rows = table.select("tr")
        
        for row in rows:
            try:
                cells = row.select("td")
                if len(cells) < 3:
                    continue
                
                horse_num = None
                try:
                    horse_num = int(cells[0].get_text(strip=True))
                except ValueError:
                    continue
                
                odds_min = None
                odds_max = None
                
                if len(cells) >= 2:
                    try:
                        odds_min = float(cells[1].get_text(strip=True).replace(",", ""))
                    except ValueError:
                        pass
                
                if len(cells) >= 3:
                    try:
                        odds_max = float(cells[2].get_text(strip=True).replace(",", ""))
                    except ValueError:
                        pass
                
                if horse_num:
                    odds_list.append({
                        "horse_number": horse_num,
                        "odds_min": odds_min,
                        "odds_max": odds_max,
                    })
                    
            except Exception:
                continue
        
        return odds_list
