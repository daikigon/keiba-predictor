from datetime import datetime
from functools import lru_cache
from typing import Optional
import time

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.models.prediction import Prediction, History
from app.models.race import Race, Entry
from app.services.predictor import FeatureExtractor, get_model

logger = get_logger(__name__)

MODEL_VERSION = "v1"

# グローバルモデルインスタンス（起動時に一度だけ読み込み）
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


def get_predictor():
    """学習済みモデルを取得（シングルトン）"""
    global _predictor
    if _predictor is None:
        _predictor = get_model(MODEL_VERSION)
    return _predictor


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

        # スコアをソフトマックスで確率に変換
        import numpy as np
        exp_scores = np.exp(scores - np.max(scores))  # オーバーフロー防止
        probabilities = exp_scores / exp_scores.sum()
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
            predictions.append({
                "horse_number": int(row["horse_number"]),
                "horse_id": row["horse_id"],
                "horse_name": entry.horse.name if entry and entry.horse else None,
                "predicted_rank": int(row["predicted_rank"]),
                "probability": round(float(row["probability"]), 4),
                "score": round(float(row["pred_score"]), 4),
                "odds": entry.odds if entry else None,
                "popularity": entry.popularity if entry else None,
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
        })

    # Normalize probabilities
    total_prob = sum(p["probability"] for p in predictions)
    if total_prob > 0:
        for p in predictions:
            p["probability"] = round(p["probability"] / total_prob, 4)

    # Sort by predicted rank for output
    predictions.sort(key=lambda x: x["predicted_rank"])
    return predictions


def _generate_recommended_bets(predictions: list[dict]) -> list[dict]:
    """Generate recommended bets based on predictions"""
    if len(predictions) < 3:
        return []

    top3 = predictions[:3]

    bets = [
        {
            "bet_type": "単勝",
            "detail": str(top3[0]["horse_number"]),
            "confidence": "high" if top3[0]["probability"] > 0.3 else "medium",
        },
        {
            "bet_type": "複勝",
            "detail": str(top3[0]["horse_number"]),
            "confidence": "high",
        },
        {
            "bet_type": "馬連",
            "detail": f"{top3[0]['horse_number']}-{top3[1]['horse_number']}",
            "confidence": "medium",
        },
        {
            "bet_type": "三連複",
            "detail": f"{top3[0]['horse_number']}-{top3[1]['horse_number']}-{top3[2]['horse_number']}",
            "confidence": "low",
        },
    ]

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
