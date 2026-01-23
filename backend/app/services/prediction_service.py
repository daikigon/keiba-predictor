from datetime import datetime
from functools import lru_cache
from itertools import combinations
from typing import Optional
import time

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models.prediction import Prediction, History
from app.models.race import Race, Entry
from app.services.predictor import FeatureExtractor, get_model
from app.services.predictor.model import DEFAULT_RACE_TYPE, RACE_TYPES

logger = get_logger(__name__)

# レースタイプ別のモデルバージョン
MODEL_VERSION = "v1"
MODEL_VERSIONS: dict[str, str] = {
    "central": "v1",
    "local": "v1",
    "banei": "v1",
}

# 期待値ベース推奨のデフォルト閾値（PDF推奨値に準拠）
DEFAULT_EV_THRESHOLD = 1.0  # 期待値が1.0以上で推奨
DEFAULT_MAX_EV = 2.0  # 期待値の上限（高すぎる穴馬を除外）
DEFAULT_UMAREN_EV_THRESHOLD = 1.2  # 馬連は少し高めの閾値
DEFAULT_UMAREN_MAX_EV = 5.0  # 馬連の期待値上限
DEFAULT_MIN_PRED = 0.01  # 最低予測確率（1%未満は除外）
DEFAULT_UMAREN_TOP_N = 3  # 馬連の組み合わせ対象馬数

# レースタイプ別のグローバルモデルインスタンス
_predictors: dict[str, any] = {}

# 後方互換性のため（centralのモデル）
_predictor = None

# 予測結果キャッシュ（TTL: 5分）
_prediction_cache: dict[str, tuple[float, dict]] = {}
CACHE_TTL_SECONDS = 300  # 5分


def _get_cached_prediction(race_id: str) -> Optional[dict]:
    """キャッシュから予測結果を取得"""
    if race_id in _prediction_cache:
        cached_time, cached_result = _prediction_cache[race_id]
        if time.time() - cached_time < CACHE_TTL_SECONDS:
            logger.debug(f"Cache hit for race {race_id}")
            return cached_result
        else:
            # 期限切れの場合は削除
            del _prediction_cache[race_id]
    return None


def _set_cached_prediction(race_id: str, result: dict) -> None:
    """予測結果をキャッシュに保存"""
    _prediction_cache[race_id] = (time.time(), result)
    logger.debug(f"Cached prediction for race {race_id}")


def clear_prediction_cache(race_id: Optional[str] = None) -> int:
    """
    予測キャッシュをクリア

    Args:
        race_id: 特定のレースIDのみクリア。Noneの場合は全クリア

    Returns:
        クリアしたエントリ数
    """
    global _prediction_cache
    if race_id:
        if race_id in _prediction_cache:
            del _prediction_cache[race_id]
            return 1
        return 0
    else:
        count = len(_prediction_cache)
        _prediction_cache = {}
        return count


def get_predictor(race_type: str = DEFAULT_RACE_TYPE):
    """
    学習済みモデルを取得（レースタイプ別シングルトン）

    Args:
        race_type: レースタイプ（central, local, banei）

    Returns:
        HorseRacingPredictor インスタンス
    """
    global _predictors, _predictor

    # レースタイプのバリデーション
    if race_type not in RACE_TYPES:
        race_type = DEFAULT_RACE_TYPE

    # キャッシュにあればそれを返す
    if race_type in _predictors:
        return _predictors[race_type]

    # 新しいモデルを読み込み
    version = MODEL_VERSIONS.get(race_type, MODEL_VERSION)
    predictor = get_model(version, race_type)
    _predictors[race_type] = predictor

    # 後方互換性: centralの場合は_predictorにも設定
    if race_type == DEFAULT_RACE_TYPE:
        _predictor = predictor

    return predictor


def set_predictor(predictor, race_type: str = DEFAULT_RACE_TYPE):
    """
    モデルを設定（モデル切り替え用）

    Args:
        predictor: HorseRacingPredictorインスタンス
        race_type: レースタイプ
    """
    global _predictors, _predictor, MODEL_VERSIONS

    _predictors[race_type] = predictor
    MODEL_VERSIONS[race_type] = predictor.model_version

    # 後方互換性
    if race_type == DEFAULT_RACE_TYPE:
        _predictor = predictor
        global MODEL_VERSION
        MODEL_VERSION = predictor.model_version


def create_prediction(db: Session, race_id: str) -> Prediction:
    """Create prediction for a race using the current model"""
    race = db.get(Race, race_id)
    if not race:
        raise ValueError(f"Race {race_id} not found")

    # Generate predictions for each horse
    predictions_result = _generate_predictions(db, race)

    prediction = Prediction(
        race_id=race_id,
        model_version=MODEL_VERSION,
        results_json=predictions_result,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def get_prediction_by_race(db: Session, race_id: str) -> Optional[Prediction]:
    """Get the latest prediction for a race"""
    stmt = select(Prediction).where(
        Prediction.race_id == race_id
    ).order_by(Prediction.created_at.desc()).limit(1)
    return db.execute(stmt).scalar_one_or_none()


def get_prediction_by_id(db: Session, prediction_id: int) -> Optional[Prediction]:
    """Get prediction by ID"""
    return db.get(Prediction, prediction_id)


def _generate_predictions(db: Session, race: Race) -> dict:
    """
    Generate predictions for a race.
    Uses ML model if available, otherwise falls back to odds-based baseline.
    Caches results for 5 minutes.
    """
    # キャッシュから取得を試みる
    cached = _get_cached_prediction(race.race_id)
    if cached:
        return cached

    entries = sorted(race.entries, key=lambda e: e.horse_number)

    # MLモデルでの予測を試みる
    predictor = get_predictor()
    use_ml = predictor.model is not None

    if use_ml:
        predictions = _generate_ml_predictions(db, race, predictor)
    else:
        predictions = _generate_baseline_predictions(entries)

    result = {
        "predictions": predictions,
        "recommended_bets": _generate_recommended_bets(predictions),
        "model_type": "ml" if use_ml else "baseline",
    }

    # キャッシュに保存
    _set_cached_prediction(race.race_id, result)

    return result


def _generate_ml_predictions(db: Session, race: Race, predictor) -> list[dict]:
    """MLモデルを使用した予測"""
    try:
        extractor = FeatureExtractor(db)
        df = extractor.extract_race_features(race)

        if df.empty:
            logger.warning(f"No features extracted for race {race.race_id}, falling back to baseline")
            return _generate_baseline_predictions(race.entries)

        # 予測スコアを取得
        scores = predictor.predict(df)
        df["pred_score"] = scores

        # キャリブレーション済み確率を取得（または従来のソフトマックス）
        probabilities = predictor.predict_proba(df)
        df["probability"] = probabilities

        # ランキングを計算（スコアが高いほど上位）
        df["predicted_rank"] = df["pred_score"].rank(ascending=False).astype(int)

        # 結果を構築
        predictions = []
        for _, row in df.iterrows():
            entry = next(
                (e for e in race.entries if e.horse_number == row["horse_number"]),
                None
            )
            odds = entry.odds if entry else None

            # 単勝期待値を計算: 期待値 = 予測勝率 × オッズ
            tansho_ev = 0.0
            if odds and odds > 0:
                tansho_ev = float(row["probability"]) * odds

            predictions.append({
                "horse_number": int(row["horse_number"]),
                "horse_id": row["horse_id"],
                "horse_name": entry.horse.name if entry and entry.horse else None,
                "predicted_rank": int(row["predicted_rank"]),
                "probability": round(float(row["probability"]), 4),
                "score": round(float(row["pred_score"]), 4),
                "odds": odds,
                "popularity": entry.popularity if entry else None,
                "tansho_ev": round(tansho_ev, 3),  # 単勝期待値
            })

        # 予測順位でソート
        predictions.sort(key=lambda x: x["predicted_rank"])
        return predictions

    except Exception as e:
        logger.error(f"ML prediction failed for race {race.race_id}: {e}")
        return _generate_baseline_predictions(race.entries)


def _generate_baseline_predictions(entries) -> list[dict]:
    """オッズベースのベースライン予測"""
    entries_list = sorted(entries, key=lambda e: e.horse_number)

    # Simple baseline: use odds for ranking (lower odds = higher predicted rank)
    entries_with_odds = [e for e in entries_list if e.odds is not None]
    entries_no_odds = [e for e in entries_list if e.odds is None]

    # Sort by odds
    entries_with_odds.sort(key=lambda e: e.odds)

    # Combine with entries without odds at the end
    ranked_entries = entries_with_odds + entries_no_odds

    predictions = []
    for rank, entry in enumerate(ranked_entries, 1):
        # Calculate a simple probability score based on odds
        if entry.odds and entry.odds > 0:
            prob = 1 / entry.odds
        else:
            prob = 0.01  # Default low probability

        predictions.append({
            "horse_number": entry.horse_number,
            "horse_id": entry.horse_id,
            "horse_name": entry.horse.name if entry.horse else None,
            "predicted_rank": rank,
            "probability": round(prob, 4),
            "odds": entry.odds,
            "popularity": entry.popularity,
            "tansho_ev": 0.0,  # ベースラインでは期待値未計算
        })

    # Normalize probabilities
    total_prob = sum(p["probability"] for p in predictions)
    if total_prob > 0:
        for p in predictions:
            p["probability"] = round(p["probability"] / total_prob, 4)
            # 正規化後の確率で期待値を再計算
            if p["odds"] and p["odds"] > 0:
                p["tansho_ev"] = round(p["probability"] * p["odds"], 3)

    # Sort by predicted rank for output
    predictions.sort(key=lambda x: x["predicted_rank"])
    return predictions


def _calculate_umaren_probability(predictions: list[dict], horse1_num: int, horse2_num: int) -> float:
    """
    馬連の的中確率を計算

    2頭が1着・2着に入る確率（順不同）
    P(A,B) = P(A勝ち)×P(B|A勝ち) + P(B勝ち)×P(A|B勝ち)

    簡易計算: P(A) × P(B) × 補正係数
    """
    horse1 = next((p for p in predictions if p["horse_number"] == horse1_num), None)
    horse2 = next((p for p in predictions if p["horse_number"] == horse2_num), None)

    if not horse1 or not horse2:
        return 0.0

    p1 = horse1["probability"]
    p2 = horse2["probability"]

    # 上位2頭が入る確率を計算
    # 簡易モデル: 勝率を使った近似
    # 実際は条件付き確率を使うべきだが、ここでは積に補正係数をかける
    n_horses = len(predictions)
    correction = n_horses / 2 if n_horses > 2 else 1

    # 順不同なので両方のケースを考慮
    umaren_prob = (p1 * p2 * correction) * 2

    return min(umaren_prob, 1.0)  # 1を超えないように


def _generate_recommended_bets(
    predictions: list[dict],
    umaren_odds: dict = None,
    ev_threshold: float = DEFAULT_EV_THRESHOLD,
    max_ev: float = DEFAULT_MAX_EV,
    umaren_ev_threshold: float = DEFAULT_UMAREN_EV_THRESHOLD,
    umaren_max_ev: float = DEFAULT_UMAREN_MAX_EV,
    min_pred: float = DEFAULT_MIN_PRED,
    umaren_top_n: int = DEFAULT_UMAREN_TOP_N,
) -> list[dict]:
    """
    期待値ベースで推奨買い目を生成

    Args:
        predictions: 馬ごとの予測結果
        umaren_odds: 馬連オッズ辞書 {(馬番1, 馬番2): オッズ}
        ev_threshold: 単勝の期待値下限（デフォルト: 1.0）
        max_ev: 単勝の期待値上限（デフォルト: 2.0）- 高すぎる穴馬を除外
        umaren_ev_threshold: 馬連の期待値下限（デフォルト: 1.2）
        umaren_max_ev: 馬連の期待値上限（デフォルト: 5.0）
        min_pred: 最低予測確率（デフォルト: 0.01）
        umaren_top_n: 馬連の組み合わせ対象馬数（デフォルト: 3）

    Returns:
        推奨買い目リスト
    """
    if len(predictions) < 2:
        return []

    bets = []

    # === 単勝の期待値ベース推奨 ===
    tansho_candidates = []
    for pred in predictions:
        # 最低確率フィルター
        if pred["probability"] < min_pred:
            continue

        ev = pred.get("tansho_ev", 0)
        # 期待値の下限・上限チェック
        if ev >= ev_threshold and ev <= max_ev:
            confidence = "high" if ev >= 1.5 else "medium"
            tansho_candidates.append({
                "bet_type": "単勝",
                "detail": str(pred["horse_number"]),
                "horse_name": pred.get("horse_name"),
                "confidence": confidence,
                "expected_value": round(ev, 3),
                "probability": pred["probability"],
                "odds": pred["odds"],
            })

    # 期待値が高い順にソート
    tansho_candidates.sort(key=lambda x: x["expected_value"], reverse=True)
    bets.extend(tansho_candidates[:3])  # 上位3件まで

    # === 馬連の期待値ベース推奨 ===
    umaren_candidates = []

    # 最低確率を満たす馬のみ対象にして、上位N頭の組み合わせを検討
    eligible_horses = [p for p in predictions if p["probability"] >= min_pred]
    top_horses = sorted(eligible_horses, key=lambda x: x["predicted_rank"])[:umaren_top_n]

    for h1, h2 in combinations(top_horses, 2):
        num1, num2 = h1["horse_number"], h2["horse_number"]

        # 馬連確率を計算
        umaren_prob = _calculate_umaren_probability(predictions, num1, num2)

        # 馬連オッズが提供されていれば使用、なければ推定
        if umaren_odds and (num1, num2) in umaren_odds:
            odds = umaren_odds[(num1, num2)]
        elif umaren_odds and (num2, num1) in umaren_odds:
            odds = umaren_odds[(num2, num1)]
        else:
            # オッズがない場合は単勝オッズから推定
            # 馬連オッズ ≈ (単勝1 × 単勝2) / 補正係数
            o1 = h1.get("odds", 10) or 10
            o2 = h2.get("odds", 10) or 10
            odds = (o1 * o2) / 3  # 経験的補正

        # 期待値を計算
        umaren_ev = umaren_prob * odds

        # 期待値の下限・上限チェック
        if umaren_ev >= umaren_ev_threshold and umaren_ev <= umaren_max_ev:
            confidence = "high" if umaren_ev >= 1.8 else "medium"
            umaren_candidates.append({
                "bet_type": "馬連",
                "detail": f"{min(num1, num2)}-{max(num1, num2)}",
                "horse_names": [h1.get("horse_name"), h2.get("horse_name")],
                "confidence": confidence,
                "expected_value": round(umaren_ev, 3),
                "probability": round(umaren_prob, 4),
                "odds": round(odds, 1) if odds else None,
            })

    # 期待値が高い順にソート
    umaren_candidates.sort(key=lambda x: x["expected_value"], reverse=True)
    bets.extend(umaren_candidates[:5])  # 上位5件まで

    # === 期待値が低くても上位馬のベーシック推奨 ===
    if len(predictions) >= 3:
        top3 = predictions[:3]

        # 既に単勝推奨がない場合、1番人気を追加
        has_tansho = any(b["bet_type"] == "単勝" for b in bets)
        if not has_tansho:
            bets.append({
                "bet_type": "単勝",
                "detail": str(top3[0]["horse_number"]),
                "horse_name": top3[0].get("horse_name"),
                "confidence": "low",
                "expected_value": top3[0].get("tansho_ev", 0),
                "probability": top3[0]["probability"],
                "odds": top3[0]["odds"],
            })

        # 複勝（参考として追加）
        bets.append({
            "bet_type": "複勝",
            "detail": str(top3[0]["horse_number"]),
            "horse_name": top3[0].get("horse_name"),
            "confidence": "high",
        })

    return bets


# History functions
def get_history(
    db: Session,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[History], dict]:
    """Get prediction history with summary"""
    query = select(History)

    if from_date:
        query = query.where(History.created_at >= from_date)
    if to_date:
        query = query.where(History.created_at <= to_date)

    # Get total count
    count_result = db.execute(
        select(func.count(History.id)).where(
            (History.created_at >= from_date) if from_date else True,
            (History.created_at <= to_date) if to_date else True,
        )
    ).scalar()
    total = count_result or 0

    # Get paginated results
    query = query.order_by(History.created_at.desc()).offset(offset).limit(limit)
    history_list = list(db.execute(query).scalars().all())

    # Calculate summary
    summary = _calculate_summary(db, from_date, to_date)

    return total, history_list, summary


def _calculate_summary(
    db: Session,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> dict:
    """Calculate betting summary statistics"""
    query = select(History).where(History.is_hit.isnot(None))

    if from_date:
        query = query.where(History.created_at >= from_date)
    if to_date:
        query = query.where(History.created_at <= to_date)

    history_list = db.execute(query).scalars().all()

    total_bets = len(history_list)
    total_hits = sum(1 for h in history_list if h.is_hit)
    total_bet_amount = sum(h.bet_amount or 0 for h in history_list)
    total_payout = sum(h.payout or 0 for h in history_list if h.is_hit)

    hit_rate = (total_hits / total_bets * 100) if total_bets > 0 else 0.0
    roi = ((total_payout / total_bet_amount - 1) * 100) if total_bet_amount > 0 else 0.0

    return {
        "total_bets": total_bets,
        "total_hits": total_hits,
        "hit_rate": round(hit_rate, 2),
        "total_bet_amount": total_bet_amount,
        "total_payout": total_payout,
        "roi": round(roi, 2),
    }


def create_history(
    db: Session,
    prediction_id: int,
    bet_type: str,
    bet_detail: str,
    bet_amount: Optional[int] = None,
) -> History:
    """Create a history entry for a bet"""
    history = History(
        prediction_id=prediction_id,
        bet_type=bet_type,
        bet_detail=bet_detail,
        bet_amount=bet_amount,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


def update_history_result(
    db: Session,
    history_id: int,
    is_hit: bool,
    payout: Optional[int] = None,
) -> Optional[History]:
    """Update history with result"""
    history = db.get(History, history_id)
    if not history:
        return None

    history.is_hit = is_hit
    history.payout = payout if is_hit else 0
    db.commit()
    db.refresh(history)
    return history
