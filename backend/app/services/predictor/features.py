"""
特徴量エンジニアリングモジュール

DBから取得したデータを機械学習モデル用の特徴量に変換する
"""
from datetime import date, datetime
from typing import Optional
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Race, Entry, Horse, Jockey, Training, Trainer, Sire


# カテゴリ変数のマッピング
SEX_MAP = {"牡": 0, "牝": 1, "セ": 2}
TRACK_TYPE_MAP = {"芝": 0, "ダート": 1}
CONDITION_MAP = {"良": 0, "稍重": 1, "重": 2, "不良": 3}
WEATHER_MAP = {"晴": 0, "曇": 1, "雨": 2, "小雨": 2, "雪": 3}
COURSE_MAP = {
    "札幌": 0, "函館": 1, "福島": 2, "新潟": 3, "東京": 4,
    "中山": 5, "中京": 6, "京都": 7, "阪神": 8, "小倉": 9,
}
GRADE_MAP = {
    # 条件戦（低い順: 0=新馬 → 9=G1）
    "新馬": 0,
    "未勝利": 1,
    "1勝クラス": 2, "1 勝クラス": 2, "1勝": 2,  # スペース有無・略称対応
    "2勝クラス": 3, "2 勝クラス": 3, "2勝": 3,
    "3勝クラス": 4, "3 勝クラス": 4, "3勝": 4,
    # 旧クラス名（2019年以前のデータ対応）
    "500万下": 2,   # 現1勝クラス相当
    "1000万下": 3,  # 現2勝クラス相当
    "1600万下": 4,  # 現3勝クラス相当
    # オープン〜重賞
    "オープン": 5, "OP": 5,
    "(L)": 6, "L": 6,  # リステッド
    "G3": 7, "GIII": 7,
    "G2": 8, "GII": 8,
    "G1": 9, "GI": 9,
}
TRAINING_RANK_MAP = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "E": 5}

# 回り（左回り=0, 右回り=1）- コースから導出
AROUND_MAP = {
    "札幌": 1,  # 右回り
    "函館": 1,  # 右回り
    "福島": 1,  # 右回り
    "新潟": 0,  # 左回り
    "東京": 0,  # 左回り
    "中山": 1,  # 右回り
    "中京": 0,  # 左回り
    "京都": 1,  # 右回り
    "阪神": 1,  # 右回り
    "小倉": 1,  # 右回り
}


class FeatureExtractor:
    """特徴量抽出クラス"""

    def __init__(self, db: Session, use_cache: bool = True):
        """
        Args:
            db: データベースセッション
            use_cache: キャッシュを使用するか（学習時はTrue推奨）
        """
        self.db = db
        self.use_cache = use_cache
        # キャッシュ用辞書
        self._horse_history_cache: dict = {}  # horse_id -> list of past entries
        self._cache_loaded = False

    def preload_horse_history(self, horse_ids: list[str], max_date: Optional[date] = None) -> None:
        """
        指定した馬の過去成績を一括でプリロードしてキャッシュする

        Args:
            horse_ids: 馬IDのリスト
            max_date: この日付より前のデータのみ取得（データリーク防止）
        """
        if not self.use_cache or not horse_ids:
            return

        # 未キャッシュの馬IDのみ取得
        uncached_ids = [hid for hid in horse_ids if hid not in self._horse_history_cache]
        if not uncached_ids:
            return

        # 一括クエリで全馬の過去成績を取得
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

        # horse_idごとにグループ化してキャッシュに格納
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
        """
        キャッシュから馬の過去成績を取得

        Args:
            horse_id: 馬ID
            race_date: レース日（この日より前のデータのみ返す）
            limit: 最大件数

        Returns:
            過去成績のリスト（新しい順）
        """
        if not self.use_cache or horse_id not in self._horse_history_cache:
            return []

        history = self._horse_history_cache.get(horse_id, [])
        # race_dateより前のデータのみフィルタリング
        filtered = [h for h in history if h['race_date'] < race_date]
        return filtered[:limit]

    def extract_race_features(self, race: Race) -> pd.DataFrame:
        """
        レースの全出走馬の特徴量を抽出

        Args:
            race: Raceオブジェクト

        Returns:
            各馬の特徴量を含むDataFrame
        """
        features_list = []

        for entry in race.entries:
            features = self._extract_entry_features(race, entry)
            features_list.append(features)

        if not features_list:
            return pd.DataFrame()

        df = pd.DataFrame(features_list)
        return df

    def _extract_entry_features(self, race: Race, entry: Entry) -> dict:
        """単一出走馬の特徴量を抽出"""
        features = {}

        # 馬番号（識別用）
        features["horse_number"] = entry.horse_number
        features["horse_id"] = entry.horse_id

        # === ID特徴量（参考ドキュメント準拠） ===
        features.update(self._get_id_features(race, entry))

        # === レース条件特徴量 ===
        features.update(self._get_race_features(race, entry))

        # === 馬の基本情報 ===
        features.update(self._get_horse_basic_features(race, entry))

        # === 騎手情報 ===
        features.update(self._get_jockey_features(entry))

        # === 騎手リーディングデータ ===
        features.update(self._get_jockey_leading_features(entry))

        # === 調教師リーディングデータ ===
        features.update(self._get_trainer_leading_features(entry))

        # === 種牡馬リーディングデータ ===
        features.update(self._get_sire_leading_features(entry, race.track_type, race.distance))

        # === 過去成績 ===
        features.update(self._get_past_performance_features(entry.horse_id, race.date))

        # === コース適性 ===
        features.update(self._get_course_aptitude_features(
            entry.horse_id, race.course, race.distance, race.track_type, race.date
        ))

        # === 条件別成績 ===
        features.update(self._get_condition_specific_features(
            entry.horse_id, race.condition, race.distance, race.track_type, race.date
        ))

        # === オッズ・人気 ===
        features.update(self._get_odds_features(entry))

        # === 調教情報 ===
        features.update(self._get_training_features(race.race_id, entry.horse_id))

        # === 脚質特徴量（新規追加） ===
        features.update(self._get_running_style_features(entry.horse_id, race.date))

        # === 季節特徴量（新規追加） ===
        features.update(self._get_season_features(race.date))

        # === ペース特徴量（新規追加） ===
        features.update(self._get_pace_features(entry.horse_id, race.date))

        # === 人気別成績（新規追加） ===
        features.update(self._get_popularity_performance_features(entry.horse_id, race.date))

        return features

    def _get_id_features(self, race: Race, entry: Entry) -> dict:
        """
        ID特徴量（参考ドキュメント準拠）

        LightGBMはIDをそのまま整数値で入力しても、カテゴリとして解釈できる
        """
        # horse_id を整数に変換（文字列の数字部分を抽出）
        try:
            horse_id_int = int(entry.horse_id) if entry.horse_id else 0
        except ValueError:
            horse_id_int = 0

        # jockey_id を整数に変換
        try:
            jockey_id_int = int(entry.jockey_id) if entry.jockey_id else 0
        except ValueError:
            jockey_id_int = 0

        # trainer_id を取得（Horse.trainer → Trainer.trainer_id）
        trainer_id_int = 0
        horse = entry.horse
        if horse and horse.trainer:
            stmt = select(Trainer).where(Trainer.name == horse.trainer)
            trainer = self.db.execute(stmt).scalar_one_or_none()
            if trainer:
                try:
                    trainer_id_int = int(trainer.trainer_id) if trainer.trainer_id else 0
                except ValueError:
                    trainer_id_int = 0

        # umaban（馬番）
        umaban = entry.horse_number or 0

        # around（回り）- コースから導出
        around = AROUND_MAP.get(race.course, -1)

        return {
            "horse_id_int": horse_id_int,
            "jockey_id_int": jockey_id_int,
            "trainer_id_int": trainer_id_int,
            "umaban": umaban,
            "around": around,
        }

    def _get_race_features(self, race: Race, entry: Entry) -> dict:
        """レース条件の特徴量"""
        field_size = len(race.entries)

        return {
            "distance": race.distance,
            "track_type": TRACK_TYPE_MAP.get(race.track_type, -1),
            "course": COURSE_MAP.get(race.course, -1),
            "condition": CONDITION_MAP.get(race.condition, -1),
            "weather": WEATHER_MAP.get(race.weather, -1),
            "grade": GRADE_MAP.get(race.grade, -1),
            "race_number": race.race_number,
            "field_size": field_size,
            "frame_number": entry.frame_number or 0,
        }

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
            }
        else:
            return {
                "jockey_win_rate": 0,
                "jockey_place_rate": 0,
                "jockey_show_rate": 0,
            }

    def _get_jockey_leading_features(self, entry: Entry) -> dict:
        """騎手リーディングデータの特徴量"""
        jockey = entry.jockey

        if jockey:
            # リーディング順位を正規化（1位=1.0, 100位=0.01, なし=0）
            year_rank = jockey.year_rank
            rank_score = 1.0 / year_rank if year_rank and year_rank > 0 else 0

            return {
                "jockey_year_rank": year_rank or 0,
                "jockey_rank_score": rank_score,
                "jockey_year_wins": jockey.year_wins or 0,
                "jockey_year_rides": jockey.year_rides or 0,
                "jockey_year_earnings": (jockey.year_earnings or 0) / 10000,  # 正規化
            }
        else:
            return {
                "jockey_year_rank": 0,
                "jockey_rank_score": 0,
                "jockey_year_wins": 0,
                "jockey_year_rides": 0,
                "jockey_year_earnings": 0,
            }

    def _get_trainer_leading_features(self, entry: Entry) -> dict:
        """調教師リーディングデータの特徴量"""
        horse = entry.horse
        if not horse or not horse.trainer:
            return {
                "trainer_year_rank": 0,
                "trainer_rank_score": 0,
                "trainer_year_wins": 0,
                "trainer_win_rate": 0,
            }

        # 調教師名から調教師データを検索
        stmt = select(Trainer).where(Trainer.name == horse.trainer)
        trainer = self.db.execute(stmt).scalar_one_or_none()

        if trainer:
            year_rank = trainer.year_rank
            rank_score = 1.0 / year_rank if year_rank and year_rank > 0 else 0

            return {
                "trainer_year_rank": year_rank or 0,
                "trainer_rank_score": rank_score,
                "trainer_year_wins": trainer.year_wins or 0,
                "trainer_win_rate": trainer.win_rate or 0,
            }
        else:
            return {
                "trainer_year_rank": 0,
                "trainer_rank_score": 0,
                "trainer_year_wins": 0,
                "trainer_win_rate": 0,
            }

    def _get_sire_leading_features(self, entry: Entry, track_type: str, distance: int) -> dict:
        """種牡馬リーディングデータの特徴量"""
        horse = entry.horse
        if not horse or not horse.father:
            return {
                "sire_year_rank": 0,
                "sire_rank_score": 0,
                "sire_year_wins": 0,
                "sire_win_rate": 0,
                "sire_track_win_rate": 0,
                "sire_distance_win_rate": 0,
            }

        # 種牡馬名から種牡馬データを検索
        stmt = select(Sire).where(Sire.name == horse.father)
        sire = self.db.execute(stmt).scalar_one_or_none()

        if sire:
            year_rank = sire.year_rank
            rank_score = 1.0 / year_rank if year_rank and year_rank > 0 else 0

            # 馬場適性
            if track_type == "芝":
                track_win_rate = sire.turf_win_rate or 0
            else:
                track_win_rate = sire.dirt_win_rate or 0

            # 距離適性
            if distance <= 1400:
                distance_win_rate = sire.short_win_rate or 0
            elif distance <= 1800:
                distance_win_rate = sire.mile_win_rate or 0
            elif distance <= 2200:
                distance_win_rate = sire.middle_win_rate or 0
            else:
                distance_win_rate = sire.long_win_rate or 0

            return {
                "sire_year_rank": year_rank or 0,
                "sire_rank_score": rank_score,
                "sire_year_wins": sire.year_wins or 0,
                "sire_win_rate": sire.win_rate or 0,
                "sire_track_win_rate": track_win_rate,
                "sire_distance_win_rate": distance_win_rate,
            }
        else:
            return {
                "sire_year_rank": 0,
                "sire_rank_score": 0,
                "sire_year_wins": 0,
                "sire_win_rate": 0,
                "sire_track_win_rate": 0,
                "sire_distance_win_rate": 0,
            }

    def _get_past_performance_features(
        self, horse_id: str, race_date: date, n_races: int = 1000
    ) -> dict:
        """
        過去成績の特徴量

        参考ドキュメント準拠で以下を追加:
        - rank_10races, rank_1000races（平均着順）
        - prize_3races, prize_5races, prize_10races, prize_1000races（平均賞金）
        """
        # 過去のエントリーを取得（最大1000件）
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.date < race_date)
            .where(Entry.result.isnot(None))
            .order_by(Race.date.desc())
            .limit(n_races)
        )
        past_entries = list(self.db.execute(stmt).scalars().all())

        if not past_entries:
            return {
                "avg_rank_last3": 0,
                "avg_rank_last5": 0,
                "avg_rank_last10": 0,
                "avg_rank_all": 0,
                "prize_3races": 0,
                "prize_5races": 0,
                "prize_10races": 0,
                "prize_1000races": 0,
                "win_rate": 0,
                "place_rate": 0,
                "show_rate": 0,
                "best_rank": 0,
                "days_since_last": 365,
                "last_result": 0,
                "avg_last3f": 0,
                "best_last3f": 0,
            }

        results = [e.result for e in past_entries if e.result]
        last3f_times = [e.last_3f for e in past_entries if e.last_3f]
        prizes = [e.prize_money for e in past_entries if e.prize_money is not None]

        # 直近N走の平均着順
        avg_rank_last3 = np.mean(results[:3]) if len(results) >= 3 else np.mean(results) if results else 0
        avg_rank_last5 = np.mean(results[:5]) if len(results) >= 5 else np.mean(results) if results else 0
        avg_rank_last10 = np.mean(results[:10]) if len(results) >= 10 else np.mean(results) if results else 0
        avg_rank_all = np.mean(results) if results else 0

        # 直近N走の平均賞金（万円）
        prize_3races = np.mean(prizes[:3]) if len(prizes) >= 3 else np.mean(prizes) if prizes else 0
        prize_5races = np.mean(prizes[:5]) if len(prizes) >= 5 else np.mean(prizes) if prizes else 0
        prize_10races = np.mean(prizes[:10]) if len(prizes) >= 10 else np.mean(prizes) if prizes else 0
        prize_1000races = np.mean(prizes) if prizes else 0

        # 勝率、連対率、複勝率
        total = len(results)
        wins = sum(1 for r in results if r == 1)
        places = sum(1 for r in results if r <= 2)
        shows = sum(1 for r in results if r <= 3)

        win_rate = wins / total if total > 0 else 0
        place_rate = places / total if total > 0 else 0
        show_rate = shows / total if total > 0 else 0

        # 最高着順
        best_rank = min(results) if results else 0

        # 前走からの日数
        if past_entries:
            last_race = self.db.get(Race, past_entries[0].race_id)
            if last_race:
                days_since_last = (race_date - last_race.date).days
            else:
                days_since_last = 365
        else:
            days_since_last = 365

        # 前走着順
        last_result = results[0] if results else 0

        # 上がり3F
        avg_last3f = np.mean(last3f_times) if last3f_times else 0
        best_last3f = min(last3f_times) if last3f_times else 0

        return {
            "avg_rank_last3": avg_rank_last3,
            "avg_rank_last5": avg_rank_last5,
            "avg_rank_last10": avg_rank_last10,
            "avg_rank_all": avg_rank_all,
            "prize_3races": prize_3races,
            "prize_5races": prize_5races,
            "prize_10races": prize_10races,
            "prize_1000races": prize_1000races,
            "win_rate": win_rate,
            "place_rate": place_rate,
            "show_rate": show_rate,
            "best_rank": best_rank,
            "days_since_last": days_since_last,
            "last_result": last_result,
            "avg_last3f": avg_last3f,
            "best_last3f": best_last3f,
        }

    def _get_course_aptitude_features(
        self, horse_id: str, course: str, distance: int, track_type: str, race_date: date
    ) -> dict:
        """コース適性の特徴量（過去データのみ使用）"""
        # 同コースでの成績（予測対象レースより前のみ）
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.course == course)
            .where(Race.date < race_date)  # データリーク防止
            .where(Entry.result.isnot(None))
        )
        course_entries = list(self.db.execute(stmt).scalars().all())

        # 同距離帯での成績（±200m、過去のみ）
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.distance.between(distance - 200, distance + 200))
            .where(Race.date < race_date)  # データリーク防止
            .where(Entry.result.isnot(None))
        )
        distance_entries = list(self.db.execute(stmt).scalars().all())

        # 同芝/ダートでの成績（過去のみ）
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.track_type == track_type)
            .where(Race.date < race_date)  # データリーク防止
            .where(Entry.result.isnot(None))
        )
        track_entries = list(self.db.execute(stmt).scalars().all())

        def calc_win_rate(entries):
            if not entries:
                return 0
            wins = sum(1 for e in entries if e.result == 1)
            return wins / len(entries)

        return {
            "course_win_rate": calc_win_rate(course_entries),
            "distance_win_rate": calc_win_rate(distance_entries),
            "track_win_rate": calc_win_rate(track_entries),
            "course_runs": len(course_entries),
            "distance_runs": len(distance_entries),
            "track_runs": len(track_entries),
        }

    def _get_condition_specific_features(
        self, horse_id: str, condition: str, distance: int, track_type: str, race_date: date
    ) -> dict:
        """
        条件別成績の特徴量（過去データのみ使用）

        - 馬場状態別成績（良/稍重/重/不良）
        - 距離カテゴリ別成績（短距離/マイル/中距離/長距離）
        """
        # 馬場状態別成績（過去のみ）
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.condition == condition)
            .where(Race.date < race_date)  # データリーク防止
            .where(Entry.result.isnot(None))
        )
        condition_entries = list(self.db.execute(stmt).scalars().all())

        # 距離カテゴリ別成績
        if distance <= 1400:
            dist_min, dist_max = 0, 1400
        elif distance <= 1800:
            dist_min, dist_max = 1401, 1800
        elif distance <= 2200:
            dist_min, dist_max = 1801, 2200
        else:
            dist_min, dist_max = 2201, 9999

        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.distance.between(dist_min, dist_max))
            .where(Race.date < race_date)  # データリーク防止
            .where(Entry.result.isnot(None))
        )
        dist_cat_entries = list(self.db.execute(stmt).scalars().all())

        # 馬場状態×馬場タイプの成績（過去のみ）
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.condition == condition)
            .where(Race.track_type == track_type)
            .where(Race.date < race_date)  # データリーク防止
            .where(Entry.result.isnot(None))
        )
        cond_track_entries = list(self.db.execute(stmt).scalars().all())

        def calc_stats(entries):
            if not entries:
                return 0, 0, 0, 0
            total = len(entries)
            wins = sum(1 for e in entries if e.result == 1)
            places = sum(1 for e in entries if e.result <= 3)
            avg_rank = np.mean([e.result for e in entries if e.result])
            return wins / total, places / total, avg_rank, total

        cond_win, cond_show, cond_avg, cond_runs = calc_stats(condition_entries)
        dist_cat_win, dist_cat_show, dist_cat_avg, dist_cat_runs = calc_stats(dist_cat_entries)
        cond_track_win, cond_track_show, cond_track_avg, cond_track_runs = calc_stats(cond_track_entries)

        return {
            # 馬場状態別
            "condition_win_rate": cond_win,
            "condition_show_rate": cond_show,
            "condition_avg_rank": cond_avg,
            "condition_runs": cond_runs,
            # 距離カテゴリ別
            "dist_category_win_rate": dist_cat_win,
            "dist_category_show_rate": dist_cat_show,
            "dist_category_avg_rank": dist_cat_avg,
            "dist_category_runs": dist_cat_runs,
            # 馬場状態×馬場タイプ
            "cond_track_win_rate": cond_track_win,
            "cond_track_show_rate": cond_track_show,
            "cond_track_runs": cond_track_runs,
        }

    def _get_odds_features(self, entry: Entry) -> dict:
        """オッズ・人気の特徴量"""
        odds = entry.odds or 0
        popularity = entry.popularity or 0

        # オッズの対数変換（大きな値を抑制）
        log_odds = np.log1p(odds) if odds > 0 else 0

        return {
            "odds": odds,
            "log_odds": log_odds,
            "popularity": popularity,
        }

    def _get_training_features(self, race_id: str, horse_id: str) -> dict:
        """調教情報の特徴量"""
        stmt = select(Training).where(
            Training.race_id == race_id,
            Training.horse_id == horse_id,
        )
        training = self.db.execute(stmt).scalar_one_or_none()

        if training:
            rank = TRAINING_RANK_MAP.get(training.training_rank, -1)

            # 調教タイムを秒に変換
            training_time = 0
            if training.training_time:
                try:
                    parts = training.training_time.replace(".", ":").split(":")
                    if len(parts) >= 2:
                        training_time = float(parts[0]) * 60 + float(parts[1])
                    else:
                        training_time = float(training.training_time)
                except (ValueError, IndexError):
                    training_time = 0

            return {
                "training_rank": rank,
                "training_time": training_time,
                "has_training": 1,
            }
        else:
            return {
                "training_rank": -1,
                "training_time": 0,
                "has_training": 0,
            }

    def _get_running_style_features(self, horse_id: str, race_date: date) -> dict:
        """
        脚質特徴量（コーナー通過順位から計算）

        脚質分類:
        - 逃げ: 1コーナー1-2番手
        - 先行: 1コーナー3-5番手
        - 差し: 1コーナー6-10番手
        - 追込: 1コーナー11番手以降
        """
        # キャッシュから過去成績を取得
        history = self.get_cached_history(horse_id, race_date, limit=20)

        # キャッシュがない場合はDBから取得（後方互換性）
        if not history and not self._cache_loaded:
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
            # キャッシュからentryを取り出す（corner_positionがあるもののみ）
            past_entries = [h['entry'] for h in history if h['entry'].corner_position][:20]

        if not past_entries:
            return {
                "running_style": -1,  # 不明
                "avg_first_corner": 0,
                "avg_last_corner": 0,
                "position_up_avg": 0,  # コーナー間の順位上昇
                "escape_rate": 0,  # 逃げ率
                "front_rate": 0,  # 先行率
                "stalker_rate": 0,  # 差し率
                "closer_rate": 0,  # 追込率
            }

        first_corners = []
        last_corners = []
        position_changes = []
        style_counts = {"escape": 0, "front": 0, "stalker": 0, "closer": 0}

        for entry in past_entries:
            if not entry.corner_position:
                continue

            # "2-2-3-3" のような形式をパース
            corners = entry.corner_position.replace(" ", "").split("-")
            try:
                positions = [int(c) for c in corners if c.isdigit()]
                if positions:
                    first_pos = positions[0]
                    last_pos = positions[-1]
                    first_corners.append(first_pos)
                    last_corners.append(last_pos)
                    position_changes.append(first_pos - last_pos)  # 正なら順位上昇

                    # 脚質分類
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
                "stalker_rate": 0,
                "closer_rate": 0,
            }

        # 主要脚質を決定
        max_style = max(style_counts, key=style_counts.get)
        style_map = {"escape": 0, "front": 1, "stalker": 2, "closer": 3}

        return {
            "running_style": style_map[max_style],
            "avg_first_corner": np.mean(first_corners),
            "avg_last_corner": np.mean(last_corners),
            "position_up_avg": np.mean(position_changes),
            "escape_rate": style_counts["escape"] / total,
            "front_rate": style_counts["front"] / total,
            "stalker_rate": style_counts["stalker"] / total,
            "closer_rate": style_counts["closer"] / total,
        }

    def _get_season_features(self, race_date: date) -> dict:
        """
        季節特徴量

        季節分類:
        - 春: 3-5月
        - 夏: 6-8月
        - 秋: 9-11月
        - 冬: 12-2月
        """
        month = race_date.month

        # 季節のワンホットエンコーディング
        is_spring = 1 if month in [3, 4, 5] else 0
        is_summer = 1 if month in [6, 7, 8] else 0
        is_autumn = 1 if month in [9, 10, 11] else 0
        is_winter = 1 if month in [12, 1, 2] else 0

        # 季節を数値化（サイクリカルエンコーディング）
        # 月を0-11に変換し、sinとcosで表現
        month_rad = 2 * np.pi * (month - 1) / 12
        month_sin = np.sin(month_rad)
        month_cos = np.cos(month_rad)

        return {
            "season": (month - 1) // 3 % 4,  # 0=冬, 1=春, 2=夏, 3=秋
            "month": month,
            "is_spring": is_spring,
            "is_summer": is_summer,
            "is_autumn": is_autumn,
            "is_winter": is_winter,
            "month_sin": month_sin,
            "month_cos": month_cos,
        }

    def _get_pace_features(self, horse_id: str, race_date: date) -> dict:
        """
        ペース特徴量（過去のペースデータから計算）

        ペース: "35.4-38.1" のような形式（前半-後半）
        """
        # キャッシュから過去成績を取得
        history = self.get_cached_history(horse_id, race_date, limit=20)

        # キャッシュがない場合はDBから取得（後方互換性）
        if not history and not self._cache_loaded:
            stmt = (
                select(Entry)
                .join(Race)
                .where(Entry.horse_id == horse_id)
                .where(Race.date < race_date)
                .where(Entry.result.isnot(None))
                .where(Entry.pace.isnot(None))
                .order_by(Race.date.desc())
                .limit(20)
            )
            past_entries = list(self.db.execute(stmt).scalars().all())
        else:
            # キャッシュからentryを取り出す（paceがあるもののみ）
            past_entries = [h['entry'] for h in history if h['entry'].pace][:20]

        if not past_entries:
            return {
                "avg_pace_first": 0,
                "avg_pace_second": 0,
                "avg_pace_diff": 0,  # 後半-前半（正なら後傾）
                "pace_consistency": 0,  # ペースの一貫性
            }

        pace_firsts = []
        pace_seconds = []

        for entry in past_entries:
            if not entry.pace:
                continue

            try:
                parts = entry.pace.replace(" ", "").split("-")
                if len(parts) == 2:
                    first = float(parts[0])
                    second = float(parts[1])
                    if first > 0 and second > 0:
                        pace_firsts.append(first)
                        pace_seconds.append(second)
            except (ValueError, IndexError):
                continue

        if not pace_firsts:
            return {
                "avg_pace_first": 0,
                "avg_pace_second": 0,
                "avg_pace_diff": 0,
                "pace_consistency": 0,
            }

        avg_first = np.mean(pace_firsts)
        avg_second = np.mean(pace_seconds)
        pace_diffs = [s - f for f, s in zip(pace_firsts, pace_seconds)]

        return {
            "avg_pace_first": avg_first,
            "avg_pace_second": avg_second,
            "avg_pace_diff": np.mean(pace_diffs),
            "pace_consistency": 1.0 / (np.std(pace_diffs) + 0.1) if len(pace_diffs) > 1 else 0,
        }

    def _get_popularity_performance_features(self, horse_id: str, race_date: date) -> dict:
        """
        人気別成績特徴量

        - 1-3番人気時の成績
        - 4-9番人気時の成績
        - 10番人気以下時の成績
        """
        # キャッシュから過去成績を取得
        history = self.get_cached_history(horse_id, race_date, limit=50)

        # キャッシュがない場合はDBから取得（後方互換性）
        if not history and not self._cache_loaded:
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
            # キャッシュからentryを取り出す（popularityがあるもののみ）
            past_entries = [h['entry'] for h in history if h['entry'].popularity][:50]

        # 初期値
        result = {
            "high_pop_win_rate": 0,  # 1-3番人気時の勝率
            "high_pop_show_rate": 0,  # 1-3番人気時の複勝率
            "high_pop_runs": 0,
            "mid_pop_win_rate": 0,  # 4-9番人気時の勝率
            "mid_pop_show_rate": 0,
            "mid_pop_runs": 0,
            "low_pop_win_rate": 0,  # 10番人気以下時の勝率
            "low_pop_show_rate": 0,
            "low_pop_runs": 0,
            "avg_odds_when_win": 0,  # 勝利時の平均オッズ
        }

        if not past_entries:
            return result

        high_pop = []  # 1-3番人気
        mid_pop = []  # 4-9番人気
        low_pop = []  # 10番人気以下
        win_odds = []

        for entry in past_entries:
            pop = entry.popularity
            res = entry.result

            if pop <= 3:
                high_pop.append(res)
            elif pop <= 9:
                mid_pop.append(res)
            else:
                low_pop.append(res)

            if res == 1 and entry.odds:
                win_odds.append(entry.odds)

        def calc_rates(results):
            if not results:
                return 0, 0, 0
            total = len(results)
            wins = sum(1 for r in results if r == 1)
            shows = sum(1 for r in results if r <= 3)
            return wins / total, shows / total, total

        hw, hs, hr = calc_rates(high_pop)
        mw, ms, mr = calc_rates(mid_pop)
        lw, ls, lr = calc_rates(low_pop)

        return {
            "high_pop_win_rate": hw,
            "high_pop_show_rate": hs,
            "high_pop_runs": hr,
            "mid_pop_win_rate": mw,
            "mid_pop_show_rate": ms,
            "mid_pop_runs": mr,
            "low_pop_win_rate": lw,
            "low_pop_show_rate": ls,
            "low_pop_runs": lr,
            "avg_odds_when_win": np.mean(win_odds) if win_odds else 0,
        }


def get_feature_columns() -> list[str]:
    """モデルで使用する特徴量カラム名を返す"""
    return [
        # ID特徴量（参考ドキュメント準拠）
        "horse_id_int", "jockey_id_int", "trainer_id_int",
        # 馬番・回り（参考ドキュメント準拠）
        "umaban", "around",
        # レース条件
        "distance", "track_type", "course", "condition", "weather",
        "grade", "race_number", "field_size", "frame_number",
        # 馬の基本情報
        "horse_age", "horse_sex", "weight", "horse_weight", "weight_diff",
        # 騎手基本
        "jockey_win_rate", "jockey_place_rate", "jockey_show_rate",
        # 騎手リーディング
        "jockey_year_rank", "jockey_rank_score", "jockey_year_wins",
        "jockey_year_rides", "jockey_year_earnings",
        # 調教師リーディング
        "trainer_year_rank", "trainer_rank_score", "trainer_year_wins",
        "trainer_win_rate",
        # 種牡馬リーディング
        "sire_year_rank", "sire_rank_score", "sire_year_wins",
        "sire_win_rate", "sire_track_win_rate", "sire_distance_win_rate",
        # 過去成績（参考ドキュメント準拠で拡張）
        "avg_rank_last3", "avg_rank_last5", "avg_rank_last10", "avg_rank_all",
        "prize_3races", "prize_5races", "prize_10races", "prize_1000races",
        "win_rate", "place_rate", "show_rate", "best_rank",
        "days_since_last", "last_result", "avg_last3f", "best_last3f",
        # コース適性
        "course_win_rate", "distance_win_rate", "track_win_rate",
        "course_runs", "distance_runs", "track_runs",
        # 条件別成績
        "condition_win_rate", "condition_show_rate", "condition_avg_rank", "condition_runs",
        "dist_category_win_rate", "dist_category_show_rate", "dist_category_avg_rank", "dist_category_runs",
        "cond_track_win_rate", "cond_track_show_rate", "cond_track_runs",
        # オッズ
        "odds", "log_odds", "popularity",
        # 調教
        "training_rank", "training_time", "has_training",
        # === 新規追加: 脚質特徴量 ===
        "running_style", "avg_first_corner", "avg_last_corner", "position_up_avg",
        "escape_rate", "front_rate", "stalker_rate", "closer_rate",
        # === 新規追加: 季節特徴量 ===
        "season", "month", "is_spring", "is_summer", "is_autumn", "is_winter",
        "month_sin", "month_cos",
        # === 新規追加: ペース特徴量 ===
        "avg_pace_first", "avg_pace_second", "avg_pace_diff", "pace_consistency",
        # === 新規追加: 人気別成績 ===
        "high_pop_win_rate", "high_pop_show_rate", "high_pop_runs",
        "mid_pop_win_rate", "mid_pop_show_rate", "mid_pop_runs",
        "low_pop_win_rate", "low_pop_show_rate", "low_pop_runs",
        "avg_odds_when_win",
    ]


def prepare_training_data(
    db: Session,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None,
    progress_callback: Optional[callable] = None,
    target_strategy: int = 0,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    学習用データを準備する

    Args:
        db: データベースセッション
        min_date: 最小日付（これ以降のレースのみ使用）
        max_date: 最大日付（これ以前のレースのみ使用）
        progress_callback: 進捗コールバック関数 (current, total, message) -> None
        target_strategy: ターゲット変数の戦略
            0: 1着のみを正例（従来）
            2: 1着と同タイムの馬も正例（タイム同着を含む）

    Returns:
        X: 特徴量DataFrame
        y: ターゲット（着順、target_strategy=2の場合は同着馬も1として返す）
    """
    extractor = FeatureExtractor(db, use_cache=True)

    # 結果が確定しているレースを取得
    stmt = select(Race).where(Race.entries.any(Entry.result.isnot(None)))
    if min_date:
        stmt = stmt.where(Race.date >= min_date)
    if max_date:
        stmt = stmt.where(Race.date <= max_date)
    stmt = stmt.order_by(Race.date)

    races = list(db.execute(stmt).scalars().all())
    total_races = len(races)

    # 全馬のIDを収集してキャッシュをプリロード（最適化）
    if progress_callback:
        progress_callback(0, total_races, "馬の過去成績をプリロード中...")

    all_horse_ids = set()
    for race in races:
        for entry in race.entries:
            if entry.horse_id:
                all_horse_ids.add(entry.horse_id)

    if all_horse_ids:
        # 一括でキャッシュをプリロード
        extractor.preload_horse_history(list(all_horse_ids), max_date=max_date)

    all_features = []
    all_targets = []

    for i, race in enumerate(races):
        # 進捗報告（100レースごと、または最初と最後）
        if progress_callback and (i % 100 == 0 or i == total_races - 1):
            progress_callback(i + 1, total_races, f"特徴量抽出中: {race.date} {race.race_name or race.race_id}")

        df = extractor.extract_race_features(race)
        if df.empty:
            continue

        # 結果（着順）とfinish_timeを取得
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
                finish_times.append(entry.finish_time)
            else:
                results.append(None)
                finish_times.append(None)

        df["result"] = results
        df["finish_time"] = finish_times
        df = df.dropna(subset=["result"])

        if not df.empty:
            # target_strategy=2: 1着と同タイムの馬を正例として扱う
            if target_strategy == 2:
                # 1着馬のfinish_timeを取得
                winner_mask = df["result"] == 1
                if winner_mask.any():
                    winner_time = df.loc[winner_mask, "finish_time"].iloc[0]
                    if winner_time:
                        # 同タイムの馬を見つけて結果を1に修正
                        # （実際の着順は保持せず、ターゲット用の値として1を設定）
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
    feature_cols = get_feature_columns()
    X = X[feature_cols]

    # 欠損値を埋める
    X = X.fillna(0)

    return X, y


def prepare_time_split_data(
    db: Session,
    train_end_date: date,
    valid_end_date: date,
    train_start_date: Optional[date] = None,
    progress_callback: Optional[callable] = None,
    target_strategy: int = 0,
) -> dict:
    """
    時系列ベースで学習・検証・テストデータを準備する

    データリークを防ぐため、時間で区切ってデータを分割する:
    - 学習データ: train_start_date ~ train_end_date
    - 検証データ: train_end_date ~ valid_end_date (early stopping用)
    - テストデータ: valid_end_date ~ 現在 (精度評価用、学習には使わない)

    Args:
        db: データベースセッション
        train_end_date: 学習データの終了日
        valid_end_date: 検証データの終了日（テストデータの開始日）
        train_start_date: 学習データの開始日（指定しない場合は全データ）
        progress_callback: 進捗コールバック関数 (phase, current, total, message) -> None
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
                # 全体の進捗を計算（各フェーズは均等に1/3ずつ）
                phase_progress = current / total if total > 0 else 0
                overall_progress = (phase_offset + phase_progress) / total_phases
                progress_callback(phase, current, total, message, overall_progress)
        return callback

    # 学習データ
    if progress_callback:
        progress_callback("train", 0, 1, "学習データを準備中...", 0)
    X_train, y_train = prepare_training_data(
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
    X_valid, y_valid = prepare_training_data(
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
    X_test, y_test = prepare_training_data(
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
        },
        'counts': {
            'train': len(y_train),
            'valid': len(y_valid),
            'test': len(y_test),
        }
    }
