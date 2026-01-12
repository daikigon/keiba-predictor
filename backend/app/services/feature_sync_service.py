"""
特徴量同期サービス

馬・騎手・調教師の特徴量を事前計算してSupabase DBに保存する。
Google Colabからの当日予想で使用する。
"""
import logging
from datetime import date, datetime
from typing import Optional
import numpy as np

from sqlalchemy import select, func, text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Horse, Jockey, Entry, Race
from app.config import settings

logger = logging.getLogger(__name__)


def get_supabase_client():
    """Supabaseクライアントを取得"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return None
    try:
        from supabase import create_client
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        return None


def compute_horse_features(db: Session, horse_id: str, as_of_date: Optional[date] = None) -> dict:
    """
    馬の特徴量を計算

    Args:
        db: データベースセッション
        horse_id: 馬ID
        as_of_date: 基準日（指定しない場合は現在）

    Returns:
        特徴量の辞書
    """
    if as_of_date is None:
        as_of_date = date.today()

    # 馬情報を取得
    horse = db.execute(select(Horse).where(Horse.horse_id == horse_id)).scalar_one_or_none()

    # 過去成績を取得
    stmt = (
        select(Entry, Race)
        .join(Race, Entry.race_id == Race.race_id)
        .where(Entry.horse_id == horse_id)
        .where(Race.date < as_of_date)
        .where(Entry.result.isnot(None))
        .order_by(Race.date.desc())
    )
    results = db.execute(stmt).all()

    if not results:
        return {"horse_id": horse_id}

    entries = [r[0] for r in results]
    races = [r[1] for r in results]

    features = {"horse_id": horse_id}

    # 基本情報
    if horse:
        features["horse_age"] = _calculate_age(horse.birth_year, as_of_date.year)
        features["horse_sex"] = _encode_sex(horse.sex)

    # 過去成績
    all_results = [e.result for e in entries if e.result]
    features["total_runs"] = len(all_results)

    if all_results:
        features["avg_rank_last3"] = np.mean(all_results[:3]) if len(all_results) >= 1 else None
        features["avg_rank_last5"] = np.mean(all_results[:5]) if len(all_results) >= 3 else None
        features["avg_rank_last10"] = np.mean(all_results[:10]) if len(all_results) >= 5 else None
        features["avg_rank_all"] = np.mean(all_results)
        features["best_rank"] = min(all_results)
        features["win_rate"] = sum(1 for r in all_results if r == 1) / len(all_results)
        features["place_rate"] = sum(1 for r in all_results if r <= 2) / len(all_results)
        features["show_rate"] = sum(1 for r in all_results if r <= 3) / len(all_results)

    # 賞金
    prizes = [e.prize_money for e in entries if e.prize_money]
    if prizes:
        features["prize_3races"] = sum(prizes[:3])
        features["prize_5races"] = sum(prizes[:5])
        features["prize_10races"] = sum(prizes[:10])

    # 前走情報
    if entries:
        features["last_result"] = entries[0].result
        if races:
            days = (as_of_date - races[0].date).days
            features["days_since_last"] = days

    # 上がり3F
    last3f_times = [e.last_3f for e in entries if e.last_3f]
    if last3f_times:
        features["avg_last3f"] = np.mean(last3f_times[:10])
        features["best_last3f"] = min(last3f_times)

    # コース適性（芝/ダート）
    turf_entries = [(e, r) for e, r in zip(entries, races) if r.track_type == "芝"]
    dirt_entries = [(e, r) for e, r in zip(entries, races) if r.track_type == "ダート"]

    if turf_entries:
        turf_results = [e.result for e, r in turf_entries if e.result]
        features["turf_runs"] = len(turf_results)
        if turf_results:
            features["turf_win_rate"] = sum(1 for r in turf_results if r == 1) / len(turf_results)
            features["turf_show_rate"] = sum(1 for r in turf_results if r <= 3) / len(turf_results)

    if dirt_entries:
        dirt_results = [e.result for e, r in dirt_entries if e.result]
        features["dirt_runs"] = len(dirt_results)
        if dirt_results:
            features["dirt_win_rate"] = sum(1 for r in dirt_results if r == 1) / len(dirt_results)
            features["dirt_show_rate"] = sum(1 for r in dirt_results if r <= 3) / len(dirt_results)

    # 距離適性
    def get_distance_stats(min_dist, max_dist):
        dist_entries = [(e, r) for e, r in zip(entries, races)
                        if r.distance and min_dist <= r.distance <= max_dist]
        if not dist_entries:
            return None, None, 0
        dist_results = [e.result for e, r in dist_entries if e.result]
        if not dist_results:
            return None, None, len(dist_entries)
        win_rate = sum(1 for r in dist_results if r == 1) / len(dist_results)
        show_rate = sum(1 for r in dist_results if r <= 3) / len(dist_results)
        return win_rate, show_rate, len(dist_results)

    features["short_win_rate"], features["short_show_rate"], features["short_runs"] = get_distance_stats(0, 1400)
    features["mile_win_rate"], features["mile_show_rate"], features["mile_runs"] = get_distance_stats(1401, 1800)
    features["middle_win_rate"], features["middle_show_rate"], features["middle_runs"] = get_distance_stats(1801, 2200)
    features["long_win_rate"], features["long_show_rate"], features["long_runs"] = get_distance_stats(2201, 9999)

    # 脚質
    corner_positions = []
    for e in entries[:20]:  # 直近20走
        if e.corner_position:
            try:
                positions = [int(p) for p in e.corner_position.replace(" ", "-").split("-") if p.strip().isdigit()]
                if positions:
                    corner_positions.append(positions)
            except:
                pass

    if corner_positions:
        first_corners = [p[0] for p in corner_positions if p]
        last_corners = [p[-1] for p in corner_positions if p]

        features["avg_first_corner"] = np.mean(first_corners)
        features["avg_last_corner"] = np.mean(last_corners)
        features["position_up_avg"] = np.mean([f - l for f, l in zip(first_corners, last_corners)])

        # 脚質分類
        avg_pos = features["avg_first_corner"]
        if avg_pos <= 3:
            features["running_style"] = 1  # 逃げ
            features["escape_rate"] = sum(1 for p in first_corners if p <= 2) / len(first_corners)
        elif avg_pos <= 6:
            features["running_style"] = 2  # 先行
        elif avg_pos <= 10:
            features["running_style"] = 3  # 差し
        else:
            features["running_style"] = 4  # 追込

        features["front_rate"] = sum(1 for p in first_corners if p <= 4) / len(first_corners)
        features["stalker_rate"] = sum(1 for p in first_corners if 3 <= p <= 6) / len(first_corners)
        features["closer_rate"] = sum(1 for p in first_corners if p >= 7) / len(first_corners)

    # ペース
    pace_firsts = []
    pace_seconds = []
    for e in entries[:20]:
        if e.pace:
            try:
                parts = e.pace.split("-")
                if len(parts) >= 2:
                    pace_firsts.append(float(parts[0]))
                    pace_seconds.append(float(parts[1]))
            except:
                pass

    if pace_firsts:
        features["avg_pace_first"] = np.mean(pace_firsts)
        features["avg_pace_second"] = np.mean(pace_seconds)
        features["avg_pace_diff"] = np.mean([s - f for f, s in zip(pace_firsts, pace_seconds)])
        if len(pace_firsts) > 1:
            features["pace_consistency"] = np.std(pace_firsts)

    # 人気別成績
    def get_pop_stats(min_pop, max_pop):
        pop_entries = [e for e in entries if e.popularity and min_pop <= e.popularity <= max_pop]
        if not pop_entries:
            return None, None, 0
        pop_results = [e.result for e in pop_entries if e.result]
        if not pop_results:
            return None, None, len(pop_entries)
        win_rate = sum(1 for r in pop_results if r == 1) / len(pop_results)
        show_rate = sum(1 for r in pop_results if r <= 3) / len(pop_results)
        return win_rate, show_rate, len(pop_entries)

    features["high_pop_win_rate"], features["high_pop_show_rate"], features["high_pop_runs"] = get_pop_stats(1, 3)
    features["mid_pop_win_rate"], features["mid_pop_show_rate"], features["mid_pop_runs"] = get_pop_stats(4, 6)
    features["low_pop_win_rate"], features["low_pop_show_rate"], features["low_pop_runs"] = get_pop_stats(7, 99)

    # 勝利時の平均オッズ
    win_odds = [e.odds for e in entries if e.result == 1 and e.odds]
    if win_odds:
        features["avg_odds_when_win"] = np.mean(win_odds)

    return features


def compute_jockey_features(db: Session, jockey_id: str) -> dict:
    """騎手の特徴量を計算"""
    stmt = (
        select(Entry)
        .where(Entry.jockey_id == jockey_id)
        .where(Entry.result.isnot(None))
    )
    entries = list(db.execute(stmt).scalars().all())

    if not entries:
        return {"jockey_id": jockey_id}

    results = [e.result for e in entries if e.result]
    features = {
        "jockey_id": jockey_id,
        "total_rides": len(results),
        "total_wins": sum(1 for r in results if r == 1),
    }

    if results:
        features["win_rate"] = features["total_wins"] / len(results)
        features["place_rate"] = sum(1 for r in results if r <= 2) / len(results)
        features["show_rate"] = sum(1 for r in results if r <= 3) / len(results)

    return features


def _calculate_age(birth_year: Optional[int], current_year: int) -> Optional[int]:
    """年齢を計算"""
    if birth_year:
        return current_year - birth_year
    return None


def _encode_sex(sex: Optional[str]) -> Optional[int]:
    """性別をエンコード"""
    if sex == "牡":
        return 1
    elif sex == "牝":
        return 2
    elif sex == "セ":
        return 3
    return None


def sync_horse_features_to_supabase(
    db: Session,
    limit: Optional[int] = None,
    progress_callback: Optional[callable] = None,
) -> dict:
    """
    全馬の特徴量をSupabaseに同期

    Args:
        db: データベースセッション
        limit: 処理する馬の上限数
        progress_callback: 進捗コールバック (current, total, message)

    Returns:
        同期結果
    """
    supabase = get_supabase_client()
    if not supabase:
        return {"status": "error", "message": "Supabase not configured"}

    # アクティブな馬を取得（直近1年以内に出走）
    one_year_ago = date.today().replace(year=date.today().year - 1)
    stmt = (
        select(Entry.horse_id)
        .join(Race, Entry.race_id == Race.race_id)
        .where(Race.date >= one_year_ago)
        .where(Entry.horse_id.isnot(None))
        .distinct()
    )

    if limit:
        stmt = stmt.limit(limit)

    horse_ids = [r[0] for r in db.execute(stmt).all()]
    total = len(horse_ids)

    logger.info(f"Syncing features for {total} horses")

    synced = 0
    errors = 0

    for i, horse_id in enumerate(horse_ids):
        try:
            if progress_callback and i % 100 == 0:
                progress_callback(i, total, f"Processing horse {horse_id}")

            features = compute_horse_features(db, horse_id)

            # Noneをnullに変換、numpy型をPython型に変換
            clean_features = {}
            for k, v in features.items():
                if v is None:
                    clean_features[k] = None
                elif isinstance(v, (np.floating, np.integer)):
                    clean_features[k] = float(v) if np.isfinite(v) else None
                else:
                    clean_features[k] = v

            clean_features["updated_at"] = datetime.now().isoformat()

            # Upsert
            supabase.table("horse_features").upsert(
                clean_features,
                on_conflict="horse_id"
            ).execute()

            synced += 1

        except Exception as e:
            logger.error(f"Error syncing horse {horse_id}: {e}")
            errors += 1

    result = {
        "status": "success",
        "total_horses": total,
        "synced": synced,
        "errors": errors,
    }

    logger.info(f"Feature sync complete: {result}")
    return result


def sync_jockey_features_to_supabase(
    db: Session,
    limit: Optional[int] = None,
) -> dict:
    """全騎手の特徴量をSupabaseに同期"""
    supabase = get_supabase_client()
    if not supabase:
        return {"status": "error", "message": "Supabase not configured"}

    # アクティブな騎手を取得
    one_year_ago = date.today().replace(year=date.today().year - 1)
    stmt = (
        select(Entry.jockey_id)
        .join(Race, Entry.race_id == Race.race_id)
        .where(Race.date >= one_year_ago)
        .where(Entry.jockey_id.isnot(None))
        .distinct()
    )

    if limit:
        stmt = stmt.limit(limit)

    jockey_ids = [r[0] for r in db.execute(stmt).all()]
    total = len(jockey_ids)

    logger.info(f"Syncing features for {total} jockeys")

    synced = 0
    errors = 0

    for jockey_id in jockey_ids:
        try:
            features = compute_jockey_features(db, jockey_id)

            clean_features = {}
            for k, v in features.items():
                if v is None:
                    clean_features[k] = None
                elif isinstance(v, (np.floating, np.integer)):
                    clean_features[k] = float(v) if np.isfinite(v) else None
                else:
                    clean_features[k] = v

            clean_features["updated_at"] = datetime.now().isoformat()

            supabase.table("jockey_features").upsert(
                clean_features,
                on_conflict="jockey_id"
            ).execute()

            synced += 1

        except Exception as e:
            logger.error(f"Error syncing jockey {jockey_id}: {e}")
            errors += 1

    return {
        "status": "success",
        "total_jockeys": total,
        "synced": synced,
        "errors": errors,
    }


def sync_all_features(
    limit: Optional[int] = None,
    progress_callback: Optional[callable] = None,
) -> dict:
    """全特徴量を同期（馬 + 騎手）"""
    db = SessionLocal()
    try:
        horse_result = sync_horse_features_to_supabase(db, limit, progress_callback)
        jockey_result = sync_jockey_features_to_supabase(db, limit)

        return {
            "status": "success",
            "horse_features": horse_result,
            "jockey_features": jockey_result,
        }
    finally:
        db.close()
