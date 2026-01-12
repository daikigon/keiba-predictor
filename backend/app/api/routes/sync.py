"""
Supabase Sync API

ローカルDBからSupabaseへのデータ同期エンドポイント
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.logging_config import get_logger
from app.services import sync_service

logger = get_logger(__name__)
router = APIRouter()


@router.post("/to-supabase")
async def start_sync_to_supabase(
    force_full: bool = Query(False, description="全件同期を強制する場合はTrue"),
    db: Session = Depends(get_db),
):
    """
    ローカルDBのデータをSupabaseに同期（非同期実行・差分同期）

    デフォルトでは前回同期以降に更新されたレコードと、
    前回失敗したレコードのみを同期します。
    force_full=True で全件同期を実行します。
    """
    status = sync_service.get_sync_status()
    if status["is_running"]:
        raise HTTPException(status_code=409, detail="同期が既に実行中です")

    try:
        sync_service.sync_to_supabase_async(db, force_full=force_full)
        return {
            "status": "started",
            "message": "全件同期を開始しました" if force_full else "差分同期を開始しました",
            "mode": "full" if force_full else "diff",
        }
    except Exception as e:
        logger.error(f"Failed to start sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_sync_status():
    """
    同期状態を取得

    Returns:
        - is_running: 実行中かどうか
        - progress: 進行状況（処理済みレコード数）
        - total: 総レコード数
        - current_table: 現在処理中のテーブル名
        - results: 完了時の結果（各テーブルの同期数・エラー数）
        - error: エラーメッセージ（失敗時）
    """
    return sync_service.get_sync_status()
