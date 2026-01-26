"""
ばんえい競馬専用 特徴量エンジニアリングモジュール

ばんえい競馬は通常競馬と大きく異なる特性を持つため、専用の特徴量設計を行う。

ばんえい競馬の特性:
- コース: 直線200m（帯広固定）
- 馬体重: 800-1200kg（通常の約2倍）
- ソリ重量: 480-1000kg（斤量の代わり）
- 障害: 2つの坂
- 騎手影響度: 馬3:騎手7（通常は馬7:騎手3）
"""
from datetime import date
from typing import Optional
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Race, Entry, Horse, Jockey, Trainer


# ばんえい用グレードマッピング
BANEI_GRADE_MAP = {
    # 新馬・未勝利
    "新馬": 0,
    "未勝利": 1,
    # 条件戦（ソリ重量基準）
    "C4": 2, "C3": 3, "C2": 4, "C1": 5,
    "B4": 6, "B3": 7, "B2": 8, "B1": 9,
    "A2": 10, "A1": 11,
    # オープン・重賞
    "オープン": 12, "OP": 12,
    "BG3": 13,
    "BG2": 14,
    "BG1": 15,
    # 特別戦
    "特別": 11,
}

# 性別マッピング
SEX_MAP = {"牡": 0, "牝": 1, "セ": 2}


# ばんえい専用特徴量カラム
BANEI_FEATURE_COLUMNS = [
    # ID特徴量 (4)
    "horse_id_int", "jockey_id_int", "trainer_id_int", "umaban",

    # ソリ重量関連 (5)
    "sori_weight", "sori_weight_ratio", "sori_weight_rank",
    "sori_weight_normalized", "sori_weight_vs_class_avg",

    # 馬体重関連 (5)
    "horse_weight_banei", "weight_diff_banei", "weight_trend",
    "power_index", "optimal_weight_gap",

    # 水分量・馬場 (4)
    "moisture_level", "moisture_aptitude", "is_light_track", "is_heavy_track",

    # レース条件 (4)
    "grade_encoded", "race_number", "field_size", "frame_number",

    # 馬基本情報 (4)
    "age", "age_category", "sex", "sex_weight_bonus",

    # 騎手 (6)
    "jockey_win_rate", "jockey_place_rate", "jockey_year_rank",
    "jockey_heavy_win_rate", "jockey_moisture_apt", "jockey_horse_combo",

    # 過去成績 (8)
    "avg_rank_last3", "avg_rank_last5", "win_rate", "place_rate",
    "show_rate", "days_since_last", "last_result", "best_rank",

    # 重量別成績 (3)
    "light_weight_win_rate", "mid_weight_win_rate", "heavy_weight_win_rate",

    # オッズ (3)
    "odds", "log_odds", "popularity",

    # 季節 (3)
    "month", "season", "is_cold_season",
]


def get_banei_feature_columns() -> list[str]:
    """ばんえいモデルで使用する特徴量カラム名を返す"""
    return BANEI_FEATURE_COLUMNS.copy()


class BaneiFeatureExtractor:
    """ばんえい競馬専用の特徴量抽出クラス"""

    def __init__(self, db: Session, use_cache: bool = True):
        """
        Args:
            db: データベースセッション
            use_cache: キャッシュを使用するか（学習時はTrue推奨）
        """
        self.db = db
        self.use_cache = use_cache
        # キャッシュ用辞書
        self._horse_history_cache: dict = {}
        self._jockey_history_cache: dict = {}
        self._cache_loaded = False

    def preload_horse_history(self, horse_ids: list[str], max_date: Optional[date] = None) -> None:
        """馬の過去成績を一括でプリロード"""
        if not self.use_cache or not horse_ids:
            return

        uncached_ids = [hid for hid in horse_ids if hid not in self._horse_history_cache]
        if not uncached_ids:
            return

        stmt = (
            select(Entry, Race.date, Race.condition, Race.grade)
            .join(Race)
            .where(Entry.horse_id.in_(uncached_ids))
            .where(Race.race_type == "banei")
            .where(Entry.result.isnot(None))
        )
        if max_date:
            stmt = stmt.where(Race.date < max_date)
        stmt = stmt.order_by(Entry.horse_id, Race.date.desc())

        results = list(self.db.execute(stmt).all())

        for hid in uncached_ids:
            self._horse_history_cache[hid] = []

        for entry, race_date, condition, grade in results:
            hid = entry.horse_id
            if hid in self._horse_history_cache:
                self._horse_history_cache[hid].append({
                    'entry': entry,
                    'race_date': race_date,
                    'condition': condition,
                    'grade': grade,
                })

        self._cache_loaded = True

    def get_cached_history(self, horse_id: str, race_date: date, limit: int = 50) -> list[dict]:
        """キャッシュから馬の過去成績を取得"""
        if not self.use_cache or horse_id not in self._horse_history_cache:
            return []
        if race_date is None:
            return []

        history = self._horse_history_cache.get(horse_id, [])
        filtered = [h for h in history if h['race_date'] is not None and h['race_date'] < race_date]
        return filtered[:limit]

    def extract_race_features(self, race: Race) -> pd.DataFrame:
        """レースの全出走馬の特徴量を抽出"""
        # レース日付がない場合はスキップ
        if race.date is None:
            return pd.DataFrame()

        features_list = []

        # レース内の統計情報を事前計算
        race_stats = self._compute_race_stats(race)

        for entry in race.entries:
            features = self._extract_entry_features(race, entry, race_stats)
            features_list.append(features)

        if not features_list:
            return pd.DataFrame()

        df = pd.DataFrame(features_list)
        return df

    def _compute_race_stats(self, race: Race) -> dict:
        """レース内の統計情報を計算"""
        weights = [e.weight for e in race.entries if e.weight]
        return {
            'avg_weight': np.mean(weights) if weights else 0,
            'max_weight': max(weights) if weights else 0,
            'min_weight': min(weights) if weights else 0,
            'field_size': len(race.entries),
        }

    def _extract_entry_features(self, race: Race, entry: Entry, race_stats: dict) -> dict:
        """単一出走馬の特徴量を抽出"""
        features = {}

        # 馬番号（識別用）
        features["horse_number"] = entry.horse_number
        features["horse_id"] = entry.horse_id

        # === ID特徴量 ===
        features.update(self._get_id_features(entry))

        # === ソリ重量関連 ===
        features.update(self._get_sori_weight_features(race, entry, race_stats))

        # === 馬体重関連 ===
        features.update(self._get_horse_weight_features(entry, race.date))

        # === 水分量・馬場 ===
        features.update(self._get_moisture_features(race, entry))

        # === レース条件 ===
        features.update(self._get_race_features(race, entry, race_stats))

        # === 馬基本情報 ===
        features.update(self._get_horse_basic_features(race, entry))

        # === 騎手 ===
        features.update(self._get_jockey_features(entry, race.date))

        # === 過去成績 ===
        features.update(self._get_past_performance_features(entry.horse_id, race.date))

        # === 重量別成績 ===
        features.update(self._get_weight_class_features(entry.horse_id, race.date))

        # === オッズ ===
        features.update(self._get_odds_features(entry))

        # === 季節 ===
        features.update(self._get_season_features(race.date))

        return features

    def _get_id_features(self, entry: Entry) -> dict:
        """ID特徴量"""
        try:
            horse_id_int = int(entry.horse_id) if entry.horse_id else 0
        except ValueError:
            horse_id_int = 0

        try:
            jockey_id_int = int(entry.jockey_id) if entry.jockey_id else 0
        except ValueError:
            jockey_id_int = 0

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

        return {
            "horse_id_int": horse_id_int,
            "jockey_id_int": jockey_id_int,
            "trainer_id_int": trainer_id_int,
            "umaban": entry.horse_number or 0,
        }

    def _get_sori_weight_features(self, race: Race, entry: Entry, race_stats: dict) -> dict:
        """ソリ重量関連特徴量"""
        sori_weight = entry.weight or 0
        horse_weight = entry.horse_weight or 900  # デフォルト900kg

        # ソリ重量/馬体重の比率
        sori_weight_ratio = sori_weight / horse_weight if horse_weight > 0 else 0

        # レース内でのソリ重量順位
        weights = [(i, e.weight or 0) for i, e in enumerate(race.entries)]
        weights_sorted = sorted(weights, key=lambda x: x[1], reverse=True)
        rank = 1
        for i, (idx, w) in enumerate(weights_sorted):
            if race.entries[idx].horse_id == entry.horse_id:
                rank = i + 1
                break
        sori_weight_rank = rank

        # 正規化ソリ重量（レース内）
        avg_weight = race_stats['avg_weight']
        sori_weight_normalized = (sori_weight - avg_weight) / 100 if avg_weight > 0 else 0

        # クラス平均との差（グレードから推定）
        grade = race.grade or ""
        if "A" in grade:
            class_avg = 750
        elif "B" in grade:
            class_avg = 680
        elif "C" in grade:
            class_avg = 620
        else:
            class_avg = 580
        sori_weight_vs_class_avg = sori_weight - class_avg

        return {
            "sori_weight": sori_weight,
            "sori_weight_ratio": sori_weight_ratio,
            "sori_weight_rank": sori_weight_rank,
            "sori_weight_normalized": sori_weight_normalized,
            "sori_weight_vs_class_avg": sori_weight_vs_class_avg,
        }

    def _get_horse_weight_features(self, entry: Entry, race_date: date) -> dict:
        """馬体重関連特徴量"""
        horse_weight = entry.horse_weight or 0
        weight_diff = entry.weight_diff or 0

        # 過去の馬体重トレンド
        past_entries = []
        if race_date is not None:
            history = self.get_cached_history(entry.horse_id, race_date, limit=5)
            if not history:
                stmt = (
                    select(Entry)
                    .join(Race)
                    .where(Entry.horse_id == entry.horse_id)
                    .where(Race.date < race_date)
                    .where(Entry.horse_weight.isnot(None))
                    .order_by(Race.date.desc())
                    .limit(5)
                )
                past_entries = list(self.db.execute(stmt).scalars().all())
            else:
                past_entries = [h['entry'] for h in history if h['entry'].horse_weight][:5]

        weight_trend = 0
        if len(past_entries) >= 2:
            weights = [e.horse_weight for e in past_entries if e.horse_weight]
            if len(weights) >= 2:
                # 増加傾向なら正、減少なら負
                weight_trend = (weights[0] - weights[-1]) / len(weights)

        # パワー指標（馬体重 - ソリ重量比の逆数で近似）
        sori_weight = entry.weight or 0
        power_index = horse_weight / (sori_weight + 1) if sori_weight > 0 else 0

        # ベスト時との体重差
        best_weight_gap = 0
        if past_entries:
            # resultがNoneの場合は99として扱う（最下位扱い）
            results = [(e.horse_weight, e.result if e.result is not None else 99)
                       for e in past_entries if e.horse_weight]
            if results:
                best = min(results, key=lambda x: x[1])
                if best[0]:
                    best_weight_gap = horse_weight - best[0]

        return {
            "horse_weight_banei": horse_weight,
            "weight_diff_banei": weight_diff,
            "weight_trend": weight_trend,
            "power_index": power_index,
            "optimal_weight_gap": best_weight_gap,
        }

    def _get_moisture_features(self, race: Race, entry: Entry) -> dict:
        """水分量・馬場特徴量"""
        condition = race.condition or ""

        # 水分量を解析（例: "3.2%" → 3.2）
        moisture_level = 0
        if condition:
            try:
                moisture_level = float(condition.replace("%", "").strip())
            except ValueError:
                # 「良」「重」などの表記の場合
                condition_map = {"良": 1.0, "稍重": 2.5, "重": 4.0, "不良": 5.5}
                moisture_level = condition_map.get(condition, 2.0)

        # 馬場状態フラグ
        is_light_track = 1 if moisture_level < 2.0 else 0
        is_heavy_track = 1 if moisture_level > 4.0 else 0

        # 水分量別成績
        moisture_aptitude = self._calc_moisture_aptitude(entry.horse_id, race.date, moisture_level)

        return {
            "moisture_level": moisture_level,
            "moisture_aptitude": moisture_aptitude,
            "is_light_track": is_light_track,
            "is_heavy_track": is_heavy_track,
        }

    def _calc_moisture_aptitude(self, horse_id: str, race_date: date, current_moisture: float) -> float:
        """水分量別の成績を計算"""
        history = self.get_cached_history(horse_id, race_date, limit=20)

        if not history:
            return 0

        similar_condition_results = []
        for h in history:
            cond = h.get('condition') or ''
            if not cond:
                continue
            try:
                m = float(cond.replace("%", "").strip())
            except ValueError:
                continue

            # 類似の水分量（±1.5%）での成績
            if abs(m - current_moisture) <= 1.5:
                if h['entry'].result:
                    similar_condition_results.append(h['entry'].result)

        if not similar_condition_results:
            return 0

        # 平均着順の逆数（良いほど高い）
        avg_rank = np.mean(similar_condition_results)
        return 1.0 / avg_rank if avg_rank > 0 else 0

    def _get_race_features(self, race: Race, entry: Entry, race_stats: dict) -> dict:
        """レース条件特徴量"""
        grade_encoded = BANEI_GRADE_MAP.get(race.grade or "", -1)

        return {
            "grade_encoded": grade_encoded,
            "race_number": race.race_number,
            "field_size": race_stats['field_size'],
            "frame_number": entry.frame_number or 0,
        }

    def _get_horse_basic_features(self, race: Race, entry: Entry) -> dict:
        """馬基本情報特徴量"""
        horse = entry.horse

        if horse and race.date and horse.birth_year:
            age = race.date.year - horse.birth_year
            sex = SEX_MAP.get(horse.sex, -1)
        else:
            age = 0
            sex = -1 if not horse else SEX_MAP.get(horse.sex, -1)

        # 年齢カテゴリ（若馬/中堅/ベテラン）
        if age <= 3:
            age_category = 0  # 若馬
        elif age <= 6:
            age_category = 1  # 中堅
        else:
            age_category = 2  # ベテラン

        # 性別によるソリ重量ボーナス（牝馬は軽い）
        sori_weight = entry.weight or 0
        sex_weight_bonus = 0
        if sex == 1 and sori_weight > 0:  # 牝馬
            sex_weight_bonus = 20  # 牝馬は約20kg軽い傾向

        return {
            "age": age,
            "age_category": age_category,
            "sex": sex,
            "sex_weight_bonus": sex_weight_bonus,
        }

    def _get_jockey_features(self, entry: Entry, race_date: date) -> dict:
        """騎手特徴量（ばんえいでは影響度が高い）"""
        jockey = entry.jockey

        jockey_win_rate = 0
        jockey_place_rate = 0
        jockey_year_rank = 0
        jockey_heavy_win_rate = 0
        jockey_moisture_apt = 0
        jockey_horse_combo = 0

        if jockey:
            jockey_win_rate = jockey.win_rate or 0
            jockey_place_rate = jockey.place_rate or 0
            jockey_year_rank = jockey.year_rank or 0

            # 重量戦勝率（700kg以上のソリ重量）
            jockey_heavy_win_rate = self._calc_jockey_heavy_win_rate(jockey.jockey_id, race_date)

            # 水分量別成績
            jockey_moisture_apt = self._calc_jockey_moisture_apt(jockey.jockey_id, race_date)

            # 騎手×馬の相性
            jockey_horse_combo = self._calc_jockey_horse_combo(
                jockey.jockey_id, entry.horse_id, race_date
            )

        return {
            "jockey_win_rate": jockey_win_rate,
            "jockey_place_rate": jockey_place_rate,
            "jockey_year_rank": jockey_year_rank,
            "jockey_heavy_win_rate": jockey_heavy_win_rate,
            "jockey_moisture_apt": jockey_moisture_apt,
            "jockey_horse_combo": jockey_horse_combo,
        }

    def _calc_jockey_heavy_win_rate(self, jockey_id: str, race_date: date) -> float:
        """騎手の重量戦勝率を計算"""
        if race_date is None:
            return 0
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.jockey_id == jockey_id)
            .where(Race.race_type == "banei")
            .where(Race.date < race_date)
            .where(Entry.weight >= 700)
            .where(Entry.result.isnot(None))
            .limit(100)
        )
        entries = list(self.db.execute(stmt).scalars().all())

        if not entries:
            return 0

        wins = sum(1 for e in entries if e.result == 1)
        return wins / len(entries)

    def _calc_jockey_moisture_apt(self, jockey_id: str, race_date: date) -> float:
        """騎手の馬場別成績"""
        if race_date is None:
            return 0
        # 直近のばんえいレースでの成績
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.jockey_id == jockey_id)
            .where(Race.race_type == "banei")
            .where(Race.date < race_date)
            .where(Entry.result.isnot(None))
            .order_by(Race.date.desc())
            .limit(50)
        )
        entries = list(self.db.execute(stmt).scalars().all())

        if not entries:
            return 0

        shows = sum(1 for e in entries if e.result and e.result <= 3)
        return shows / len(entries)

    def _calc_jockey_horse_combo(self, jockey_id: str, horse_id: str, race_date: date) -> float:
        """騎手×馬の相性を計算"""
        if race_date is None:
            return 0
        stmt = (
            select(Entry)
            .join(Race)
            .where(Entry.jockey_id == jockey_id)
            .where(Entry.horse_id == horse_id)
            .where(Race.date < race_date)
            .where(Entry.result.isnot(None))
            .order_by(Race.date.desc())
            .limit(20)
        )
        entries = list(self.db.execute(stmt).scalars().all())

        if not entries:
            return 0

        # 平均着順の逆数
        avg_rank = np.mean([e.result for e in entries if e.result])
        return 1.0 / avg_rank if avg_rank > 0 else 0

    def _get_past_performance_features(self, horse_id: str, race_date: date) -> dict:
        """過去成績特徴量"""
        # race_dateがNoneの場合はデフォルト値を返す
        if race_date is None:
            return {
                "avg_rank_last3": 0,
                "avg_rank_last5": 0,
                "win_rate": 0,
                "place_rate": 0,
                "show_rate": 0,
                "days_since_last": 365,
                "last_result": 0,
                "best_rank": 0,
            }

        history = self.get_cached_history(horse_id, race_date, limit=50)

        if not history:
            stmt = (
                select(Entry)
                .join(Race)
                .where(Entry.horse_id == horse_id)
                .where(Race.race_type == "banei")
                .where(Race.date < race_date)
                .where(Entry.result.isnot(None))
                .order_by(Race.date.desc())
                .limit(50)
            )
            past_entries = list(self.db.execute(stmt).scalars().all())
        else:
            past_entries = [h['entry'] for h in history]

        if not past_entries:
            return {
                "avg_rank_last3": 0,
                "avg_rank_last5": 0,
                "win_rate": 0,
                "place_rate": 0,
                "show_rate": 0,
                "days_since_last": 365,
                "last_result": 0,
                "best_rank": 0,
            }

        results = [e.result for e in past_entries if e.result]

        avg_rank_last3 = np.mean(results[:3]) if len(results) >= 3 else np.mean(results) if results else 0
        avg_rank_last5 = np.mean(results[:5]) if len(results) >= 5 else np.mean(results) if results else 0

        total = len(results)
        wins = sum(1 for r in results if r == 1)
        places = sum(1 for r in results if r <= 2)
        shows = sum(1 for r in results if r <= 3)

        win_rate = wins / total if total > 0 else 0
        place_rate = places / total if total > 0 else 0
        show_rate = shows / total if total > 0 else 0

        best_rank = min(results) if results else 0
        last_result = results[0] if results else 0

        # 前走からの日数
        days_since_last = 365
        if history and race_date and history[0]['race_date']:
            days_since_last = (race_date - history[0]['race_date']).days
        elif past_entries and race_date:
            stmt = select(Race).where(Race.race_id == past_entries[0].race_id)
            last_race = self.db.execute(stmt).scalar_one_or_none()
            if last_race and last_race.date:
                days_since_last = (race_date - last_race.date).days

        return {
            "avg_rank_last3": avg_rank_last3,
            "avg_rank_last5": avg_rank_last5,
            "win_rate": win_rate,
            "place_rate": place_rate,
            "show_rate": show_rate,
            "days_since_last": days_since_last,
            "last_result": last_result,
            "best_rank": best_rank,
        }

    def _get_weight_class_features(self, horse_id: str, race_date: date) -> dict:
        """重量別成績特徴量"""
        # race_dateがNoneの場合はデフォルト値を返す
        if race_date is None:
            return {
                "light_weight_win_rate": 0,
                "mid_weight_win_rate": 0,
                "heavy_weight_win_rate": 0,
            }

        history = self.get_cached_history(horse_id, race_date, limit=50)

        if not history:
            stmt = (
                select(Entry)
                .join(Race)
                .where(Entry.horse_id == horse_id)
                .where(Race.race_type == "banei")
                .where(Race.date < race_date)
                .where(Entry.result.isnot(None))
                .where(Entry.weight.isnot(None))
                .order_by(Race.date.desc())
                .limit(50)
            )
            past_entries = list(self.db.execute(stmt).scalars().all())
        else:
            past_entries = [h['entry'] for h in history if h['entry'].weight]

        light_results = []  # <600kg
        mid_results = []    # 600-750kg
        heavy_results = []  # >750kg

        for e in past_entries:
            w = e.weight
            r = e.result
            if w and r:
                if w < 600:
                    light_results.append(r)
                elif w <= 750:
                    mid_results.append(r)
                else:
                    heavy_results.append(r)

        def calc_win_rate(results):
            if not results:
                return 0
            wins = sum(1 for r in results if r == 1)
            return wins / len(results)

        return {
            "light_weight_win_rate": calc_win_rate(light_results),
            "mid_weight_win_rate": calc_win_rate(mid_results),
            "heavy_weight_win_rate": calc_win_rate(heavy_results),
        }

    def _get_odds_features(self, entry: Entry) -> dict:
        """オッズ特徴量"""
        odds = entry.odds or 0
        popularity = entry.popularity or 0

        log_odds = np.log1p(odds) if odds > 0 else 0

        return {
            "odds": odds,
            "log_odds": log_odds,
            "popularity": popularity,
        }

    def _get_season_features(self, race_date: date) -> dict:
        """季節特徴量（ばんえいは冬季が重要）"""
        if race_date is None:
            return {
                "month": 0,
                "season": 0,
                "is_cold_season": 0,
            }

        month = race_date.month

        # 季節分類
        if month in [3, 4, 5]:
            season = 1  # 春
        elif month in [6, 7, 8]:
            season = 2  # 夏
        elif month in [9, 10, 11]:
            season = 3  # 秋
        else:
            season = 0  # 冬

        # 寒冷期フラグ（帯広の冬は厳しい）
        is_cold_season = 1 if month in [11, 12, 1, 2, 3] else 0

        return {
            "month": month,
            "season": season,
            "is_cold_season": is_cold_season,
        }


def prepare_banei_training_data(
    db: Session,
    min_date: Optional[date] = None,
    max_date: Optional[date] = None,
    progress_callback: Optional[callable] = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    ばんえい用学習データを準備する

    Args:
        db: データベースセッション
        min_date: 最小日付
        max_date: 最大日付
        progress_callback: 進捗コールバック関数

    Returns:
        X: 特徴量DataFrame
        y: ターゲット（着順）
    """
    extractor = BaneiFeatureExtractor(db, use_cache=True)

    # ばんえいレースのみを取得
    stmt = (
        select(Race)
        .where(Race.race_type == "banei")
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
            all_targets.extend(df["result"].tolist())
            all_features.append(df)

    if not all_features:
        return pd.DataFrame(), pd.Series(dtype=float)

    X = pd.concat(all_features, ignore_index=True)
    y = pd.Series(all_targets)

    # 特徴量カラムのみを選択
    feature_cols = get_banei_feature_columns()
    X = X[feature_cols]

    # 欠損値を埋める
    X = X.fillna(0)

    return X, y


def prepare_banei_time_split_data(
    db: Session,
    train_end_date: date,
    valid_end_date: date,
    train_start_date: Optional[date] = None,
    progress_callback: Optional[callable] = None,
) -> dict:
    """
    時系列ベースでばんえい学習・検証・テストデータを準備する
    """
    from datetime import timedelta

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
    X_train, y_train = prepare_banei_training_data(
        db,
        min_date=train_start_date,
        max_date=train_end_date,
        progress_callback=make_phase_callback("train", 0),
    )

    # 検証データ
    valid_start = train_end_date + timedelta(days=1)
    if progress_callback:
        progress_callback("valid", 0, 1, "検証データを準備中...", 0.33)
    X_valid, y_valid = prepare_banei_training_data(
        db,
        min_date=valid_start,
        max_date=valid_end_date,
        progress_callback=make_phase_callback("valid", 1),
    )

    # テストデータ
    test_start = valid_end_date + timedelta(days=1)
    if progress_callback:
        progress_callback("test", 0, 1, "テストデータを準備中...", 0.66)
    X_test, y_test = prepare_banei_training_data(
        db,
        min_date=test_start,
        progress_callback=make_phase_callback("test", 2),
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
