#!/usr/bin/env python3
"""
モデル評価スクリプト

Usage:
    python ml/evaluate.py                    # デフォルト設定で評価
    python ml/evaluate.py --version v2       # バージョン指定
    python ml/evaluate.py --test-date 2024-12-01  # テスト日指定
"""

import argparse
import sys
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.db.base import SessionLocal
from app.models import Race, Entry
from app.services.predictor import FeatureExtractor, get_model


def calculate_metrics(predictions: list, actuals: list) -> dict:
    """
    予測精度のメトリクスを計算

    Args:
        predictions: 予測順位のリスト
        actuals: 実際の着順のリスト

    Returns:
        メトリクスの辞書
    """
    if not predictions or not actuals:
        return {}

    # 1着的中率
    win_correct = sum(1 for p, a in zip(predictions, actuals) if p == 1 and a == 1)
    win_total = sum(1 for a in actuals if a == 1)
    win_rate = win_correct / win_total if win_total > 0 else 0

    # 3着以内的中率（複勝）
    show_correct = sum(1 for p, a in zip(predictions, actuals) if p <= 3 and a <= 3)
    show_total = sum(1 for a in actuals if a <= 3)
    show_rate = show_correct / show_total if show_total > 0 else 0

    # 上位3頭のうち3着以内に入った頭数の平均
    top3_in_top3 = []
    for i in range(0, len(predictions), 18):  # レースごと（最大18頭）
        race_preds = predictions[i:i+18]
        race_actuals = actuals[i:i+18]
        if len(race_preds) >= 3:
            top3_pred_indices = sorted(range(len(race_preds)), key=lambda x: race_preds[x])[:3]
            count = sum(1 for idx in top3_pred_indices if race_actuals[idx] <= 3)
            top3_in_top3.append(count)

    avg_top3_hit = np.mean(top3_in_top3) if top3_in_top3 else 0

    return {
        "win_rate": win_rate,
        "show_rate": show_rate,
        "avg_top3_hit": avg_top3_hit,
    }


def evaluate_by_race(db, predictor, extractor, race: Race) -> dict:
    """
    レース単位で評価を行う

    Args:
        db: データベースセッション
        predictor: 予測モデル
        extractor: 特徴量抽出器
        race: Raceオブジェクト

    Returns:
        評価結果
    """
    # 特徴量抽出
    df = extractor.extract_race_features(race)
    if df.empty:
        return None

    # 実際の着順を取得
    actual_results = {}
    for entry in race.entries:
        if entry.result:
            actual_results[entry.horse_number] = entry.result

    if not actual_results:
        return None

    # 予測
    try:
        scores = predictor.predict(df)
    except RuntimeError as e:
        return None

    # 予測スコアでランキング
    df["pred_score"] = scores
    df["pred_rank"] = df["pred_score"].rank(ascending=False).astype(int)
    df["actual_rank"] = df["horse_number"].map(actual_results)
    df = df.dropna(subset=["actual_rank"])

    if df.empty:
        return None

    # 1着予測の正解
    pred_winner = df.loc[df["pred_rank"] == 1, "horse_number"].iloc[0] if len(df) > 0 else None
    actual_winner = df.loc[df["actual_rank"] == 1, "horse_number"].iloc[0] if len(df[df["actual_rank"] == 1]) > 0 else None
    win_hit = pred_winner == actual_winner if pred_winner and actual_winner else False

    # 上位3頭の3着以内的中数
    top3_pred = df.nsmallest(3, "pred_rank")["horse_number"].tolist()
    top3_hit = sum(1 for hn in top3_pred if actual_results.get(hn, 999) <= 3)

    return {
        "race_id": race.race_id,
        "race_name": race.race_name,
        "date": race.date,
        "field_size": len(df),
        "win_hit": win_hit,
        "top3_hit": top3_hit,
        "pred_ranking": df.sort_values("pred_rank")[["horse_number", "pred_rank", "actual_rank"]].to_dict("records"),
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate horse racing prediction model")
    parser.add_argument(
        "--version",
        type=str,
        default="v1",
        help="Model version (default: v1)",
    )
    parser.add_argument(
        "--test-date",
        type=str,
        help="Test data start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of races to evaluate (default: 100)",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Show detailed results for each race",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Horse Racing Prediction Model Evaluation")
    print("=" * 60)
    print(f"Model version: {args.version}")
    print(f"Test date from: {args.test_date or 'All data'}")
    print(f"Max races: {args.limit}")
    print("=" * 60)

    # データベース接続
    db = SessionLocal()

    try:
        # モデル読み込み
        print("\n[1/3] Loading model...")
        predictor = get_model(args.version)

        if predictor.model is None:
            print("Error: Model not found. Please train the model first.")
            print("  Run: python ml/train.py")
            return 1

        print(f"  - Model version: {predictor.model_version}")
        print(f"  - Features: {len(predictor.feature_columns)}")

        # テストデータ取得
        print("\n[2/3] Loading test data...")
        stmt = (
            select(Race)
            .where(Race.entries.any(Entry.result.isnot(None)))
            .order_by(Race.date.desc())
            .limit(args.limit)
        )

        if args.test_date:
            test_date = datetime.strptime(args.test_date, "%Y-%m-%d").date()
            stmt = stmt.where(Race.date >= test_date)

        races = list(db.execute(stmt).scalars().all())
        print(f"  - Found {len(races)} races")

        if not races:
            print("Error: No test data found.")
            return 1

        # 評価
        print("\n[3/3] Evaluating...")
        extractor = FeatureExtractor(db)
        results = []

        for race in races:
            result = evaluate_by_race(db, predictor, extractor, race)
            if result:
                results.append(result)

        if not results:
            print("Error: No valid results.")
            return 1

        # 集計
        total_races = len(results)
        win_hits = sum(1 for r in results if r["win_hit"])
        avg_top3 = np.mean([r["top3_hit"] for r in results])

        print("\n" + "=" * 60)
        print("Evaluation Results")
        print("=" * 60)
        print(f"Total races evaluated: {total_races}")
        print(f"Win prediction accuracy: {win_hits}/{total_races} ({100*win_hits/total_races:.1f}%)")
        print(f"Average top-3 hits: {avg_top3:.2f}/3")
        print()

        # グレード別集計
        print("[By Grade]")
        grade_results = {}
        for r in results:
            race = next((race for race in races if race.race_id == r["race_id"]), None)
            if race:
                grade = race.grade or "Other"
                if grade not in grade_results:
                    grade_results[grade] = {"total": 0, "win_hits": 0, "top3_sum": 0}
                grade_results[grade]["total"] += 1
                grade_results[grade]["win_hits"] += 1 if r["win_hit"] else 0
                grade_results[grade]["top3_sum"] += r["top3_hit"]

        for grade, stats in sorted(grade_results.items()):
            win_pct = 100 * stats["win_hits"] / stats["total"]
            avg_t3 = stats["top3_sum"] / stats["total"]
            print(f"  {grade}: {stats['total']} races, Win: {win_pct:.1f}%, Avg Top3: {avg_t3:.2f}")

        # 詳細表示
        if args.detail:
            print("\n[Detailed Results]")
            for r in results[:10]:
                status = "O" if r["win_hit"] else "X"
                print(f"  [{status}] {r['date']} {r['race_name']} (Top3 hit: {r['top3_hit']}/3)")
                for pred in r["pred_ranking"][:5]:
                    print(f"      #{pred['horse_number']}: Pred={pred['pred_rank']}, Actual={int(pred['actual_rank'])}")

        print("\n" + "=" * 60)
        print("Evaluation completed!")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\nError during evaluation: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
