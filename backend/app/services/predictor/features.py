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

from app.models import Race, Entry, Horse, Jockey, Training


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
    "G1": 0, "G2": 1, "G3": 2, "L": 3, "オープン": 4,
    "3勝": 5, "2勝": 6, "1勝": 7, "新馬": 8, "未勝利": 9,
}
TRAINING_RANK_MAP = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "E": 5}


class FeatureExtractor:
    """特徴量抽出クラス"""

    def __init__(self, db: Session):
        self.db = db

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

        # === レース条件特徴量 ===
        features.update(self._get_race_features(race, entry))

        # === 馬の基本情報 ===
        features.update(self._get_horse_basic_features(race, entry))

        # === 騎手情報 ===
        features.update(self._get_jockey_features(entry))

        # === 過去成績 ===
        features.update(self._get_past_performance_features(entry.horse_id, race.date))

        # === コース適性 ===
        features.update(self._get_course_aptitude_features(
            entry.horse_id, race.course, race.distance, race.track_type
        ))

        # === オッズ・人気 ===
        features.update(self._get_odds_features(entry))

        # === 調教情報 ===
        features.update(self._get_training_features(race.race_id, entry.horse_id))

        return features

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

    def _get_past_performance_features(
        self, horse_id: str, race_date: date, n_races: int = 5
    ) -> dict:
        """過去成績の特徴量"""
        # 過去のエントリーを取得
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

        # 直近3走、5走の平均着順
        avg_rank_last3 = np.mean(results[:3]) if len(results) >= 3 else np.mean(results) if results else 0
        avg_rank_last5 = np.mean(results[:5]) if len(results) >= 5 else np.mean(results) if results else 0

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
        self, horse_id: str, course: str, distance: int, track_type: str
    ) -> dict:
        """コース適性の特徴量"""
        # 同コースでの成績
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.course == course)
            .where(Entry.result.isnot(None))
        )
        course_entries = list(self.db.execute(stmt).scalars().all())

        # 同距離帯での成績（±200m）
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.distance.between(distance - 200, distance + 200))
            .where(Entry.result.isnot(None))
        )
        distance_entries = list(self.db.execute(stmt).scalars().all())

        # 同芝/ダートでの成績
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.horse_id == horse_id)
            .where(Race.track_type == track_type)
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


def get_feature_columns() -> list[str]:
    """モデルで使用する特徴量カラム名を返す"""
    return [
        # レース条件
        "distance", "track_type", "course", "condition", "weather",
        "grade", "race_number", "field_size", "frame_number",
        # 馬の基本情報
        "horse_age", "horse_sex", "weight", "horse_weight", "weight_diff",
        # 騎手
        "jockey_win_rate", "jockey_place_rate", "jockey_show_rate",
        # 過去成績
        "avg_rank_last3", "avg_rank_last5", "win_rate", "place_rate",
        "show_rate", "best_rank", "days_since_last", "last_result",
        "avg_last3f", "best_last3f",
        # コース適性
        "course_win_rate", "distance_win_rate", "track_win_rate",
        "course_runs", "distance_runs", "track_runs",
        # オッズ
        "odds", "log_odds", "popularity",
        # 調教
        "training_rank", "training_time", "has_training",
    ]


def prepare_training_data(db: Session, min_date: Optional[date] = None) -> tuple[pd.DataFrame, pd.Series]:
    """
    学習用データを準備する

    Args:
        db: データベースセッション
        min_date: 最小日付（これ以降のレースのみ使用）

    Returns:
        X: 特徴量DataFrame
        y: ターゲット（着順）
    """
    extractor = FeatureExtractor(db)

    # 結果が確定しているレースを取得
    stmt = select(Race).where(Race.entries.any(Entry.result.isnot(None)))
    if min_date:
        stmt = stmt.where(Race.date >= min_date)
    stmt = stmt.order_by(Race.date)

    races = list(db.execute(stmt).scalars().all())

    all_features = []
    all_targets = []

    for race in races:
        df = extractor.extract_race_features(race)
        if df.empty:
            continue

        # 結果（着順）を取得
        results = []
        for _, row in df.iterrows():
            entry_stmt = select(Entry).where(
                Entry.race_id == race.race_id,
                Entry.horse_number == row["horse_number"]
            )
            entry = db.execute(entry_stmt).scalar_one_or_none()
            if entry and entry.result:
                results.append(entry.result)
            else:
                results.append(None)

        df["result"] = results
        df = df.dropna(subset=["result"])

        if not df.empty:
            all_features.append(df)
            all_targets.extend(df["result"].tolist())

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
