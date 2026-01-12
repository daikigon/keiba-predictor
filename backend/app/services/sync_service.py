"""
Supabase Sync サービス

ローカルDBからSupabaseへのデータ同期を管理
差分同期対応: 前回同期以降の更新分 + 失敗したレコードのみを同期
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Set
import threading
import json
import os

from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import get_logger
from app.models import Horse, Jockey, Race, Entry
from app.services.storage_service import get_supabase_client

logger = get_logger(__name__)

# 同期状態ファイルのパス
SYNC_STATE_FILE = os.path.join(os.path.dirname(__file__), ".sync_state.json")

# 同期状態管理
_sync_status: Dict[str, Any] = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "current_table": None,
    "results": None,
    "error": None,
}
_sync_lock = threading.Lock()


def _load_sync_state() -> Dict[str, Any]:
    """前回の同期状態を読み込む"""
    if os.path.exists(SYNC_STATE_FILE):
        try:
            with open(SYNC_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load sync state: {e}")
    return {
        "last_sync_at": None,
        "failed_ids": {
            "horses": [],
            "jockeys": [],
            "races": [],
            "entries": [],
        }
    }


def _save_sync_state(state: Dict[str, Any]):
    """同期状態を保存"""
    try:
        with open(SYNC_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save sync state: {e}")


def get_sync_status() -> Dict[str, Any]:
    """同期状態を取得"""
    with _sync_lock:
        status = _sync_status.copy()

    # 前回の同期情報も追加
    state = _load_sync_state()
    status["last_sync_at"] = state.get("last_sync_at")
    status["pending_retries"] = sum(len(ids) for ids in state.get("failed_ids", {}).values())
    return status


def _update_status(**kwargs):
    """同期状態を更新"""
    with _sync_lock:
        _sync_status.update(kwargs)


def sync_to_supabase(db: Session, force_full: bool = False) -> Dict[str, Any]:
    """
    ローカルDBのデータをSupabaseに同期（差分同期）

    Args:
        db: ローカルDBセッション
        force_full: Trueの場合は全件同期

    Returns:
        同期結果
    """
    global _sync_status

    with _sync_lock:
        if _sync_status["is_running"]:
            raise RuntimeError("同期が既に実行中です")
        _sync_status = {
            "is_running": True,
            "progress": 0,
            "total": 0,
            "current_table": None,
            "results": None,
            "error": None,
        }

    try:
        client = get_supabase_client()
        if client is None:
            raise RuntimeError("Supabaseに接続できません")

        # 前回の同期状態を読み込む
        sync_state = _load_sync_state()
        last_sync_at = None
        if not force_full and sync_state.get("last_sync_at"):
            last_sync_at = datetime.fromisoformat(sync_state["last_sync_at"])

        failed_ids = sync_state.get("failed_ids", {
            "horses": [],
            "jockeys": [],
            "races": [],
            "entries": [],
        })

        results = {
            "horses": {"synced": 0, "errors": 0, "skipped": 0},
            "jockeys": {"synced": 0, "errors": 0, "skipped": 0},
            "races": {"synced": 0, "errors": 0, "skipped": 0},
            "entries": {"synced": 0, "errors": 0, "skipped": 0},
        }

        new_failed_ids: Dict[str, List] = {
            "horses": [],
            "jockeys": [],
            "races": [],
            "entries": [],
        }

        # 1. Horses を同期
        _update_status(current_table="horses")
        if force_full or last_sync_at is None:
            horses_to_sync = db.query(Horse).all()
            total_horses = len(horses_to_sync)
        else:
            # SQLレベルで差分フィルタ
            failed_horse_ids = failed_ids.get("horses", [])
            horses_to_sync = db.query(Horse).filter(
                (Horse.updated_at > last_sync_at) | (Horse.horse_id.in_(failed_horse_ids)) if failed_horse_ids
                else Horse.updated_at > last_sync_at
            ).all()
            total_horses = db.query(Horse).count()
        logger.info(f"Syncing {len(horses_to_sync)}/{total_horses} horses (diff sync)")

        total_to_sync = len(horses_to_sync)
        progress = 0

        for horse in horses_to_sync:
            try:
                data = {
                    "horse_id": horse.horse_id,
                    "name": horse.name,
                    "sex": horse.sex,
                    "birth_year": horse.birth_year,
                    "father": horse.father,
                    "mother": horse.mother,
                    "mother_father": horse.mother_father,
                    "trainer": horse.trainer,
                    "owner": horse.owner,
                    "created_at": horse.created_at.isoformat() if horse.created_at else None,
                    "updated_at": horse.updated_at.isoformat() if horse.updated_at else None,
                }
                client.table("horses").upsert(data, on_conflict="horse_id").execute()
                results["horses"]["synced"] += 1
            except Exception as e:
                logger.error(f"Failed to sync horse {horse.horse_id}: {e}")
                results["horses"]["errors"] += 1
                new_failed_ids["horses"].append(horse.horse_id)

            progress += 1
            _update_status(progress=progress)

        results["horses"]["skipped"] = total_horses - len(horses_to_sync)

        # 2. Jockeys を同期
        _update_status(current_table="jockeys")
        if force_full or last_sync_at is None:
            jockeys_to_sync = db.query(Jockey).all()
            total_jockeys = len(jockeys_to_sync)
        else:
            failed_jockey_ids = failed_ids.get("jockeys", [])
            jockeys_to_sync = db.query(Jockey).filter(
                (Jockey.updated_at > last_sync_at) | (Jockey.jockey_id.in_(failed_jockey_ids)) if failed_jockey_ids
                else Jockey.updated_at > last_sync_at
            ).all()
            total_jockeys = db.query(Jockey).count()
        logger.info(f"Syncing {len(jockeys_to_sync)}/{total_jockeys} jockeys (diff sync)")

        total_to_sync += len(jockeys_to_sync)
        _update_status(total=total_to_sync)

        for jockey in jockeys_to_sync:
            try:
                data = {
                    "jockey_id": jockey.jockey_id,
                    "name": jockey.name,
                    "win_rate": jockey.win_rate,
                    "place_rate": jockey.place_rate,
                    "show_rate": jockey.show_rate,
                    "year_rank": jockey.year_rank,
                    "year_wins": jockey.year_wins,
                    "year_rides": jockey.year_rides,
                    "year_earnings": jockey.year_earnings,
                    "created_at": jockey.created_at.isoformat() if jockey.created_at else None,
                    "updated_at": jockey.updated_at.isoformat() if jockey.updated_at else None,
                }
                client.table("jockeys").upsert(data, on_conflict="jockey_id").execute()
                results["jockeys"]["synced"] += 1
            except Exception as e:
                logger.error(f"Failed to sync jockey {jockey.jockey_id}: {e}")
                results["jockeys"]["errors"] += 1
                new_failed_ids["jockeys"].append(jockey.jockey_id)

            progress += 1
            _update_status(progress=progress)

        results["jockeys"]["skipped"] = total_jockeys - len(jockeys_to_sync)

        # 3. Races を同期
        _update_status(current_table="races")
        if force_full or last_sync_at is None:
            races_to_sync = db.query(Race).all()
            total_races = len(races_to_sync)
        else:
            failed_race_ids = failed_ids.get("races", [])
            races_to_sync = db.query(Race).filter(
                (Race.updated_at > last_sync_at) | (Race.race_id.in_(failed_race_ids)) if failed_race_ids
                else Race.updated_at > last_sync_at
            ).all()
            total_races = db.query(Race).count()
        logger.info(f"Syncing {len(races_to_sync)}/{total_races} races (diff sync)")

        total_to_sync += len(races_to_sync)
        _update_status(total=total_to_sync)

        for race in races_to_sync:
            try:
                data = {
                    "race_id": race.race_id,
                    "date": race.date.isoformat() if race.date else None,
                    "course": race.course,
                    "race_number": race.race_number,
                    "race_name": race.race_name,
                    "distance": race.distance,
                    "track_type": race.track_type,
                    "weather": race.weather,
                    "condition": race.condition,
                    "grade": race.grade,
                    "num_horses": race.num_horses,
                    "venue_detail": race.venue_detail,
                    "created_at": race.created_at.isoformat() if race.created_at else None,
                    "updated_at": race.updated_at.isoformat() if race.updated_at else None,
                }
                client.table("races").upsert(data, on_conflict="race_id").execute()
                results["races"]["synced"] += 1
            except Exception as e:
                logger.error(f"Failed to sync race {race.race_id}: {e}")
                results["races"]["errors"] += 1
                new_failed_ids["races"].append(race.race_id)

            progress += 1
            _update_status(progress=progress)

        results["races"]["skipped"] = total_races - len(races_to_sync)

        # 4. Entries を同期 (外部キー制約のため最後に)
        _update_status(current_table="entries")
        if force_full or last_sync_at is None:
            entries_to_sync = db.query(Entry).all()
            total_entries = len(entries_to_sync)
        else:
            failed_entry_ids = failed_ids.get("entries", [])
            entries_to_sync = db.query(Entry).filter(
                (Entry.updated_at > last_sync_at) | (Entry.id.in_(failed_entry_ids)) if failed_entry_ids
                else Entry.updated_at > last_sync_at
            ).all()
            total_entries = db.query(Entry).count()
        logger.info(f"Syncing {len(entries_to_sync)}/{total_entries} entries (diff sync)")

        total_to_sync += len(entries_to_sync)
        _update_status(total=total_to_sync)

        for entry in entries_to_sync:
            try:
                data = {
                    "id": entry.id,
                    "race_id": entry.race_id,
                    "horse_id": entry.horse_id,
                    "jockey_id": entry.jockey_id,
                    "frame_number": entry.frame_number,
                    "horse_number": entry.horse_number,
                    "weight": entry.weight,
                    "horse_weight": entry.horse_weight,
                    "weight_diff": entry.weight_diff,
                    "odds": entry.odds,
                    "popularity": entry.popularity,
                    "result": entry.result,
                    "finish_time": entry.finish_time,
                    "margin": entry.margin,
                    "corner_position": entry.corner_position,
                    "last_3f": entry.last_3f,
                    "pace": entry.pace,
                    "prize_money": entry.prize_money,
                    "winner_or_second": entry.winner_or_second,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None,
                    "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
                }
                client.table("entries").upsert(data, on_conflict="id").execute()
                results["entries"]["synced"] += 1
            except Exception as e:
                logger.error(f"Failed to sync entry {entry.id}: {e}")
                results["entries"]["errors"] += 1
                new_failed_ids["entries"].append(entry.id)

            progress += 1
            _update_status(progress=progress)

        results["entries"]["skipped"] = total_entries - len(entries_to_sync)

        # 同期状態を保存
        new_state = {
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
            "failed_ids": new_failed_ids,
        }
        _save_sync_state(new_state)

        logger.info(f"Sync completed: {results}")
        _update_status(
            is_running=False,
            current_table=None,
            results=results,
        )
        return results

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        _update_status(
            is_running=False,
            error=str(e),
        )
        raise


def sync_to_supabase_async(db: Session, force_full: bool = False):
    """
    非同期でSupabaseに同期を実行

    Args:
        db: ローカルDBセッション
        force_full: Trueの場合は全件同期
    """
    from app.db.session import SessionLocal

    def run_sync():
        # 新しいセッションを作成（スレッドセーフ）
        sync_db = SessionLocal()
        try:
            sync_to_supabase(sync_db, force_full=force_full)
        finally:
            sync_db.close()

    thread = threading.Thread(target=run_sync)
    thread.start()
