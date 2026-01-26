"""
地方競馬（NAR）専用の特徴量エンジニアリングモジュール

地方競馬の特性を考慮した特徴量設計:
- ダート100%（芝成績は不要）
- 同一競馬場での出走が多い
- 出走間隔が短い（2-3週間）
- 騎手が固定されやすい
- クラス体系が異なる（A1, A2, B1, B2, C1, C2など）
"""
from datetime import date, datetime
from typing import Optional
import numpy as np
import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import Race, Entry, Horse, Jockey, Training, Trainer, Sire


# === 地方競馬場マッピング ===
LOCAL_COURSE_MAP = {
    # 北海道
    "門別": 0,
    # 東北
    "盛岡": 1, "水沢": 2,
    # 南関東
    "浦和": 3, "船橋": 4, "大井": 5, "川崎": 6,
    # 北陸・東海
    "金沢": 7, "笠松": 8, "名古屋": 9,
    # 近畿
    "園田": 10, "姫路": 11,
    # 四国・九州
    "高知": 12, "佐賀": 13,
}

# 地方競馬場の特性（コース形態）
# 0=小回り, 1=中回り, 2=大回り
LOCAL_COURSE_TYPE = {
    "門別": 2,  # 直線が長い
    "盛岡": 2, "水沢": 1,
    "浦和": 0, "船橋": 1, "大井": 2, "川崎": 0,
    "金沢": 1, "笠松": 0, "名古屋": 0,
    "園田": 0, "姫路": 0,
    "高知": 0, "佐賀": 1,
}

# 地方競馬のグレード体系
LOCAL_GRADE_MAP = {
    # 下級条件（C3が最下層）
    "C3": 0, "C2": 1, "C1": 2,
    "B3": 3, "B2": 4, "B1": 5,
    "A2": 6, "A1": 7,
    # オープン・重賞
    "オープン": 8, "OP": 8,
    "準重賞": 9,
    "重賞": 10,
    # ダートグレード競走
    "JpnIII": 11, "JpnII": 12, "JpnI": 13,
    "GIII": 11, "GII": 12, "GI": 13,
    # 未分類
    "新馬": 0, "未勝利": 0,
    # 特別戦
    "特別": 5,
}

# カテゴリ変数のマッピング
SEX_MAP = {"牡": 0, "牝": 1, "セ": 2}
CONDITION_MAP = {"良": 0, "稍重": 1, "重": 2, "不良": 3}
WEATHER_MAP = {"晴": 0, "曇": 1, "雨": 2, "小雨": 2, "雪": 3}


class LocalFeatureExtractor:
    """地方競馬専用の特徴量抽出クラス"""

    def __init__(self, db: Session, use_cache: bool = True):
        self.db = db
        self.use_cache = use_cache
        self._horse_history_cache: dict = {}
        self._jockey_horse_cache: dict = {}  # 騎手-馬コンビキャッシュ
        self._cache_loaded = False

    def preload_horse_history(self, horse_ids: list[str], max_date: Optional[date] = None) -> None:
        """馬の過去成績を一括でプリロード"""
        if not self.use_cache or not horse_ids:
            return

        uncached_ids = [hid for hid in horse_ids if hid not in self._horse_history_cache]
        if not uncached_ids:
            return

        stmt = (
            select(Entry, Race.date, Race.track_type, Race.distance, Race.condition, Race.course)
            .join(Race)
            .where(Entry.horse_id.in_(uncached_ids))
            .where(Entry.result.isnot(None))
        )
        if max_date:
            stmt = stmt.where(Race.date < max_date)
        stmt = stmt.order_by(Entry.horse_id, Race.date.desc())

        results = list(self.db.execute(stmt).all())

        for hid in uncached_ids:
            self._horse_history_cache[hid] = []

        for entry, race_date, track_type, distance, condition, course in results:
            hid = entry.horse_id
            if hid in self._horse_history_cache:
                self._horse_history_cache[hid].append({
                    'entry': entry,
                    'race_date': race_date,
                    'track_type': track_type,
                    'distance': distance,
                    'condition': condition,
                    'course': course,
                })

        self._cache_loaded = True

    def get_cached_history(self, horse_id: str, race_date: date, limit: int = 50) -> list[dict]:
        """キャッシュから馬の過去成績を取得"""
        if not self.use_cache or horse_id not in self._horse_history_cache:
            return []

        history = self._horse_history_cache.get(horse_id, [])
        filtered = [h for h in history if h['race_date'] < race_date]
        return filtered[:limit]

    def extract_race_features(self, race: Race) -> pd.DataFrame:
        """レースの全出走馬の特徴量を抽出"""
        features_list = []

        for entry in race.entries:
            features = self._extract_entry_features(race, entry)
            features_list.append(features)

        if not features_list:
            return pd.DataFrame()

        return pd.DataFrame(features_list)

    def _extract_entry_features(self, race: Race, entry: Entry) -> dict:
        """単一出走馬の特徴量を抽出"""
        features = {}

        # 識別用
        features["horse_number"] = entry.horse_number
        features["horse_id"] = entry.horse_id

        # === 基本特徴量 ===
        features.update(self._get_id_features(race, entry))
        features.update(self._get_race_features(race, entry))
        features.update(self._get_horse_basic_features(race, entry))

        # === 騎手特徴量（地方向け強化） ===
        features.update(self._get_jockey_features(entry))
        features.update(self._get_jockey_horse_combo_features(entry, race.date))

        # === 過去成績（地方向け調整） ===
        features.update(self._get_past_performance_features(entry.horse_id, race.date))

        # === 同一競馬場成績（地方特有） ===
        features.update(self._get_same_course_features(entry.horse_id, race.course, race.date))

        # === 出走間隔特徴量（地方特有） ===
        features.update(self._get_interval_features(entry.horse_id, race.date))

        # === ダート適性（地方はダート100%） ===
        features.update(self._get_dirt_aptitude_features(entry.horse_id, race.condition, race.distance, race.date))

        # === オッズ・人気 ===
        features.update(self._get_odds_features(entry))

        # === 脚質特徴量 ===
        features.update(self._get_running_style_features(entry.horse_id, race.date))

        # === 季節特徴量 ===
        features.update(self._get_season_features(race.date))

        # === クラス昇降特徴量（地方特有） ===
        features.update(self._get_class_change_features(entry.horse_id, race.grade, race.date))

        # === 人気別成績 ===
        features.update(self._get_popularity_performance_features(entry.horse_id, race.date))

        return features

    def _get_id_features(self, race: Race, entry: Entry) -> dict:
        """ID特徴量"""
        try:
            horse_id_int = int(entry.horse_id) if entry.horse_id else 0
        except ValueError:
            horse_id_int = 0

        try:
            jockey_id_int = int(entry.jockey_id) if entry.jockey_id else 0
        except ValueError:
            jockey_id_int = 0

        return {
            "horse_id_int": horse_id_int,
            "jockey_id_int": jockey_id_int,
            "umaban": entry.horse_number or 0,
        }

    def _get_race_features(self, race: Race, entry: Entry) -> dict:
        """レース条件の特徴量（地方向け）"""
        field_size = len(race.entries)

        # 地方競馬場コード
        course_code = LOCAL_COURSE_MAP.get(race.course, -1)
        course_type = LOCAL_COURSE_TYPE.get(race.course, 1)

        # 地方グレード
        grade = self._parse_local_grade(race.grade)

        return {
            "distance": race.distance,
            "local_course": course_code,
            "course_type": course_type,  # 小回り/中回り/大回り
            "condition": CONDITION_MAP.get(race.condition, -1),
            "weather": WEATHER_MAP.get(race.weather, -1),
            "local_grade": grade,
            "race_number": race.race_number,
            "field_size": field_size,
            "frame_number": entry.frame_number or 0,
            # 距離カテゴリ（地方は短距離が多い）
            "is_sprint": 1 if race.distance <= 1200 else 0,
            "is_mile": 1 if 1201 <= race.distance <= 1600 else 0,
            "is_middle": 1 if 1601 <= race.distance <= 2000 else 0,
            "is_long": 1 if race.distance > 2000 else 0,
        }

    def _parse_local_grade(self, grade_str: str) -> int:
        """地方競馬のグレードをパース"""
        if not grade_str:
            return -1

        # 直接マッチ
        if grade_str in LOCAL_GRADE_MAP:
            return LOCAL_GRADE_MAP[grade_str]

        # 部分マッチ
        grade_upper = grade_str.upper()
        for key, val in LOCAL_GRADE_MAP.items():
            if key in grade_str or key.upper() in grade_upper:
                return val

        return -1

    def _get_horse_basic_features(self, race: Race, entry: Entry) -> dict:
        """馬の基本情報"""
        horse = entry.horse

        if horse:
            age = race.date.year - horse.birth_year
            sex = SEX_MAP.get(horse.sex, -1)
        else:
            age = 0
            sex = -1

        return {
            "horse_age": age,
            "horse_sex": sex,
            "weight": entry.weight or 0,
            "horse_weight": entry.horse_weight or 0,
            "weight_diff": entry.weight_diff or 0,
        }

    def _get_jockey_features(self, entry: Entry) -> dict:
        """騎手の特徴量"""
        jockey = entry.jockey

        if jockey:
            return {
                "jockey_win_rate": jockey.win_rate or 0,
                "jockey_place_rate": jockey.place_rate or 0,
                "jockey_show_rate": jockey.show_rate or 0,
                "jockey_year_wins": jockey.year_wins or 0,
                "jockey_year_rides": jockey.year_rides or 0,
            }
        else:
            return {
                "jockey_win_rate": 0,
                "jockey_place_rate": 0,
                "jockey_show_rate": 0,
                "jockey_year_wins": 0,
                "jockey_year_rides": 0,
            }

    def _get_jockey_horse_combo_features(self, entry: Entry, race_date: date) -> dict:
        """
        騎手-馬のコンビ成績（地方特有）
        地方競馬は同じ騎手・馬の組み合わせが多い
        """
        if not entry.horse_id or not entry.jockey_id:
            return {
                "combo_runs": 0,
                "combo_wins": 0,
                "combo_win_rate": 0,
                "combo_show_rate": 0,
                "is_regular_jockey": 0,
            }

        # 同じ騎手-馬の過去成績を取得
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == entry.horse_id)
            .where(Entry.jockey_id == entry.jockey_id)
            .where(Race.date < race_date)
            .where(Entry.result.isnot(None))
        )
        combo_entries = list(self.db.execute(stmt).scalars().all())

        if not combo_entries:
            return {
                "combo_runs": 0,
                "combo_wins": 0,
                "combo_win_rate": 0,
                "combo_show_rate": 0,
                "is_regular_jockey": 0,
            }

        total = len(combo_entries)
        wins = sum(1 for e in combo_entries if e.result == 1)
        shows = sum(1 for e in combo_entries if e.result <= 3)

        # この馬の総出走回数を取得してレギュラー騎手か判定
        stmt_total = (
            select(func.count(Entry.id))
            .join(Race)
            .where(Entry.horse_id == entry.horse_id)
            .where(Race.date < race_date)
            .where(Entry.result.isnot(None))
        )
        total_runs = self.db.execute(stmt_total).scalar() or 0

        # 50%以上の騎乗率ならレギュラー騎手
        is_regular = 1 if total_runs > 0 and total / total_runs >= 0.5 else 0

        return {
            "combo_runs": total,
            "combo_wins": wins,
            "combo_win_rate": wins / total if total > 0 else 0,
            "combo_show_rate": shows / total if total > 0 else 0,
            "is_regular_jockey": is_regular,
        }

    def _get_past_performance_features(self, horse_id: str, race_date: date) -> dict:
        """過去成績の特徴量"""
        history = self.get_cached_history(horse_id, race_date, limit=50)

        if not history:
            stmt = (
                select(Entry)
                .join(Race)
                .where(Entry.horse_id == horse_id)
                .where(Race.date < race_date)
                .where(Entry.result.isnot(None))
                .order_by(Race.date.desc())
                .limit(50)
            )
            past_entries = list(self.db.execute(stmt).scalars().all())
        else:
            past_entries = [h['entry'] for h in history][:50]

        if not past_entries:
            return {
                "avg_rank_last3": 0,
                "avg_rank_last5": 0,
                "avg_rank_last10": 0,
                "total_runs": 0,
                "win_rate": 0,
                "place_rate": 0,
                "show_rate": 0,
                "best_rank": 0,
                "last_result": 0,
                "avg_last3f": 0,
                "best_last3f": 0,
            }

        results = [e.result for e in past_entries if e.result]
        last3f_times = [e.last_3f for e in past_entries if e.last_3f]

        avg_rank_last3 = np.mean(results[:3]) if len(results) >= 3 else np.mean(results) if results else 0
        avg_rank_last5 = np.mean(results[:5]) if len(results) >= 5 else np.mean(results) if results else 0
        avg_rank_last10 = np.mean(results[:10]) if len(results) >= 10 else np.mean(results) if results else 0

        total = len(results)
        wins = sum(1 for r in results if r == 1)
        places = sum(1 for r in results if r <= 2)
        shows = sum(1 for r in results if r <= 3)

        return {
            "avg_rank_last3": avg_rank_last3,
            "avg_rank_last5": avg_rank_last5,
            "avg_rank_last10": avg_rank_last10,
            "total_runs": total,
            "win_rate": wins / total if total > 0 else 0,
            "place_rate": places / total if total > 0 else 0,
            "show_rate": shows / total if total > 0 else 0,
            "best_rank": min(results) if results else 0,
            "last_result": results[0] if results else 0,
            "avg_last3f": np.mean(last3f_times) if last3f_times else 0,
            "best_last3f": min(last3f_times) if last3f_times else 0,
        }

    def _get_same_course_features(self, horse_id: str, course: str, race_date: date) -> dict:
        """
        同一競馬場での成績（地方特有）
        地方競馬は同じ競馬場での出走が多いため重要
        """
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.course == course)
            .where(Race.date < race_date)
            .where(Entry.result.isnot(None))
        )
        course_entries = list(self.db.execute(stmt).scalars().all())

        if not course_entries:
            return {
                "same_course_runs": 0,
                "same_course_wins": 0,
                "same_course_win_rate": 0,
                "same_course_show_rate": 0,
                "same_course_avg_rank": 0,
            }

        total = len(course_entries)
        wins = sum(1 for e in course_entries if e.result == 1)
        shows = sum(1 for e in course_entries if e.result <= 3)
        avg_rank = np.mean([e.result for e in course_entries if e.result])

        return {
            "same_course_runs": total,
            "same_course_wins": wins,
            "same_course_win_rate": wins / total if total > 0 else 0,
            "same_course_show_rate": shows / total if total > 0 else 0,
            "same_course_avg_rank": avg_rank,
        }

    def _get_interval_features(self, horse_id: str, race_date: date) -> dict:
        """
        出走間隔の特徴量（地方特有）
        地方競馬は出走間隔が短い（2-3週間）ため重要
        """
        history = self.get_cached_history(horse_id, race_date, limit=10)

        if not history:
            stmt = (
                select(Entry, Race.date)
                .join(Race)
                .where(Entry.horse_id == horse_id)
                .where(Race.date < race_date)
                .where(Entry.result.isnot(None))
                .order_by(Race.date.desc())
                .limit(10)
            )
            results = list(self.db.execute(stmt).all())
            past_dates = [r[1] for r in results]
        else:
            past_dates = [h['race_date'] for h in history][:10]

        if not past_dates:
            return {
                "days_since_last": 365,
                "avg_interval": 30,
                "short_interval_count": 0,  # 2週間以内の出走回数
                "is_fresh": 0,  # 休み明け（60日以上）
            }

        days_since_last = (race_date - past_dates[0]).days

        # 過去の出走間隔を計算
        intervals = []
        for i in range(len(past_dates) - 1):
            interval = (past_dates[i] - past_dates[i + 1]).days
            intervals.append(interval)

        avg_interval = np.mean(intervals) if intervals else 30
        short_interval_count = sum(1 for i in intervals if i <= 14)
        is_fresh = 1 if days_since_last >= 60 else 0

        return {
            "days_since_last": days_since_last,
            "avg_interval": avg_interval,
            "short_interval_count": short_interval_count,
            "is_fresh": is_fresh,
        }

    def _get_dirt_aptitude_features(
        self, horse_id: str, condition: str, distance: int, race_date: date
    ) -> dict:
        """
        ダート適性の特徴量（地方はダート100%）
        馬場状態別、距離別の成績を重視
        """
        # 馬場状態別成績
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.condition == condition)
            .where(Race.date < race_date)
            .where(Entry.result.isnot(None))
        )
        condition_entries = list(self.db.execute(stmt).scalars().all())

        # 距離帯別成績（地方向け区分）
        if distance <= 1200:
            dist_min, dist_max = 0, 1200
        elif distance <= 1600:
            dist_min, dist_max = 1201, 1600
        elif distance <= 2000:
            dist_min, dist_max = 1601, 2000
        else:
            dist_min, dist_max = 2001, 9999

        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.distance.between(dist_min, dist_max))
            .where(Race.date < race_date)
            .where(Entry.result.isnot(None))
        )
        distance_entries = list(self.db.execute(stmt).scalars().all())

        # 重馬場成績（地方で重要）
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.condition.in_(["重", "不良"]))
            .where(Race.date < race_date)
            .where(Entry.result.isnot(None))
        )
        heavy_entries = list(self.db.execute(stmt).scalars().all())

        def calc_stats(entries):
            if not entries:
                return 0, 0, 0
            total = len(entries)
            wins = sum(1 for e in entries if e.result == 1)
            shows = sum(1 for e in entries if e.result <= 3)
            return wins / total, shows / total, total

        cond_win, cond_show, cond_runs = calc_stats(condition_entries)
        dist_win, dist_show, dist_runs = calc_stats(distance_entries)
        heavy_win, heavy_show, heavy_runs = calc_stats(heavy_entries)

        return {
            "condition_win_rate": cond_win,
            "condition_show_rate": cond_show,
            "condition_runs": cond_runs,
            "distance_win_rate": dist_win,
            "distance_show_rate": dist_show,
            "distance_runs": dist_runs,
            "heavy_track_win_rate": heavy_win,
            "heavy_track_show_rate": heavy_show,
            "heavy_track_runs": heavy_runs,
        }

    def _get_odds_features(self, entry: Entry) -> dict:
        """オッズ・人気の特徴量"""
        odds = entry.odds or 0
        popularity = entry.popularity or 0
        log_odds = np.log1p(odds) if odds > 0 else 0

        return {
            "odds": odds,
            "log_odds": log_odds,
            "popularity": popularity,
        }

    def _get_running_style_features(self, horse_id: str, race_date: date) -> dict:
        """脚質特徴量"""
        history = self.get_cached_history(horse_id, race_date, limit=20)

        if not history:
            stmt = (
                select(Entry)
                .join(Race)
                .where(Entry.horse_id == horse_id)
                .where(Race.date < race_date)
                .where(Entry.result.isnot(None))
                .where(Entry.corner_position.isnot(None))
                .order_by(Race.date.desc())
                .limit(20)
            )
            past_entries = list(self.db.execute(stmt).scalars().all())
        else:
            past_entries = [h['entry'] for h in history if h['entry'].corner_position][:20]

        if not past_entries:
            return {
                "running_style": -1,
                "avg_first_corner": 0,
                "avg_last_corner": 0,
                "position_up_avg": 0,
                "escape_rate": 0,
                "front_rate": 0,
            }

        first_corners = []
        last_corners = []
        style_counts = {"escape": 0, "front": 0, "stalker": 0, "closer": 0}

        for entry in past_entries:
            if not entry.corner_position:
                continue

            corners = entry.corner_position.replace(" ", "").split("-")
            try:
                positions = [int(c) for c in corners if c.isdigit()]
                if positions:
                    first_pos = positions[0]
                    last_pos = positions[-1]
                    first_corners.append(first_pos)
                    last_corners.append(last_pos)

                    if first_pos <= 2:
                        style_counts["escape"] += 1
                    elif first_pos <= 5:
                        style_counts["front"] += 1
                    elif first_pos <= 10:
                        style_counts["stalker"] += 1
                    else:
                        style_counts["closer"] += 1
            except (ValueError, IndexError):
                continue

        total = len(first_corners)
        if total == 0:
            return {
                "running_style": -1,
                "avg_first_corner": 0,
                "avg_last_corner": 0,
                "position_up_avg": 0,
                "escape_rate": 0,
                "front_rate": 0,
            }

        max_style = max(style_counts, key=style_counts.get)
        style_map = {"escape": 0, "front": 1, "stalker": 2, "closer": 3}
        position_changes = [f - l for f, l in zip(first_corners, last_corners)]

        return {
            "running_style": style_map[max_style],
            "avg_first_corner": np.mean(first_corners),
            "avg_last_corner": np.mean(last_corners),
            "position_up_avg": np.mean(position_changes),
            "escape_rate": style_counts["escape"] / total,
            "front_rate": style_counts["front"] / total,
        }

    def _get_season_features(self, race_date: date) -> dict:
        """季節特徴量"""
        month = race_date.month
        month_rad = 2 * np.pi * (month - 1) / 12

        return {
            "month": month,
            "season": (month - 1) // 3 % 4,
            "month_sin": np.sin(month_rad),
            "month_cos": np.cos(month_rad),
        }

    def _get_class_change_features(self, horse_id: str, current_grade: str, race_date: date) -> dict:
        """
        クラス昇降の特徴量（地方特有）
        地方競馬はクラス移動が頻繁
        """
        history = self.get_cached_history(horse_id, race_date, limit=5)

        if not history:
            return {
                "is_class_up": 0,
                "is_class_down": 0,
                "class_change": 0,
            }

        current_level = self._parse_local_grade(current_grade)
        if current_level < 0:
            return {
                "is_class_up": 0,
                "is_class_down": 0,
                "class_change": 0,
            }

        # 直近のレースからグレードを取得
        for h in history:
            entry = h['entry']
            if entry.race_id:
                race = self.db.get(Race, entry.race_id)
                if race and race.grade:
                    prev_level = self._parse_local_grade(race.grade)
                    if prev_level >= 0:
                        change = current_level - prev_level
                        return {
                            "is_class_up": 1 if change > 0 else 0,
                            "is_class_down": 1 if change < 0 else 0,
                            "class_change": change,
                        }

        return {
            "is_class_up": 0,
            "is_class_down": 0,
            "class_change": 0,
        }

    def _get_popularity_performance_features(self, horse_id: str, race_date: date) -> dict:
        """人気別成績特徴量"""
        history = self.get_cached_history(horse_id, race_date, limit=50)

        if not history:
            stmt = (
                select(Entry)
                .join(Race)
                .where(Entry.horse_id == horse_id)
                .where(Race.date < race_date)
                .where(Entry.result.isnot(None))
                .where(Entry.popularity.isnot(None))
                .order_by(Race.date.desc())
                .limit(50)
            )
            past_entries = list(self.db.execute(stmt).scalars().all())
        else:
            past_entries = [h['entry'] for h in history if h['entry'].popularity][:50]

        if not past_entries:
            return {
                "high_pop_win_rate": 0,
                "high_pop_show_rate": 0,
                "mid_pop_win_rate": 0,
                "mid_pop_show_rate": 0,
                "low_pop_win_rate": 0,
                "low_pop_show_rate": 0,
            }

        high_pop = []
        mid_pop = []
        low_pop = []

        for entry in past_entries:
            pop = entry.popularity
            res = entry.result

            if pop <= 3:
                high_pop.append(res)
            elif pop <= 6:
                mid_pop.append(res)
            else:
                low_pop.append(res)

        def calc_rates(results):
            if not results:
                return 0, 0
            total = len(results)
            wins = sum(1 for r in results if r == 1)
            shows = sum(1 for r in results if r <= 3)
            return wins / total, shows / total

        hw, hs = calc_rates(high_pop)
        mw, ms = calc_rates(mid_pop)
        lw, ls = calc_rates(low_pop)

        return {
            "high_pop_win_rate": hw,
            "high_pop_show_rate": hs,
            "mid_pop_win_rate": mw,
            "mid_pop_show_rate": ms,
            "low_pop_win_rate": lw,
            "low_pop_show_rate": ls,
        }


def get_local_feature_columns() -> list[str]:
    """地方競馬モデルで使用する特徴量カラム名を返す"""
    return [
        # ID特徴量
        "horse_id_int", "jockey_id_int", "umaban",
        # レース条件（地方向け）
        "distance", "local_course", "course_type",
        "condition", "weather", "local_grade",
        "race_number", "field_size", "frame_number",
        "is_sprint", "is_mile", "is_middle", "is_long",
        # 馬の基本情報
        "horse_age", "horse_sex", "weight", "horse_weight", "weight_diff",
        # 騎手特徴量
        "jockey_win_rate", "jockey_place_rate", "jockey_show_rate",
        "jockey_year_wins", "jockey_year_rides",
        # 騎手-馬コンビ（地方特有）
        "combo_runs", "combo_wins", "combo_win_rate", "combo_show_rate", "is_regular_jockey",
        # 過去成績
        "avg_rank_last3", "avg_rank_last5", "avg_rank_last10",
        "total_runs", "win_rate", "place_rate", "show_rate",
        "best_rank", "last_result", "avg_last3f", "best_last3f",
        # 同一競馬場成績（地方特有）
        "same_course_runs", "same_course_wins",
        "same_course_win_rate", "same_course_show_rate", "same_course_avg_rank",
        # 出走間隔（地方特有）
        "days_since_last", "avg_interval", "short_interval_count", "is_fresh",
        # ダート適性
        "condition_win_rate", "condition_show_rate", "condition_runs",
        "distance_win_rate", "distance_show_rate", "distance_runs",
        "heavy_track_win_rate", "heavy_track_show_rate", "heavy_track_runs",
        # オッズ
        "odds", "log_odds", "popularity",
        # 脚質
        "running_style", "avg_first_corner", "avg_last_corner",
        "position_up_avg", "escape_rate", "front_rate",
        # 季節
        "month", "season", "month_sin", "month_cos",
        # クラス昇降（地方特有）
        "is_class_up", "is_class_down", "class_change",
        # 人気別成績
        "high_pop_win_rate", "high_pop_show_rate",
        "mid_pop_win_rate", "mid_pop_show_rate",
        "low_pop_win_rate", "low_pop_show_rate",
    ]


def prepare_local_training_data(
    db: Session,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None,
    progress_callback: Optional[callable] = None,
    target_strategy: int = 0,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    地方競馬用の学習データを準備する

    Args:
        db: データベースセッション
        min_date: 最小日付
        max_date: 最大日付
        progress_callback: 進捗コールバック関数
        target_strategy: ターゲット変数の戦略
            0: 1着のみを正例（従来）
            2: 1着と同タイムの馬も正例（タイム同着を含む）

    Returns:
        X: 特徴量DataFrame
        y: ターゲット（着順、target_strategy=2の場合は同着馬も1として返す）
    """
    extractor = LocalFeatureExtractor(db, use_cache=True)

    # 地方競馬のレースのみ取得
    stmt = (
        select(Race)
        .where(Race.race_type == "local")
        .where(Race.entries.any(Entry.result.isnot(None)))
    )
    if min_date:
        stmt = stmt.where(Race.date >= min_date)
    if max_date:
        stmt = stmt.where(Race.date <= max_date)
    stmt = stmt.order_by(Race.date)

    races = list(db.execute(stmt).scalars().all())
    total_races = len(races)

    if progress_callback:
        progress_callback(0, total_races, "馬の過去成績をプリロード中...")

    # 全馬のIDを収集してキャッシュをプリロード
    all_horse_ids = set()
    for race in races:
        for entry in race.entries:
            if entry.horse_id:
                all_horse_ids.add(entry.horse_id)

    if all_horse_ids:
        extractor.preload_horse_history(list(all_horse_ids), max_date=max_date)

    all_features = []
    all_targets = []

    for i, race in enumerate(races):
        if progress_callback and (i % 100 == 0 or i == total_races - 1):
            progress_callback(i + 1, total_races, f"特徴量抽出中: {race.date} {race.race_name or race.race_id}")

        df = extractor.extract_race_features(race)
        if df.empty:
            continue

        # 結果とfinish_timeを取得
        results = []
        finish_times = []
        for _, row in df.iterrows():
            entry_stmt = select(Entry).where(
                Entry.race_id == race.race_id,
                Entry.horse_number == row["horse_number"]
            )
            entry = db.execute(entry_stmt).scalar_one_or_none()
            if entry and entry.result:
                results.append(entry.result)
                finish_times.append(getattr(entry, 'finish_time', None))
            else:
                results.append(None)
                finish_times.append(None)

        df["result"] = results
        df["finish_time"] = finish_times
        df = df.dropna(subset=["result"])

        if not df.empty:
            # target_strategy=2: 1着と同タイムの馬を正例として扱う
            if target_strategy == 2:
                winner_mask = df["result"] == 1
                if winner_mask.any():
                    winner_time = df.loc[winner_mask, "finish_time"].iloc[0]
                    if winner_time:
                        # 同タイムの馬を見つけて結果を1に修正
                        modified_results = df["result"].copy()
                        time_tie_mask = (df["finish_time"] == winner_time) & (df["result"] > 1)
                        modified_results.loc[time_tie_mask] = 1
                        all_targets.extend(modified_results.tolist())
                    else:
                        all_targets.extend(df["result"].tolist())
                else:
                    all_targets.extend(df["result"].tolist())
            else:
                all_targets.extend(df["result"].tolist())
            all_features.append(df)

    if not all_features:
        return pd.DataFrame(), pd.Series(dtype=float)

    X = pd.concat(all_features, ignore_index=True)
    y = pd.Series(all_targets)

    # 特徴量カラムのみを選択
    feature_cols = get_local_feature_columns()
    X = X[feature_cols]
    X = X.fillna(0)

    return X, y


def prepare_local_time_split_data(
    db: Session,
    train_end_date: date,
    valid_end_date: date,
    train_start_date: Optional[date] = None,
    progress_callback: Optional[callable] = None,
    target_strategy: int = 0,
) -> dict:
    """
    地方競馬用の時系列ベースで学習・検証・テストデータを準備する

    データリークを防ぐため、時間で区切ってデータを分割する:
    - 学習データ: train_start_date ~ train_end_date
    - 検証データ: train_end_date ~ valid_end_date (early stopping用)
    - テストデータ: valid_end_date ~ 現在 (精度評価用、学習には使わない)

    Args:
        db: データベースセッション
        train_end_date: 学習データの終了日
        valid_end_date: 検証データの終了日（テストデータの開始日）
        train_start_date: 学習データの開始日（指定しない場合は全データ）
        progress_callback: 進捗コールバック関数 (phase, current, total, message, overall_progress) -> None
        target_strategy: ターゲット変数の戦略
            0: 1着のみを正例（従来）
            2: 1着と同タイムの馬も正例（タイム同着を含む）

    Returns:
        dict: {
            'train': (X_train, y_train),
            'valid': (X_valid, y_valid),
            'test': (X_test, y_test),
            'date_ranges': {
                'train': (start, end),
                'valid': (start, end),
                'test': (start, end),
            }
        }
    """
    from datetime import timedelta

    # 進捗コールバックをラップ
    def make_phase_callback(phase: str, phase_offset: int, total_phases: int = 3):
        def callback(current, total, message):
            if progress_callback:
                phase_progress = current / total if total > 0 else 0
                overall_progress = (phase_offset + phase_progress) / total_phases
                progress_callback(phase, current, total, message, overall_progress)
        return callback

    # 学習データ
    if progress_callback:
        progress_callback("train", 0, 1, "学習データを準備中...", 0)
    X_train, y_train = prepare_local_training_data(
        db,
        min_date=train_start_date,
        max_date=train_end_date,
        progress_callback=make_phase_callback("train", 0),
        target_strategy=target_strategy,
    )

    # 検証データ（train_end_dateの翌日から）
    valid_start = train_end_date + timedelta(days=1)
    if progress_callback:
        progress_callback("valid", 0, 1, "検証データを準備中...", 0.33)
    X_valid, y_valid = prepare_local_training_data(
        db,
        min_date=valid_start,
        max_date=valid_end_date,
        progress_callback=make_phase_callback("valid", 1),
        target_strategy=target_strategy,
    )

    # テストデータ（valid_end_dateの翌日から現在まで）
    test_start = valid_end_date + timedelta(days=1)
    if progress_callback:
        progress_callback("test", 0, 1, "テストデータを準備中...", 0.66)
    X_test, y_test = prepare_local_training_data(
        db,
        min_date=test_start,
        progress_callback=make_phase_callback("test", 2),
        target_strategy=target_strategy,
    )

    return {
        'train': (X_train, y_train),
        'valid': (X_valid, y_valid),
        'test': (X_test, y_test),
        'date_ranges': {
            'train': (train_start_date, train_end_date),
            'valid': (valid_start, valid_end_date),
            'test': (test_start, None),
        }
    }
