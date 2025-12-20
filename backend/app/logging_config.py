"""
ログ設定モジュール

JSON形式のログ出力とローテーションを設定
"""
import logging
import logging.handlers
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings


class JSONFormatter(logging.Formatter):
    """JSON形式でログを出力するフォーマッター"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> None:
    """ログ設定を初期化する"""
    # ログディレクトリの作成
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    # ルートロガーの設定
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)

    # 既存のハンドラをクリア
    root_logger.handlers.clear()

    # コンソールハンドラ
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.LOG_LEVEL)

    if settings.LOG_FORMAT == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    root_logger.addHandler(console_handler)

    # ファイルハンドラ（ローテーション付き）
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=settings.LOG_MAX_BYTES,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(settings.LOG_LEVEL)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # uvicornのログレベルを調整
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # SQLAlchemyのログを抑制
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """名前付きロガーを取得する"""
    return logging.getLogger(name)
