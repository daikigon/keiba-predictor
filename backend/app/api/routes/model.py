"""
モデル管理API

再学習・モデル切り替え・バージョン管理・シミュレーションエンドポイント
SSEストリーミング対応
"""
import asyncio
import json
from datetime import datetime
from itertools import combinations
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.logging_config import get_logger
from app.models import Race, Entry
from app.services import retraining_service, prediction_service
from app.services.predictor import FeatureExtractor, get_model

logger = get_logger(__name__)
router = APIRouter()

# シミュレーション状態管理
_simulation_status = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "results": None,
    "error": None,
}


class RetrainParams(BaseModel):
    """再学習パラメータ"""
    num_boost_round: int = 3000
    early_stopping: int = 100
    # 従来モード用
    min_date: Optional[str] = None
    valid_fraction: float = 0.2
    # 時系列分割モード用（推奨）
    use_time_split: bool = True  # デフォルトで時系列分割を使用
    train_end_date: Optional[str] = None
    valid_end_date: Optional[str] = None


@router.post("/retrain")
async def retrain_model(params: RetrainParams):
    """
    モデルの再学習を開始

    バックグラウンドで再学習を実行します。
    進捗は GET /api/v1/model/status で確認できます。

    ## モード

    ### 従来モード（デフォルト）
    - `min_date`: 学習データの開始日
    - `valid_fraction`: 検証データの割合（末尾からの割合）

    ### 時系列分割モード（推奨）
    - `use_time_split`: true に設定
    - `train_end_date`: 学習データの終了日
    - `valid_end_date`: 検証データの終了日（これ以降がテストデータ）
    """

    def parse_date(date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD")

    parsed_min_date = parse_date(params.min_date)
    parsed_train_end = parse_date(params.train_end_date)
    parsed_valid_end = parse_date(params.valid_end_date)

    # 時系列分割モードのバリデーション
    if params.use_time_split:
        if not parsed_train_end or not parsed_valid_end:
            raise HTTPException(
                status_code=400,
                detail="Time-split mode requires train_end_date and valid_end_date"
            )
        if parsed_train_end >= parsed_valid_end:
            raise HTTPException(
                status_code=400,
                detail="train_end_date must be before valid_end_date"
            )

    logger.info(f"Starting retraining: use_time_split={params.use_time_split}, "
                f"train_end={params.train_end_date}, valid_end={params.valid_end_date}")

    result = retraining_service.start_retraining(
        min_date=parsed_min_date,
        num_boost_round=params.num_boost_round,
        early_stopping=params.early_stopping,
        valid_fraction=params.valid_fraction,
        use_time_split=params.use_time_split,
        train_end_date=parsed_train_end,
        valid_end_date=parsed_valid_end,
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


@router.get("/status/stream")
async def stream_retraining_status():
    """
    再学習の進捗をSSEでストリーミング

    リアルタイムで学習の進捗状況を受け取れます。
    学習完了またはエラー時に接続が終了します。

    ## 使用例（JavaScript）
    ```javascript
    const eventSource = new EventSource('/api/v1/model/status/stream');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log(data.message, data.progress_percent + '%');
    };
    ```
    """
    async def event_generator():
        # リスナーを登録
        progress_queue = retraining_service.register_progress_listener()

        try:
            # 初期状態を送信
            status = retraining_service.get_retraining_status()
            yield f"data: {json.dumps({'type': 'connected', 'is_running': status['is_running']})}\n\n"

            # イベントを待機してストリーミング
            while True:
                try:
                    # 非同期でキューからイベントを取得（1秒タイムアウト）
                    event = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: progress_queue.get(timeout=1.0)
                    )

                    # イベントをSSE形式で送信
                    yield f"data: {json.dumps(event)}\n\n"

                    # 完了またはエラーの場合は終了
                    if event.get("type") in ("complete", "error"):
                        break

                except Exception:
                    # タイムアウト時はハートビートを送信
                    status = retraining_service.get_retraining_status()
                    if not status["is_running"]:
                        # 学習が終了している場合は接続終了
                        yield f"data: {json.dumps({'type': 'idle', 'message': '学習は実行されていません'})}\n\n"
                        break
                    else:
                        # ハートビート
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

        finally:
            # リスナーを解除
            retraining_service.unregister_progress_listener(progress_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


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


# ================== シミュレーション関連 ==================

class SimulationParams(BaseModel):
    """シミュレーションパラメータ"""
    ev_threshold: float = 1.0
    umaren_ev_threshold: float = 1.2
    # 期待値上限（高すぎる穴馬を除外）
    max_ev: float = 2.0  # 単勝の期待値上限
    umaren_max_ev: float = 5.0  # 馬連の期待値上限
    bet_type: str = "all"  # "tansho", "umaren", or "all"
    bet_amount: int = 100
    limit: int = 200
    # 期間指定（テストデータのみでシミュレーションする場合）
    start_date: Optional[str] = None  # YYYY-MM-DD形式
    end_date: Optional[str] = None  # YYYY-MM-DD形式
    # 最低確率フィルター（これ以下の確率の馬には賭けない）
    min_probability: float = 0.01  # デフォルト1%（PDF推奨値）
    # 馬連の組み合わせ対象馬数
    umaren_top_n: int = 3  # 上位3頭（PDF推奨: 組み合わせ爆発防止）


def _calculate_umaren_prob(probabilities: dict, h1: int, h2: int, n_horses: int) -> float:
    """
    馬連の的中確率を計算

    より現実的な近似式:
    - P(馬連) ≈ P(h1が1着)×P(h2が2着|h1が1着) + P(h2が1着)×P(h1が2着|h2が1着)
    - 近似: P(2着|他馬1着) ≈ P(勝ち) / (1 - P(他馬勝ち))
    """
    p1 = probabilities.get(h1, 0)
    p2 = probabilities.get(h2, 0)
    if p1 == 0 or p2 == 0:
        return 0.0

    # h1が1着でh2が2着の確率
    p1_wins_p2_second = p1 * (p2 / (1 - p1)) if p1 < 1 else 0
    # h2が1着でh1が2着の確率
    p2_wins_p1_second = p2 * (p1 / (1 - p2)) if p2 < 1 else 0

    umaren_prob = p1_wins_p2_second + p2_wins_p1_second
    return min(umaren_prob, 1.0)


def _run_simulation(
    db: Session,
    params: SimulationParams,
):
    """バックグラウンドでシミュレーションを実行"""
    global _simulation_status

    try:
        _simulation_status["is_running"] = True
        _simulation_status["progress"] = 0
        _simulation_status["error"] = None

        # 現在アクティブなモデルを使用
        predictor = prediction_service.get_predictor()
        if predictor.model is None:
            _simulation_status["error"] = "モデルが読み込まれていません"
            _simulation_status["is_running"] = False
            return

        logger.info(f"Simulation using model version: {predictor.model_version}")
        logger.info(f"Simulation params: start_date={params.start_date}, end_date={params.end_date}, limit={params.limit}")

        # レース取得（期間フィルタ適用）
        stmt = (
            select(Race)
            .where(Race.entries.any(Entry.result.isnot(None)))
        )

        # 期間フィルタ
        if params.start_date:
            try:
                start = datetime.strptime(params.start_date, "%Y-%m-%d").date()
                stmt = stmt.where(Race.date >= start)
            except ValueError:
                pass

        if params.end_date:
            try:
                end = datetime.strptime(params.end_date, "%Y-%m-%d").date()
                stmt = stmt.where(Race.date <= end)
            except ValueError:
                pass

        stmt = stmt.order_by(Race.date.desc()).limit(params.limit)
        races = list(db.execute(stmt).scalars().all())
        _simulation_status["total"] = len(races)
        logger.info(f"Simulation: Retrieved {len(races)} races (limit={params.limit})")

        extractor = FeatureExtractor(db)
        all_results = []
        total_bet = 0
        total_payout = 0
        tansho_bets = []
        umaren_bets = []

        for i, race in enumerate(races):
            _simulation_status["progress"] = i + 1

            # 特徴量抽出
            df = extractor.extract_race_features(race)
            if df.empty:
                continue

            # 実際の着順とオッズを取得
            actual_results = {}
            odds_data = {}
            for entry in race.entries:
                if entry.result:
                    actual_results[entry.horse_number] = entry.result
                if entry.odds:
                    odds_data[entry.horse_number] = entry.odds

            if not actual_results or not odds_data:
                continue

            # 予測（正規化済み確率を使用）
            try:
                probabilities_arr = predictor.predict_proba(df)
            except RuntimeError:
                continue

            df["probability"] = probabilities_arr
            df["pred_rank"] = (-probabilities_arr).argsort().argsort() + 1

            probabilities = dict(zip(df["horse_number"].astype(int), df["probability"]))

            # 単勝シミュレーション
            if params.bet_type in ("tansho", "all"):
                for _, row in df.iterrows():
                    horse_num = int(row["horse_number"])
                    prob = row["probability"]
                    odds = odds_data.get(horse_num, 0)

                    if odds <= 0:
                        continue

                    # 最低確率フィルター（穴馬を除外）
                    if prob < params.min_probability:
                        continue

                    ev = prob * odds

                    # 期待値の下限・上限チェック
                    if ev >= params.ev_threshold and ev <= params.max_ev:
                        actual_rank = actual_results.get(horse_num, 999)
                        is_hit = actual_rank == 1
                        payout = int(odds * params.bet_amount) if is_hit else 0

                        tansho_bets.append({
                            "horse_number": horse_num,
                            "ev": round(ev, 3),
                            "odds": odds,
                            "is_hit": is_hit,
                            "payout": payout,
                        })
                        total_bet += params.bet_amount
                        total_payout += payout

            # 馬連シミュレーション
            if params.bet_type in ("umaren", "all"):
                # 最低確率を満たす馬のみ対象、上位N頭に制限
                eligible_horses = df[df["probability"] >= params.min_probability]
                top_n = eligible_horses.nsmallest(params.umaren_top_n, "pred_rank")

                for (_, h1), (_, h2) in combinations(top_n.iterrows(), 2):
                    num1, num2 = int(h1["horse_number"]), int(h2["horse_number"])

                    umaren_prob = _calculate_umaren_prob(probabilities, num1, num2, len(df))

                    o1 = odds_data.get(num1, 10)
                    o2 = odds_data.get(num2, 10)
                    estimated_odds = (o1 * o2) / 3

                    ev = umaren_prob * estimated_odds

                    # 期待値の下限・上限チェック
                    if ev >= params.umaren_ev_threshold and ev <= params.umaren_max_ev:
                        r1 = actual_results.get(num1, 999)
                        r2 = actual_results.get(num2, 999)
                        is_hit = (r1 <= 2 and r2 <= 2)
                        payout = int(estimated_odds * params.bet_amount) if is_hit else 0

                        umaren_bets.append({
                            "combination": f"{min(num1,num2)}-{max(num1,num2)}",
                            "ev": round(ev, 3),
                            "odds": round(estimated_odds, 1),
                            "is_hit": is_hit,
                            "payout": payout,
                        })
                        total_bet += params.bet_amount
                        total_payout += payout

        # 結果集計
        total_bets_count = len(tansho_bets) + len(umaren_bets)
        total_hits = sum(1 for b in tansho_bets if b["is_hit"]) + sum(1 for b in umaren_bets if b["is_hit"])
        roi = ((total_payout / total_bet) - 1) * 100 if total_bet > 0 else 0
        hit_rate = (total_hits / total_bets_count) * 100 if total_bets_count > 0 else 0

        _simulation_status["results"] = {
            "total_races": len(races),
            "total_bets": total_bets_count,
            "total_hits": total_hits,
            "hit_rate": round(hit_rate, 1),
            "total_bet_amount": total_bet,
            "total_payout": total_payout,
            "profit": total_payout - total_bet,
            "return_rate": round(100 * total_payout / total_bet, 1) if total_bet > 0 else 0,
            "roi": round(roi, 1),
            "tansho": {
                "count": len(tansho_bets),
                "hits": sum(1 for b in tansho_bets if b["is_hit"]),
                "hit_rate": round(100 * sum(1 for b in tansho_bets if b["is_hit"]) / len(tansho_bets), 1) if tansho_bets else 0,
                "bet_amount": len(tansho_bets) * params.bet_amount,
                "payout": sum(b["payout"] for b in tansho_bets),
                "return_rate": round(100 * sum(b["payout"] for b in tansho_bets) / (len(tansho_bets) * params.bet_amount), 1) if tansho_bets else 0,
            },
            "umaren": {
                "count": len(umaren_bets),
                "hits": sum(1 for b in umaren_bets if b["is_hit"]),
                "hit_rate": round(100 * sum(1 for b in umaren_bets if b["is_hit"]) / len(umaren_bets), 1) if umaren_bets else 0,
                "bet_amount": len(umaren_bets) * params.bet_amount,
                "payout": sum(b["payout"] for b in umaren_bets),
                "return_rate": round(100 * sum(b["payout"] for b in umaren_bets) / (len(umaren_bets) * params.bet_amount), 1) if umaren_bets else 0,
            },
            "params": {
                "ev_threshold": params.ev_threshold,
                "max_ev": params.max_ev,
                "umaren_ev_threshold": params.umaren_ev_threshold,
                "umaren_max_ev": params.umaren_max_ev,
                "min_probability": params.min_probability,
                "umaren_top_n": params.umaren_top_n,
                "bet_type": params.bet_type,
                "bet_amount": params.bet_amount,
            },
        }

    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        _simulation_status["error"] = str(e)
    finally:
        _simulation_status["is_running"] = False


@router.post("/simulate")
async def start_simulation(
    background_tasks: BackgroundTasks,
    params: SimulationParams,
    db: Session = Depends(get_db),
):
    """
    期待値ベースのシミュレーションを開始

    バックグラウンドで実行され、結果は /api/v1/model/simulate/status で確認できます。
    """
    global _simulation_status

    if _simulation_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="シミュレーションは既に実行中です"
        )

    # バックグラウンドで実行
    background_tasks.add_task(_run_simulation, db, params)

    return {
        "status": "success",
        "message": "シミュレーションを開始しました",
    }


@router.get("/simulate/status")
async def get_simulation_status():
    """
    シミュレーションの状態と結果を取得
    """
    return {
        "status": "success",
        "simulation": _simulation_status,
    }


@router.post("/simulate/sync")
async def run_simulation_sync(
    params: SimulationParams,
    db: Session = Depends(get_db),
):
    """
    シミュレーションを同期実行（小規模データ用）

    結果が即座に返されます。大規模データの場合は /simulate を使用してください。
    """
    global _simulation_status

    if _simulation_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="シミュレーションは既に実行中です"
        )

    # 同期実行
    _run_simulation(db, params)

    if _simulation_status["error"]:
        raise HTTPException(
            status_code=500,
            detail=_simulation_status["error"]
        )

    return {
        "status": "success",
        "results": _simulation_status["results"],
    }


# ================== 閾値スイープ分析 ==================

# 閾値スイープ状態管理
_sweep_status = {
    "is_running": False,
    "phase": "idle",  # "idle", "preparing", "sweeping", "complete"
    "progress": 0,
    "total": 0,
    "current_threshold": 0,
    "total_thresholds": 0,
    "results": None,
    "error": None,
}


class ThresholdSweepParams(BaseModel):
    """閾値スイープ分析パラメータ"""
    bet_type: str = "tansho"  # "tansho" or "umaren"
    ev_min: float = 0.8
    ev_max: float = 2.0
    ev_step: float = 0.05
    max_ev: float = 10.0  # 期待値上限（スイープ中は固定）
    min_probability: float = 0.01
    umaren_top_n: int = 3
    bet_amount: int = 100
    limit: int = 500
    start_date: Optional[str] = None
    end_date: Optional[str] = None


def _run_threshold_sweep_async(
    db: Session,
    params: ThresholdSweepParams,
):
    """バックグラウンドで閾値スイープを実行"""
    global _sweep_status

    try:
        _sweep_status["is_running"] = True
        _sweep_status["phase"] = "preparing"
        _sweep_status["error"] = None
        _sweep_status["results"] = None

        results = _run_threshold_sweep(db, params)

        _sweep_status["results"] = {
            "bet_type": params.bet_type,
            "total_races": params.limit,
            "data": results,
        }
        _sweep_status["phase"] = "complete"

    except Exception as e:
        logger.error(f"Threshold sweep failed: {e}")
        _sweep_status["error"] = str(e)
        _sweep_status["phase"] = "error"
    finally:
        _sweep_status["is_running"] = False


def _run_threshold_sweep(
    db: Session,
    params: ThresholdSweepParams,
) -> list[dict]:
    """
    閾値を変化させながらシミュレーションを実行し、
    各閾値での回収率・シャープレシオを計算
    """
    global _sweep_status

    predictor = prediction_service.get_predictor()
    if predictor.model is None:
        raise ValueError("モデルが読み込まれていません")

    # レース取得
    stmt = (
        select(Race)
        .where(Race.entries.any(Entry.result.isnot(None)))
    )

    if params.start_date:
        try:
            start = datetime.strptime(params.start_date, "%Y-%m-%d").date()
            stmt = stmt.where(Race.date >= start)
        except ValueError:
            pass

    if params.end_date:
        try:
            end = datetime.strptime(params.end_date, "%Y-%m-%d").date()
            stmt = stmt.where(Race.date <= end)
        except ValueError:
            pass

    stmt = stmt.order_by(Race.date.desc()).limit(params.limit)
    races = list(db.execute(stmt).scalars().all())

    if not races:
        return []

    extractor = FeatureExtractor(db)

    # 進捗: データ準備フェーズ
    _sweep_status["phase"] = "preparing"
    _sweep_status["total"] = len(races)
    _sweep_status["progress"] = 0

    # 全レースの予測と実績を事前計算
    race_data = []
    for i, race in enumerate(races):
        _sweep_status["progress"] = i + 1

        df = extractor.extract_race_features(race)
        if df.empty:
            continue

        actual_results = {}
        odds_data = {}
        for entry in race.entries:
            if entry.result:
                actual_results[entry.horse_number] = entry.result
            if entry.odds:
                odds_data[entry.horse_number] = entry.odds

        if not actual_results or not odds_data:
            continue

        try:
            probabilities_arr = predictor.predict_proba(df)
        except RuntimeError:
            continue

        df["probability"] = probabilities_arr
        df["pred_rank"] = (-probabilities_arr).argsort().argsort() + 1
        probabilities = dict(zip(df["horse_number"].astype(int), df["probability"]))

        race_data.append({
            "df": df,
            "actual_results": actual_results,
            "odds_data": odds_data,
            "probabilities": probabilities,
        })

    # 進捗: 閾値スイープフェーズ
    _sweep_status["phase"] = "sweeping"
    total_thresholds = int((params.ev_max - params.ev_min) / params.ev_step) + 1
    _sweep_status["total_thresholds"] = total_thresholds
    _sweep_status["current_threshold"] = 0

    # 閾値スイープ
    results = []
    ev_threshold = params.ev_min
    threshold_idx = 0

    while ev_threshold <= params.ev_max + 0.001:
        _sweep_status["current_threshold"] = threshold_idx + 1
        threshold_idx += 1
        returns = []  # 各賭けのリターン率（シャープレシオ計算用）

        total_bet = 0
        total_payout = 0
        bet_count = 0
        hit_count = 0

        for rd in race_data:
            df = rd["df"]
            actual_results = rd["actual_results"]
            odds_data = rd["odds_data"]
            probabilities = rd["probabilities"]

            if params.bet_type == "tansho":
                # 単勝シミュレーション
                for _, row in df.iterrows():
                    horse_num = int(row["horse_number"])
                    prob = row["probability"]
                    odds = odds_data.get(horse_num, 0)

                    if odds <= 0 or prob < params.min_probability:
                        continue

                    ev = prob * odds
                    if ev >= ev_threshold and ev <= params.max_ev:
                        actual_rank = actual_results.get(horse_num, 999)
                        is_hit = actual_rank == 1
                        payout = int(odds * params.bet_amount) if is_hit else 0

                        total_bet += params.bet_amount
                        total_payout += payout
                        bet_count += 1
                        if is_hit:
                            hit_count += 1

                        # リターン率を記録（シャープレシオ用）
                        ret = (payout - params.bet_amount) / params.bet_amount
                        returns.append(ret)

            else:  # umaren
                # 馬連シミュレーション
                eligible_horses = df[df["probability"] >= params.min_probability]
                top_n = eligible_horses.nsmallest(params.umaren_top_n, "pred_rank")

                for (_, h1), (_, h2) in combinations(top_n.iterrows(), 2):
                    num1, num2 = int(h1["horse_number"]), int(h2["horse_number"])

                    umaren_prob = _calculate_umaren_prob(probabilities, num1, num2, len(df))

                    o1 = odds_data.get(num1, 10)
                    o2 = odds_data.get(num2, 10)
                    estimated_odds = (o1 * o2) / 3

                    ev = umaren_prob * estimated_odds

                    if ev >= ev_threshold and ev <= params.max_ev:
                        r1 = actual_results.get(num1, 999)
                        r2 = actual_results.get(num2, 999)
                        is_hit = (r1 <= 2 and r2 <= 2)
                        payout = int(estimated_odds * params.bet_amount) if is_hit else 0

                        total_bet += params.bet_amount
                        total_payout += payout
                        bet_count += 1
                        if is_hit:
                            hit_count += 1

                        ret = (payout - params.bet_amount) / params.bet_amount
                        returns.append(ret)

        # 回収率とシャープレシオを計算
        return_rate = (total_payout / total_bet) if total_bet > 0 else 0
        hit_rate = (hit_count / bet_count) if bet_count > 0 else 0

        # シャープレシオ計算
        if len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = mean_return / std_return if std_return > 0 else 0
        else:
            sharpe_ratio = 0

        results.append({
            "ev_threshold": round(ev_threshold, 2),
            "return_rate": round(return_rate, 4),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "bet_count": bet_count,
            "hit_count": hit_count,
            "hit_rate": round(hit_rate, 4),
            "total_bet": total_bet,
            "total_payout": total_payout,
            "profit": total_payout - total_bet,
        })

        ev_threshold += params.ev_step

    return results


@router.post("/simulate/threshold-sweep")
async def start_threshold_sweep(
    background_tasks: BackgroundTasks,
    params: ThresholdSweepParams,
    db: Session = Depends(get_db),
):
    """
    閾値スイープ分析を開始（非同期）

    バックグラウンドで実行され、進捗は /api/v1/model/simulate/threshold-sweep/status で確認できます。
    """
    global _sweep_status

    if _sweep_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="閾値スイープ分析は既に実行中です"
        )

    # バックグラウンドで実行
    background_tasks.add_task(_run_threshold_sweep_async, db, params)

    return {
        "status": "success",
        "message": "閾値スイープ分析を開始しました",
    }


@router.get("/simulate/threshold-sweep/status")
async def get_threshold_sweep_status():
    """
    閾値スイープ分析の進捗と結果を取得
    """
    return {
        "status": "success",
        "sweep": _sweep_status,
    }


@router.post("/simulate/threshold-sweep/sync")
async def run_threshold_sweep_sync(
    params: ThresholdSweepParams,
    db: Session = Depends(get_db),
):
    """
    閾値スイープ分析を同期実行（小規模データ用）

    結果が即座に返されます。
    """
    global _sweep_status

    if _sweep_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="閾値スイープ分析は既に実行中です"
        )

    try:
        _sweep_status["is_running"] = True
        results = _run_threshold_sweep(db, params)

        return {
            "status": "success",
            "bet_type": params.bet_type,
            "total_races": params.limit,
            "data": results,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Threshold sweep failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        _sweep_status["is_running"] = False


# ================== クラウドストレージ関連 ==================

from app.services import storage_service


@router.get("/storage/status")
async def get_storage_status():
    """
    Supabase Storage の接続状態を確認
    """
    available = storage_service.is_storage_available()
    return {
        "status": "success",
        "storage_available": available,
        "bucket": settings.SUPABASE_MODEL_BUCKET if available else None,
    }


@router.get("/storage/models")
async def list_cloud_models():
    """
    クラウド（Supabase Storage）に保存されているモデル一覧を取得
    """
    if not storage_service.is_storage_available():
        raise HTTPException(
            status_code=503,
            detail="Supabase Storage is not configured or unavailable"
        )

    models = storage_service.list_models()
    return {
        "status": "success",
        "count": len(models),
        "models": models,
    }


class UploadModelParams(BaseModel):
    """モデルアップロードパラメータ"""
    version: str = "v1"
    description: Optional[str] = None


@router.post("/storage/upload")
async def upload_model_to_cloud(params: UploadModelParams):
    """
    ローカルの学習済みモデルをクラウド（Supabase Storage）にアップロード

    現在ロードされているモデルをSupabase Storageにアップロードします。
    Colabなど他の環境から利用できるようになります。
    """
    if not storage_service.is_storage_available():
        raise HTTPException(
            status_code=503,
            detail="Supabase Storage is not configured or unavailable"
        )

    # 現在のモデルを取得
    predictor = prediction_service.get_predictor()
    if predictor.model is None:
        raise HTTPException(
            status_code=404,
            detail="No model is currently loaded. Train or load a model first."
        )

    try:
        # モデルデータを準備
        model_data = {
            "model": predictor.model,
            "scaler": predictor.scaler,
            "calibrator": predictor.calibrator,
            "feature_columns": predictor.feature_columns,
            "model_version": params.version,
        }

        # メタデータ
        metadata = {
            "version": params.version,
            "description": params.description,
            "num_features": len(predictor.feature_columns),
            "best_iteration": predictor.model.best_iteration if predictor.model else None,
            "uploaded_from": "fastapi_local",
        }

        # アップロード
        result = storage_service.upload_model(model_data, params.version, metadata)

        logger.info(f"Model uploaded to cloud: {params.version}")

        return {
            "status": "success",
            "message": f"Model {params.version} uploaded to cloud storage",
            **result,
        }

    except Exception as e:
        logger.error(f"Failed to upload model: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload model: {str(e)}"
        )


class DownloadModelParams(BaseModel):
    """モデルダウンロードパラメータ"""
    version: str = "v1"
    set_as_current: bool = True


@router.post("/storage/download")
async def download_model_from_cloud(params: DownloadModelParams):
    """
    クラウド（Supabase Storage）からモデルをダウンロード

    Supabase Storageからモデルをダウンロードし、ローカルに保存します。
    set_as_current=true の場合、現在のモデルとしてロードします。
    """
    if not storage_service.is_storage_available():
        raise HTTPException(
            status_code=503,
            detail="Supabase Storage is not configured or unavailable"
        )

    try:
        # ダウンロード
        model_data = storage_service.download_model(params.version)

        if model_data is None:
            raise HTTPException(
                status_code=404,
                detail=f"Model version '{params.version}' not found in cloud storage"
            )

        # ローカルに保存
        from app.services.predictor import HorseRacingPredictor
        from app.services.predictor.model import MODEL_DIR

        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        local_path = MODEL_DIR / f"model_{params.version}.pkl"

        import pickle
        with open(local_path, "wb") as f:
            pickle.dump(model_data, f)

        logger.info(f"Model downloaded from cloud: {params.version} -> {local_path}")

        # 現在のモデルとして設定
        if params.set_as_current:
            new_predictor = HorseRacingPredictor(model_version=params.version)
            new_predictor.load()
            prediction_service._predictor = new_predictor
            prediction_service.MODEL_VERSION = params.version
            logger.info(f"Model set as current: {params.version}")

        return {
            "status": "success",
            "message": f"Model {params.version} downloaded from cloud storage",
            "version": params.version,
            "local_path": str(local_path),
            "set_as_current": params.set_as_current,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download model: {str(e)}"
        )


class RetrainAndUploadParams(BaseModel):
    """再学習＆アップロードパラメータ"""
    version: str = "v1"
    description: Optional[str] = None
    num_boost_round: int = 1000
    early_stopping: int = 50
    use_time_split: bool = False
    train_end_date: Optional[str] = None
    valid_end_date: Optional[str] = None


@router.post("/retrain-and-upload")
async def retrain_and_upload(params: RetrainAndUploadParams):
    """
    モデルを再学習してクラウドにアップロード（ハイブリッド構成用）

    ローカルで重い学習処理を行い、完了後に自動的にSupabase Storageに
    アップロードします。Colabからは推論のみ行えるようになります。

    ## フロー
    1. ローカルでモデル学習（重い処理）
    2. 学習完了後、Supabase Storageにアップロード
    3. Colabから最新モデルをダウンロードして推論実行

    ## 注意
    - 学習には時間がかかります（数分〜数十分）
    - 進捗は GET /api/v1/model/status で確認できます
    """
    if not storage_service.is_storage_available():
        raise HTTPException(
            status_code=503,
            detail="Supabase Storage is not configured. Set SUPABASE_URL and SUPABASE_KEY."
        )

    def parse_date(date_str: Optional[str]):
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}")

    parsed_train_end = parse_date(params.train_end_date)
    parsed_valid_end = parse_date(params.valid_end_date)

    if params.use_time_split and (not parsed_train_end or not parsed_valid_end):
        raise HTTPException(
            status_code=400,
            detail="Time-split mode requires train_end_date and valid_end_date"
        )

    # 再学習を開始
    result = retraining_service.start_retraining(
        min_date=None,
        num_boost_round=params.num_boost_round,
        early_stopping=params.early_stopping,
        valid_fraction=0.2,
        use_time_split=params.use_time_split,
        train_end_date=parsed_train_end,
        valid_end_date=parsed_valid_end,
        # アップロード用の追加パラメータ
        upload_after_training=True,
        upload_version=params.version,
        upload_description=params.description,
    )

    if result["status"] == "already_running":
        raise HTTPException(
            status_code=409,
            detail=f"Retraining is already running since {result['started_at']}"
        )

    return {
        "status": "success",
        "message": f"Retraining started. Model will be uploaded as version '{params.version}' after completion.",
        "started_at": result["started_at"],
        "upload_version": params.version,
    }


from app.config import settings
