"""
モデル管理API

再学習・モデル切り替え・バージョン管理エンドポイント
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.logging_config import get_logger
from app.services import retraining_service, prediction_service

logger = get_logger(__name__)
router = APIRouter()


@router.post("/retrain")
async def retrain_model(
    min_date: Optional[str] = Query(None, description="Minimum date for training data (YYYY-MM-DD)"),
    num_boost_round: int = Query(1000, description="Number of boosting rounds"),
    early_stopping: int = Query(50, description="Early stopping rounds"),
    valid_fraction: float = Query(0.2, description="Validation data fraction"),
):
    """
    モデルの再学習を開始

    バックグラウンドで再学習を実行します。
    進捗は GET /api/v1/model/status で確認できます。
    """
    parsed_date = None
    if min_date:
        try:
            parsed_date = datetime.strptime(min_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    logger.info(f"Starting retraining: min_date={min_date}, boost_round={num_boost_round}")

    result = retraining_service.start_retraining(
        min_date=parsed_date,
        num_boost_round=num_boost_round,
        early_stopping=early_stopping,
        valid_fraction=valid_fraction,
    )

    if result["status"] == "already_running":
        raise HTTPException(
            status_code=409,
            detail=f"Retraining is already running since {result['started_at']}"
        )

    return {
        "status": "success",
        "message": "Retraining started",
        "started_at": result["started_at"],
    }


@router.get("/status")
async def get_retraining_status():
    """
    再学習の状態を取得

    進行中の再学習の進捗や、最後の再学習結果を確認できます。
    """
    status = retraining_service.get_retraining_status()
    return {
        "status": "success",
        "retraining_status": status,
    }


@router.get("/versions")
async def list_model_versions():
    """
    利用可能なモデルバージョン一覧を取得

    保存されている全てのモデルバージョンの情報を返します。
    """
    versions = retraining_service.list_model_versions()
    return {
        "status": "success",
        "count": len(versions),
        "versions": versions,
    }


@router.get("/current")
async def get_current_model():
    """
    現在使用中のモデル情報を取得
    """
    predictor = prediction_service.get_predictor()

    model_info = {
        "version": prediction_service.MODEL_VERSION,
        "is_loaded": predictor.model is not None,
        "num_features": len(predictor.feature_columns) if predictor.feature_columns else 0,
    }

    if predictor.model is not None:
        model_info["best_iteration"] = predictor.model.best_iteration

    return {
        "status": "success",
        "model": model_info,
    }


@router.post("/switch")
async def switch_model(
    version: str = Query(..., description="Model version to switch to"),
):
    """
    使用するモデルを切り替え

    指定したバージョンのモデルに切り替えます。
    現在はランタイム中の切り替えのみで、永続化はされません。
    """
    logger.info(f"Switching model to version: {version}")

    # バージョンの存在確認
    versions = retraining_service.list_model_versions()
    version_exists = any(v["version"] == version for v in versions)

    if not version_exists:
        raise HTTPException(
            status_code=404,
            detail=f"Model version '{version}' not found"
        )

    try:
        # 新しいモデルを読み込み
        from app.services.predictor import HorseRacingPredictor

        new_predictor = HorseRacingPredictor(model_version=version)
        new_predictor.load()

        # グローバルモデルを更新
        prediction_service._predictor = new_predictor
        prediction_service.MODEL_VERSION = version

        logger.info(f"Model switched to version: {version}")

        return {
            "status": "success",
            "message": f"Model switched to version {version}",
            "model": {
                "version": version,
                "num_features": len(new_predictor.feature_columns),
                "best_iteration": new_predictor.model.best_iteration if new_predictor.model else None,
            },
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Model file for version '{version}' not found"
        )
    except Exception as e:
        logger.error(f"Failed to switch model: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to switch model: {str(e)}"
        )


@router.get("/feature-importance")
async def get_feature_importance(
    limit: int = Query(20, description="Number of top features to return"),
):
    """
    特徴量重要度を取得

    現在のモデルの特徴量重要度上位を返します。
    """
    predictor = prediction_service.get_predictor()

    if predictor.model is None:
        raise HTTPException(
            status_code=404,
            detail="No model is loaded"
        )

    try:
        importance = predictor.get_feature_importance()
        top_features = importance.head(limit).to_dict("records")

        return {
            "status": "success",
            "model_version": predictor.model_version,
            "features": top_features,
        }

    except Exception as e:
        logger.error(f"Failed to get feature importance: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
