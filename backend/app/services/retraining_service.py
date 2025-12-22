"""
モデル再学習サービス

APIから呼び出し可能な再学習機能を提供
"""
from datetime import datetime, date
from pathlib import Path
from typing import Optional
import threading

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
              use_time_split, train_end_date, valid_end_date),
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
) -> None:
    """バックグラウンドで再学習を実行"""
    result = RetrainingResult()
    result.started_at = datetime.now()

    db = SessionLocal()

    try:
        with _lock:
            _retraining_status["progress"] = "preparing_data"

        logger.info("Starting model retraining...")

        # 日付ベースのバージョンを生成
        version = datetime.now().strftime("v%Y%m%d_%H%M%S")
        result.model_version = version

        predictor = HorseRacingPredictor(model_version=version)

        if use_time_split and train_end_date and valid_end_date:
            # 時系列分割モード
            logger.info(f"Using time-split mode: train_end={train_end_date}, valid_end={valid_end_date}")
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
            logger.info(f"Train: {len(X_train)} samples, Valid: {len(X_valid)} samples, Test: {data['counts']['test']} samples")

            with _lock:
                _retraining_status["progress"] = "training"

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
            X, y = prepare_training_data(db, min_date=min_date)

            if X.empty:
                raise ValueError("No training data found")

            result.num_samples = len(X)
            result.num_features = len(X.columns)
            logger.info(f"Training data: {result.num_samples} samples, {result.num_features} features")

            with _lock:
                _retraining_status["progress"] = "training"

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
        logger.info(f"Training completed: train_rmse={result.train_rmse:.4f}, valid_rmse={result.valid_rmse:.4f}")

        with _lock:
            _retraining_status["progress"] = "saving"

        # モデル保存
        logger.info("Saving model...")
        model_path = predictor.save()
        result.model_path = str(model_path)
        logger.info(f"Model saved to {model_path}")

        result.success = True
        result.completed_at = datetime.now()

        with _lock:
            _retraining_status["progress"] = "completed"
            _retraining_status["last_result"] = result

        logger.info(f"Retraining completed successfully: {version}")

    except Exception as e:
        logger.error(f"Retraining failed: {e}")
        result.error = str(e)
        result.completed_at = datetime.now()

        with _lock:
            _retraining_status["progress"] = "failed"
            _retraining_status["last_result"] = result

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
