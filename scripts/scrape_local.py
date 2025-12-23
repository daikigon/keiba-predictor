#!/usr/bin/env python3
"""
ローカル用スクレイピングスクリプト
過去レースデータを取得してSupabaseに保存
"""

import os
import sys
from pathlib import Path

# .envファイルを読み込み
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

import requests
import time
import re
from datetime import date, datetime, timedelta
from bs4 import BeautifulSoup
from typing import Optional, List, Dict
from supabase import create_client

# ===== 設定 =====
SCRAPE_INTERVAL = 1.0  # リクエスト間隔（秒）- ローカルは少し速く
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

# JRA競馬場コード
JRA_COURSE_CODES = {"01", "02", "03", "04", "05", "06", "07", "08", "09", "10"}
COURSE_NAMES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
    "09": "阪神", "10": "小倉",
}

# グローバル変数
session = requests.Session()
session.headers.update(HEADERS)
last_request_time = 0
supabase = None


def init_supabase():
    """Supabase接続を初期化"""
    global supabase

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        print("エラー: 環境変数 SUPABASE_URL と SUPABASE_KEY を設定してください")
        print()
        print("設定方法:")
        print('  export SUPABASE_URL="https://xxxxx.supabase.co"')
        print('  export SUPABASE_KEY="your-key"')
        sys.exit(1)

    supabase = create_client(url, key)
    print(f"Supabase接続: {url[:40]}...")
    return supabase


def fetch_html(url: str) -> str:
    """HTMLを取得（レート制限付き）"""
    global last_request_time
    elapsed = time.time() - last_request_time
    if elapsed < SCRAPE_INTERVAL:
        time.sleep(SCRAPE_INTERVAL - elapsed)

    response = session.get(url, timeout=30)
    last_request_time = time.time()

    if "EUC-JP" in response.text[:500] or "euc-jp" in response.text[:500].lower():
        response.encoding = "euc-jp"
    else:
        response.encoding = response.apparent_encoding or "utf-8"

    return response.text


def is_jra_race(race_id: str) -> bool:
    """JRAレースかどうか判定"""
    if len(race_id) >= 6:
        return race_id[4:6] in JRA_COURSE_CODES
    return False


def scrape_race_list(target_date: date, jra_only: bool = True) -> List[Dict]:
    """指定日のレース一覧を取得"""
    date_str = target_date.strftime("%Y%m%d")
    url = f"https://db.netkeiba.com/race/list/{date_str}/"

    html = fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    races = []
    seen_ids = set()

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        match = re.search(r"/race/(\d{12})/", href)
        if match:
            race_id = match.group(1)
            if race_id not in seen_ids:
                if jra_only and not is_jra_race(race_id):
                    continue
                seen_ids.add(race_id)
                races.append({
                    "race_id": race_id,
                    "date": target_date.isoformat(),
                    "race_name": link.get_text(strip=True),
                })

    return races


def scrape_race_detail(race_id: str) -> Dict:
    """レース詳細を取得"""
    url = f"https://db.netkeiba.com/race/{race_id}/"
    html = fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    race_data = {
        "race_id": race_id,
        "course": COURSE_NAMES.get(race_id[4:6], ""),
        "race_number": int(race_id[10:12]) if len(race_id) >= 12 else 0,
    }

    # レース名
    title_elem = soup.select_one(".racedata h1, .data_intro h1")
    if title_elem:
        race_data["race_name"] = title_elem.get_text(strip=True)

    # 距離・馬場
    race_data_elem = soup.select_one(".racedata, .data_intro")
    if race_data_elem:
        text = race_data_elem.get_text()

        distance_match = re.search(r"(\d+)m", text)
        if distance_match:
            race_data["distance"] = int(distance_match.group(1))

        if "芝" in text:
            race_data["track_type"] = "芝"
        elif "ダート" in text or "ダ" in text:
            race_data["track_type"] = "ダート"

        condition_match = re.search(r"(芝|ダ)\s*:\s*(良|稍重|重|不良)", text)
        if condition_match:
            race_data["condition"] = condition_match.group(2)

        for grade in ["(G1)", "(G2)", "(G3)", "(L)", "オープン", "3勝", "2勝", "1勝", "新馬", "未勝利"]:
            if grade in text:
                race_data["grade"] = grade.replace("(", "").replace(")", "")
                break

    # 出走馬
    entries = []
    table = soup.select_one("table.race_table_01")
    if table:
        for row in table.select("tr")[1:]:
            entry = parse_entry_row(row)
            if entry:
                entries.append(entry)

    race_data["entries"] = entries
    return race_data


def parse_entry_row(row) -> Optional[Dict]:
    """出走馬の行をパース"""
    cells = row.select("td")
    if len(cells) < 10:
        return None

    entry = {}

    # 着順
    try:
        result_text = cells[0].get_text(strip=True)
        if result_text.isdigit():
            entry["result"] = int(result_text)
    except:
        pass

    # 枠番
    try:
        entry["frame_number"] = int(cells[1].get_text(strip=True))
    except:
        pass

    # 馬番
    try:
        entry["horse_number"] = int(cells[2].get_text(strip=True))
    except:
        return None

    # 馬名・ID
    horse_link = cells[3].select_one("a")
    if horse_link:
        href = horse_link.get("href", "")
        match = re.search(r"/horse/(\d+)", href)
        if match:
            entry["horse_id"] = match.group(1)
        entry["horse_name"] = horse_link.get_text(strip=True)

    # 性齢
    try:
        sex_age = cells[4].get_text(strip=True)
        if sex_age:
            entry["sex"] = sex_age[0]
    except:
        pass

    # 斤量
    try:
        entry["weight"] = float(cells[5].get_text(strip=True))
    except:
        pass

    # 騎手
    jockey_link = cells[6].select_one("a")
    if jockey_link:
        href = jockey_link.get("href", "")
        match = re.search(r"/jockey/(?:result/recent/)?(\d+)", href)
        if match:
            entry["jockey_id"] = match.group(1)
        entry["jockey_name"] = jockey_link.get_text(strip=True)

    # タイム
    try:
        time_text = cells[7].get_text(strip=True)
        if time_text:
            entry["finish_time"] = time_text
    except:
        pass

    # オッズ
    try:
        if len(cells) > 12:
            odds_text = cells[12].get_text(strip=True)
            if odds_text:
                entry["odds"] = float(odds_text)
    except:
        pass

    # 人気
    try:
        if len(cells) > 13:
            pop_text = cells[13].get_text(strip=True)
            if pop_text.isdigit():
                entry["popularity"] = int(pop_text)
    except:
        pass

    return entry if entry.get("horse_number") else None


# ===== Supabase保存関数 =====

def save_horse(horse_data: Dict) -> bool:
    """馬をSupabaseに保存"""
    try:
        existing = supabase.table("horses").select("horse_id").eq("horse_id", horse_data["horse_id"]).execute()
        if existing.data:
            supabase.table("horses").update(horse_data).eq("horse_id", horse_data["horse_id"]).execute()
        else:
            supabase.table("horses").insert(horse_data).execute()
        return True
    except Exception as e:
        print(f"馬の保存エラー: {e}")
        return False


def save_jockey(jockey_data: Dict) -> bool:
    """騎手をSupabaseに保存"""
    try:
        existing = supabase.table("jockeys").select("jockey_id").eq("jockey_id", jockey_data["jockey_id"]).execute()
        if existing.data:
            supabase.table("jockeys").update(jockey_data).eq("jockey_id", jockey_data["jockey_id"]).execute()
        else:
            supabase.table("jockeys").insert(jockey_data).execute()
        return True
    except Exception as e:
        print(f"騎手の保存エラー: {e}")
        return False


def save_race(race_data: Dict) -> bool:
    """レースをSupabaseに保存"""
    try:
        entries = race_data.pop("entries", [])

        existing = supabase.table("races").select("race_id").eq("race_id", race_data["race_id"]).execute()
        if existing.data:
            supabase.table("races").update(race_data).eq("race_id", race_data["race_id"]).execute()
        else:
            supabase.table("races").insert(race_data).execute()

        for entry in entries:
            if "horse_id" in entry:
                horse_data = {
                    "horse_id": entry["horse_id"],
                    "name": entry.get("horse_name", "不明"),
                    "sex": entry.get("sex", "不"),
                    "birth_year": 2020,
                }
                save_horse(horse_data)

            if "jockey_id" in entry:
                jockey_data = {
                    "jockey_id": entry["jockey_id"],
                    "name": entry.get("jockey_name", "不明"),
                }
                save_jockey(jockey_data)

            entry_data = {
                "race_id": race_data["race_id"],
                "horse_id": entry.get("horse_id"),
                "jockey_id": entry.get("jockey_id"),
                "frame_number": entry.get("frame_number"),
                "horse_number": entry["horse_number"],
                "weight": entry.get("weight"),
                "odds": entry.get("odds"),
                "popularity": entry.get("popularity"),
                "result": entry.get("result"),
                "finish_time": entry.get("finish_time"),
            }

            existing = supabase.table("entries").select("id").eq("race_id", race_data["race_id"]).eq("horse_number", entry["horse_number"]).execute()
            if existing.data:
                supabase.table("entries").update(entry_data).eq("id", existing.data[0]["id"]).execute()
            else:
                supabase.table("entries").insert(entry_data).execute()

        return True
    except Exception as e:
        print(f"レースの保存エラー: {e}")
        return False


def scrape_date_range(start_date: date, end_date: date, jra_only: bool = True):
    """日付範囲でスクレイピング"""
    current = start_date
    total_races = 0
    total_success = 0

    while current <= end_date:
        print(f"\n=== {current} ===")
        races = scrape_race_list(current, jra_only=jra_only)
        print(f"  {len(races)}件のレースが見つかりました")

        for race_info in races:
            try:
                race_detail = scrape_race_detail(race_info["race_id"])
                race_detail["date"] = race_info["date"]

                if save_race(race_detail):
                    total_success += 1
                    print(f"  ✓ {race_info['race_id']}")
                else:
                    print(f"  ✗ {race_info['race_id']} (保存エラー)")

                total_races += 1
            except Exception as e:
                print(f"  ✗ {race_info['race_id']} - {e}")
                total_races += 1

        current += timedelta(days=1)

    print(f"\n完了: {total_success}/{total_races}件 保存成功")


def show_stats():
    """現在のデータ件数を表示"""
    tables = ["races", "entries", "horses", "jockeys", "predictions"]
    print("\nSupabaseデータ件数:")
    for table in tables:
        try:
            result = supabase.table(table).select("*", count="exact").execute()
            print(f"  {table}: {result.count}件")
        except Exception as e:
            print(f"  {table}: エラー - {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="競馬データスクレイピング（ローカル版）")
    parser.add_argument("--start", type=str, help="開始日 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="終了日 (YYYY-MM-DD)")
    parser.add_argument("--date", type=str, help="単日指定 (YYYY-MM-DD)")
    parser.add_argument("--stats", action="store_true", help="データ件数を表示")

    args = parser.parse_args()

    # Supabase初期化
    init_supabase()

    if args.stats:
        show_stats()
        return

    # 日付設定
    if args.date:
        start = end = datetime.strptime(args.date, "%Y-%m-%d").date()
    elif args.start and args.end:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
        end = datetime.strptime(args.end, "%Y-%m-%d").date()
    else:
        # デフォルト: 昨日
        start = end = date.today() - timedelta(days=1)

    print(f"スクレイピング期間: {start} ~ {end}")
    scrape_date_range(start, end)
    show_stats()


if __name__ == "__main__":
    main()
