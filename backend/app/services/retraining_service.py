"""
モデル再学習サービス

APIから呼び出し可能な再学習機能を提供
SSEストリーミング対応
"""
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any
import threading
import queue
import json

from sqlalchemy.orm import Session

from app.logging_config import get_logger
from app.db.base import SessionLocal
from app.services.predictor import prepare_training_data, prepare_time_split_data, HorseRacingPredictor
from app.services.predictor.model import MODEL_DIR

logger = get_logger(__name__)

# 再学習状態を管理
_retraining_status = {
    "is_running": False,
    "started_at": None,
    "progress": None,
    "last_result": None,
}
_lock = threading.Lock()

# SSE用の進捗イベントキュー（複数クライアント対応）
_progress_queues: List[queue.Queue] = []
_queues_lock = threading.Lock()


def register_progress_listener() -> queue.Queue:
    """進捗リスナーを登録"""
    q = queue.Queue()
    with _queues_lock:
        _progress_queues.append(q)
    return q


def unregister_progress_listener(q: queue.Queue):
    """進捗リスナーを解除"""
    with _queues_lock:
        if q in _progress_queues:
            _progress_queues.remove(q)


def emit_progress(event_type: str, data: Dict[str, Any]):
    """進捗イベントを発行"""
    event = {
        "type": event_type,
        "timestamp": datetime.now().isoformat(),
        **data,
    }
    with _queues_lock:
        for q in _progress_queues:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass  # キューがいっぱいの場合はスキップ


class RetrainingResult:
    """再学習結果"""

    def __init__(self):
        self.success = False
        self.model_version: Optional[str] = None
        self.model_path: Optional[str] = None
        self.train_rmse: Optional[float] = None
        self.valid_rmse: Optional[float] = None
        self.num_samples: int = 0
        self.num_features: int = 0
        self.error: Optional[str] = None
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "model_version": self.model_version,
            "model_path": self.model_path,
            "train_rmse": self.train_rmse,
            "valid_rmse": self.valid_rmse,
            "num_samples": self.num_samples,
            "num_features": self.num_features,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


def get_retraining_status() -> dict:
    """再学習の現在の状態を取得"""
    with _lock:
        return {
            "is_running": _retraining_status["is_running"],
            "started_at": (
                _retraining_status["started_at"].isoformat()
                if _retraining_status["started_at"]
                else None
            ),
            "progress": _retraining_status["progress"],
            "last_result": (
                _retraining_status["last_result"].to_dict()
                if _retraining_status["last_result"]
                else None
            ),
        }


def start_retraining(
    min_date: Optional[date] = None,
    num_boost_round: int = 1000,
    early_stopping: int = 50,
    valid_fraction: float = 0.2,
    # 時系列分割モード用パラメータ
    use_time_split: bool = False,
    train_end_date: Optional[date] = None,
    valid_end_date: Optional[date] = None,
    # クラウドアップロード用パラメータ
    upload_after_training: bool = False,
    upload_version: Optional[str] = None,
    upload_description: Optional[str] = None,
) -> dict:
    """
    再学習を開始する

    Args:
        min_date: 学習データの最小日付（従来モード）
        num_boost_round: ブースティング回数
        early_stopping: 早期停止回数
        valid_fraction: 検証データの割合（従来モード）
        use_time_split: 時系列分割モードを使用するか
        train_end_date: 学習データの終了日（時系列分割モード）
        valid_end_date: 検証データの終了日（時系列分割モード）
        upload_after_training: 学習完了後にクラウドにアップロードするか
        upload_version: アップロード時のバージョン名
        upload_description: アップロード時の説明

    Returns:
        開始状態
    """
    with _lock:
        if _retraining_status["is_running"]:
            return {
                "status": "already_running",
                "started_at": _retraining_status["started_at"].isoformat(),
            }

        _retraining_status["is_running"] = True
        _retraining_status["started_at"] = datetime.now()
        _retraining_status["progress"] = "starting"

    # バックグラウンドで再学習を実行
    thread = threading.Thread(
        target=_run_retraining,
        args=(min_date, num_boost_round, early_stopping, valid_fraction,
              use_time_split, train_end_date, valid_end_date,
              upload_after_training, upload_version, upload_description),
        daemon=True,
    )
    thread.start()

    return {
        "status": "started",
        "started_at": _retraining_status["started_at"].isoformat(),
    }


def _run_retraining(
    min_date: Optional[date],
    num_boost_round: int,
    early_stopping: int,
    valid_fraction: float,
    use_time_split: bool = False,
    train_end_date: Optional[date] = None,
    valid_end_date: Optional[date] = None,
    upload_after_training: bool = False,
    upload_version: Optional[str] = None,
    upload_description: Optional[str] = None,
) -> None:
    """バックグラウンドで再学習を実行"""
    result = RetrainingResult()
    result.started_at = datetime.now()

    db = SessionLocal()

    try:
        # ステップ1: データ準備開始
        with _lock:
            _retraining_status["progress"] = "preparing_data"
        emit_progress("step", {
            "step": "preparing_data",
            "message": "学習データを準備中...",
            "progress_percent": 5,
        })

        logger.info("Starting model retraining...")

        # 日付ベースのバージョンを生成
        version = upload_version or datetime.now().strftime("v%Y%m%d_%H%M%S")
        result.model_version = version

        emit_progress("info", {
            "message": f"モデルバージョン: {version}",
        })

        predictor = HorseRacingPredictor(model_version=version)

        if use_time_split and train_end_date and valid_end_date:
            # 時系列分割モード
            logger.info(f"Using time-split mode: train_end={train_end_date}, valid_end={valid_end_date}")
            emit_progress("info", {
                "message": f"時系列分割モード: 学習〜{train_end_date}, 検証〜{valid_end_date}",
            })

            data = prepare_time_split_data(
                db,
                train_end_date=train_end_date,
                valid_end_date=valid_end_date,
                train_start_date=min_date,
            )

            X_train, y_train = data['train']
            X_valid, y_valid = data['valid']

            if X_train.empty:
                raise ValueError("No training data found")
            if X_valid.empty:
                raise ValueError("No validation data found")

            result.num_samples = len(X_train) + len(X_valid)
            result.num_features = len(X_train.columns)

            emit_progress("step", {
                "step": "data_ready",
                "message": f"データ準備完了: 学習{len(X_train)}件, 検証{len(X_valid)}件",
                "progress_percent": 15,
                "num_train_samples": len(X_train),
                "num_valid_samples": len(X_valid),
                "num_features": result.num_features,
            })

            logger.info(f"Train: {len(X_train)} samples, Valid: {len(X_valid)} samples, Test: {data['counts']['test']} samples")

            with _lock:
                _retraining_status["progress"] = "training"

            # ステップ2: 学習開始
            emit_progress("step", {
                "step": "training",
                "message": "モデルを学習中...",
                "progress_percent": 20,
            })

            # 時系列分割モードで学習
            logger.info("Training model with time-split data...")
            train_result = predictor.train_with_validation(
                X_train,
                y_train,
                X_valid,
                y_valid,
                num_boost_round=num_boost_round,
                early_stopping_rounds=early_stopping,
            )
        else:
            # 従来モード
            logger.info("Using legacy mode (fraction-based split)")
            emit_progress("info", {
                "message": "従来モード（ランダム分割）",
            })

            X, y = prepare_training_data(db, min_date=min_date)

            if X.empty:
                raise ValueError("No training data found")

            result.num_samples = len(X)
            result.num_features = len(X.columns)

            emit_progress("step", {
                "step": "data_ready",
                "message": f"データ準備完了: {result.num_samples}件, {result.num_features}特徴量",
                "progress_percent": 15,
                "num_samples": result.num_samples,
                "num_features": result.num_features,
            })

            logger.info(f"Training data: {result.num_samples} samples, {result.num_features} features")

            with _lock:
                _retraining_status["progress"] = "training"

            # ステップ2: 学習開始
            emit_progress("step", {
                "step": "training",
                "message": "モデルを学習中...",
                "progress_percent": 20,
            })

            # 従来モードで学習
            logger.info("Training model...")
            train_result = predictor.train(
                X,
                y,
                num_boost_round=num_boost_round,
                early_stopping_rounds=early_stopping,
                valid_fraction=valid_fraction,
            )

        result.train_rmse = train_result["train_rmse"]
        result.valid_rmse = train_result["valid_rmse"]

        # ステップ3: 学習完了
        emit_progress("step", {
            "step": "training_done",
            "message": f"学習完了: Train RMSE={result.train_rmse:.4f}, Valid RMSE={result.valid_rmse:.4f}",
            "progress_percent": 70,
            "train_rmse": result.train_rmse,
            "valid_rmse": result.valid_rmse,
            "best_iteration": train_result.get("best_iteration"),
        })

        logger.info(f"Training completed: train_rmse={result.train_rmse:.4f}, valid_rmse={result.valid_rmse:.4f}")

        with _lock:
            _retraining_status["progress"] = "saving"

        # ステップ4: モデル保存
        emit_progress("step", {
            "step": "saving",
            "message": "モデルをローカルに保存中...",
            "progress_percent": 80,
        })

        logger.info("Saving model...")
        model_path = predictor.save()
        result.model_path = str(model_path)
        logger.info(f"Model saved to {model_path}")

        emit_progress("info", {
            "message": f"ローカル保存完了: {model_path}",
        })

        # クラウドへのアップロード
        if upload_after_training:
            with _lock:
                _retraining_status["progress"] = "uploading_to_cloud"

            # ステップ5: クラウドアップロード
            emit_progress("step", {
                "step": "uploading",
                "message": "Supabase Storageにアップロード中...",
                "progress_percent": 90,
            })

            logger.info(f"Uploading model to cloud storage: {version}")
            try:
                from app.services import storage_service

                if storage_service.is_storage_available():
                    # モデルデータを準備
                    model_data = {
                        "model": predictor.model,
                        "scaler": predictor.scaler,
                        "calibrator": predictor.calibrator,
                        "feature_columns": predictor.feature_columns,
                        "model_version": version,
                    }

                    # メタデータ
                    metadata = {
                        "version": version,
                        "description": upload_description,
                        "num_features": result.num_features,
                        "num_samples": result.num_samples,
                        "train_rmse": result.train_rmse,
                        "valid_rmse": result.valid_rmse,
                        "best_iteration": predictor.model.best_iteration if predictor.model else None,
                        "uploaded_from": "fastapi_local",
                        "trained_at": result.started_at.isoformat() if result.started_at else None,
                    }

                    upload_result = storage_service.upload_model(model_data, version, metadata)
                    logger.info(f"Model uploaded to cloud: {upload_result}")

                    emit_progress("info", {
                        "message": f"クラウドアップロード完了: {version}",
                    })
                else:
                    logger.warning("Supabase Storage is not available, skipping upload")
                    emit_progress("warning", {
                        "message": "Supabase Storageが利用不可のためスキップ",
                    })
            except Exception as upload_error:
                logger.error(f"Failed to upload model to cloud: {upload_error}")
                emit_progress("warning", {
                    "message": f"アップロード失敗: {upload_error}",
                })
                # アップロード失敗は学習成功に影響しない

        result.success = True
        result.completed_at = datetime.now()

        with _lock:
            _retraining_status["progress"] = "completed"
            _retraining_status["last_result"] = result

        # ステップ6: 完了
        emit_progress("complete", {
            "step": "completed",
            "message": "再学習が正常に完了しました",
            "progress_percent": 100,
            "version": version,
            "train_rmse": result.train_rmse,
            "valid_rmse": result.valid_rmse,
            "num_samples": result.num_samples,
            "num_features": result.num_features,
        })

        logger.info(f"Retraining completed successfully: {version}")

    except Exception as e:
        logger.error(f"Retraining failed: {e}")
        result.error = str(e)
        result.completed_at = datetime.now()

        with _lock:
            _retraining_status["progress"] = "failed"
            _retraining_status["last_result"] = result

        # エラーイベントを発行
        emit_progress("error", {
            "step": "failed",
            "message": f"再学習に失敗しました: {e}",
            "progress_percent": 0,
            "error": str(e),
        })

    finally:
        db.close()
        with _lock:
            _retraining_status["is_running"] = False


def list_model_versions() -> list[dict]:
    """
    利用可能なモデルバージョン一覧を取得

    Returns:
        モデル情報のリスト
    """
    models = []

    if not MODEL_DIR.exists():
        return models

    for model_file in MODEL_DIR.glob("model_*.pkl"):
        version = model_file.stem.replace("model_", "")
        stat = model_file.stat()
        models.append({
            "version": version,
            "file_path": str(model_file),
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })

    # 作成日時でソート（新しい順）
    models.sort(key=lambda x: x["created_at"], reverse=True)
    return models


def get_latest_model_version() -> Optional[str]:
    """最新のモデルバージョンを取得"""
    models = list_model_versions()
    if models:
        return models[0]["version"]
    return None
