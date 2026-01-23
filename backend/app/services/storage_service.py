"""
Supabase Storage サービス

モデルファイルのアップロード・ダウンロードを管理
"""
import io
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from supabase import create_client, Client

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Supabase クライアント（遅延初期化）
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """Supabase クライアントを取得"""
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        logger.warning("Supabase credentials not configured")
        return None

    try:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
        logger.info(f"Supabase connected: {settings.SUPABASE_URL[:40]}...")
        return _supabase_client
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        return None


def is_storage_available() -> bool:
    """Supabase Storage が利用可能か確認"""
    client = get_supabase_client()
    if client is None:
        return False

    try:
        # バケットの存在確認
        client.storage.from_(settings.SUPABASE_MODEL_BUCKET).list()
        return True
    except Exception as e:
        logger.warning(f"Storage bucket not available: {e}")
        return False


def upload_model(
    model_data: Dict[str, Any],
    version: str,
    metadata: Optional[Dict] = None,
    race_type: str = "central"
) -> Dict[str, Any]:
    """
    モデルを Supabase Storage にアップロード

    Args:
        model_data: pickle化するモデルデータ
        version: モデルバージョン (例: "v1", "v2")
        metadata: 追加のメタデータ
        race_type: レースタイプ (central/local/banei)

    Returns:
        アップロード結果
    """
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase not configured")

    bucket = settings.SUPABASE_MODEL_BUCKET
    # race_typeに応じたファイル名
    if race_type == "central":
        filename = f"model_{version}.pkl"
    else:
        filename = f"model_{race_type}_{version}.pkl"

    try:
        # モデルをバイト列に変換
        buffer = io.BytesIO()
        pickle.dump(model_data, buffer)
        buffer.seek(0)
        model_bytes = buffer.getvalue()

        # アップロード（既存ファイルは上書き）
        client.storage.from_(bucket).upload(
            filename,
            model_bytes,
            file_options={"content-type": "application/octet-stream", "upsert": "true"}
        )

        logger.info(f"Model uploaded: {filename} ({len(model_bytes)} bytes)")

        # メタデータを別ファイルとして保存
        if metadata:
            if race_type == "central":
                meta_filename = f"model_{version}_meta.json"
            else:
                meta_filename = f"model_{race_type}_{version}_meta.json"
            import json
            meta_bytes = json.dumps(metadata, ensure_ascii=False, default=str).encode()
            client.storage.from_(bucket).upload(
                meta_filename,
                meta_bytes,
                file_options={"content-type": "application/json", "upsert": "true"}
            )

        return {
            "status": "success",
            "filename": filename,
            "size_bytes": len(model_bytes),
            "version": version,
            "uploaded_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to upload model: {e}")
        raise RuntimeError(f"Upload failed: {e}")


def download_model(version: str) -> Optional[Dict[str, Any]]:
    """
    モデルを Supabase Storage からダウンロード

    Args:
        version: モデルバージョン

    Returns:
        モデルデータ（pickle.load済み）
    """
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase not configured")

    bucket = settings.SUPABASE_MODEL_BUCKET
    filename = f"model_{version}.pkl"

    try:
        # ダウンロード
        response = client.storage.from_(bucket).download(filename)

        # バイト列からモデルを復元
        buffer = io.BytesIO(response)
        model_data = pickle.load(buffer)

        logger.info(f"Model downloaded: {filename}")
        return model_data

    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        return None


def list_models() -> List[Dict[str, Any]]:
    """
    保存されているモデル一覧を取得

    Returns:
        モデルファイル情報のリスト
    """
    client = get_supabase_client()
    if client is None:
        return []

    bucket = settings.SUPABASE_MODEL_BUCKET

    try:
        files = client.storage.from_(bucket).list()

        models = []
        for f in files:
            if f["name"].endswith(".pkl"):
                # バージョン抽出 (model_v1.pkl -> v1)
                version = f["name"].replace("model_", "").replace(".pkl", "")
                models.append({
                    "version": version,
                    "filename": f["name"],
                    "size_bytes": f.get("metadata", {}).get("size", 0),
                    "created_at": f.get("created_at"),
                    "updated_at": f.get("updated_at"),
                })

        return sorted(models, key=lambda x: x.get("updated_at", ""), reverse=True)

    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return []


def delete_model(version: str) -> bool:
    """
    モデルを削除

    Args:
        version: 削除するモデルバージョン

    Returns:
        削除成功したか
    """
    client = get_supabase_client()
    if client is None:
        return False

    bucket = settings.SUPABASE_MODEL_BUCKET
    filename = f"model_{version}.pkl"
    meta_filename = f"model_{version}_meta.json"

    try:
        # モデルファイル削除
        client.storage.from_(bucket).remove([filename])

        # メタデータも削除（存在する場合）
        try:
            client.storage.from_(bucket).remove([meta_filename])
        except:
            pass

        logger.info(f"Model deleted: {filename}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete model: {e}")
        return False


def get_model_url(version: str, expires_in: int = 3600) -> Optional[str]:
    """
    モデルの署名付きURLを取得（一時的なダウンロードリンク）

    Args:
        version: モデルバージョン
        expires_in: URL有効期限（秒）

    Returns:
        署名付きURL
    """
    client = get_supabase_client()
    if client is None:
        return None

    bucket = settings.SUPABASE_MODEL_BUCKET
    filename = f"model_{version}.pkl"

    try:
        result = client.storage.from_(bucket).create_signed_url(
            filename,
            expires_in
        )
        return result.get("signedURL")
    except Exception as e:
        logger.error(f"Failed to create signed URL: {e}")
        return None
