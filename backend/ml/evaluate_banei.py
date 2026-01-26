#!/usr/bin/env python3
"""
ばんえい競馬 モデル評価スクリプト

学習済みのばんえいモデルを評価し、予測精度や特徴量重要度を可視化する。

Usage:
    python ml/evaluate_banei.py                    # デフォルト（最新モデル）
    python ml/evaluate_banei.py --version v1      # バージョン指定
    python ml/evaluate_banei.py --test-date 2024-01-01  # 特定日以降をテスト
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.base import SessionLocal
from app.services.predictor import (
    prepare_banei_training_data,
    HorseRacingPredictor,
    BaneiFeatureExtractor,
)
from app.models import Race, Entry
from sqlalchemy import select


def main():
    parser = argparse.ArgumentParser(description="Evaluate Banei horse racing prediction model")
    parser.add_argument(
        "--version",
        type=str,
        default="v1",
        help="Model version to evaluate (default: v1)",
    )
    parser.add_argument(
        "--test-date",
        type=str,
        help="Use data after this date for testing (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--show-predictions",
        action="store_true",
        help="Show sample predictions",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Banei Horse Racing Model Evaluation")
    print("=" * 60)
    print(f"Model version: {args.version}")
    print(f"Race type: banei")

    # モデル読み込み
    print("\n[1/4] Loading Banei model...")
    try:
        predictor = HorseRacingPredictor(
            model_version=args.version,
            race_type="banei",
        )
        predictor.load()
        print(f"  - Model loaded successfully")
        print(f"  - Feature columns: {len(predictor.feature_columns)}")
    except FileNotFoundError:
        print(f"  Error: Banei model version '{args.version}' not found.")
        print("  Please train the model first using: python ml/train_banei.py")
        return 1

    # データベース接続
    db = SessionLocal()

    try:
        # テストデータ準備
        print("\n[2/4] Preparing test data...")
        test_date = None
        if args.test_date:
            test_date = datetime.strptime(args.test_date, "%Y-%m-%d").date()

        X_test, y_test = prepare_banei_training_data(db, min_date=test_date)

        if X_test.empty:
            print("  Error: No test data found.")
            return 1

        print(f"  - Test samples: {len(X_test)}")
        print(f"  - Positive samples (1st place): {(y_test == 1).sum()}")

        # 評価実行
        print("\n[3/4] Evaluating model...")
        evaluate_model(predictor, X_test, y_test)

        # 特徴量重要度
        print("\n[4/4] Feature importance analysis...")
        show_feature_importance(predictor)

        # サンプル予測表示
        if args.show_predictions:
            print("\n[Bonus] Sample predictions...")
            show_sample_predictions(db, predictor, test_date)

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


def evaluate_model(predictor, X_test, y_test):
    """モデルを評価"""
    from sklearn.metrics import (
        log_loss, roc_auc_score, accuracy_score,
        precision_score, recall_score, f1_score,
        confusion_matrix
    )

    # 予測
    y_pred_proba = predictor.predict(X_test)
    y_pred_binary = (y_pred_proba > 0.5).astype(int)
    y_true_binary = (y_test == 1).astype(int)

    # メトリクス計算
    logloss = log_loss(y_true_binary, y_pred_proba)
    try:
        auc = roc_auc_score(y_true_binary, y_pred_proba)
    except ValueError:
        auc = 0.0

    accuracy = accuracy_score(y_true_binary, y_pred_binary)
    precision = precision_score(y_true_binary, y_pred_binary, zero_division=0)
    recall = recall_score(y_true_binary, y_pred_binary, zero_division=0)
    f1 = f1_score(y_true_binary, y_pred_binary, zero_division=0)

    print(f"\n  [Classification Metrics]")
    print(f"  - Log Loss:   {logloss:.4f}")
    print(f"  - AUC:        {auc:.4f}")
    print(f"  - Accuracy:   {accuracy:.4f}")
    print(f"  - Precision:  {precision:.4f}")
    print(f"  - Recall:     {recall:.4f}")
    print(f"  - F1 Score:   {f1:.4f}")

    # 混同行列
    cm = confusion_matrix(y_true_binary, y_pred_binary)
    print(f"\n  [Confusion Matrix]")
    print(f"                 Predicted")
    print(f"                 0      1")
    print(f"  Actual 0    {cm[0][0]:5d}  {cm[0][1]:5d}")
    print(f"         1    {cm[1][0]:5d}  {cm[1][1]:5d}")

    # 的中率分析（レース単位）
    print(f"\n  [Hit Rate Analysis]")
    analyze_hit_rate(X_test, y_test, y_pred_proba)


def analyze_hit_rate(X_test, y_test, y_pred_proba):
    """的中率を分析（レース単位）"""
    # レースごとにグループ化するのが難しいので、
    # 上位N予測での的中率を計算

    # y_pred_probaの上位予測と実際の1着の一致率
    total_samples = len(y_test)
    winners = (y_test == 1).sum()

    # 予測確率の分位点ごとの的中率
    percentiles = [10, 20, 30, 50]
    for p in percentiles:
        threshold = np.percentile(y_pred_proba, 100 - p)
        top_predictions = y_pred_proba >= threshold
        hits = ((y_test == 1) & top_predictions).sum()
        hit_rate = hits / top_predictions.sum() if top_predictions.sum() > 0 else 0
        print(f"    Top {p:2d}% predictions: {hit_rate:.2%} hit rate ({hits}/{top_predictions.sum()})")


def show_feature_importance(predictor):
    """特徴量重要度を表示"""
    importance = predictor.get_feature_importance()

    print("\n  [Top 20 Important Features]")
    print("  " + "-" * 50)

    max_importance = importance['importance'].max()
    for idx, row in importance.head(20).iterrows():
        bar_len = int(row['importance'] / max_importance * 25)
        bar = '#' * bar_len
        print(f"  {row['feature']:28s}: {row['importance']:8.2f} {bar}")

    # カテゴリ別の重要度サマリー
    print("\n  [Feature Category Summary]")
    print("  " + "-" * 50)

    categories = {
        "ソリ重量関連": ["sori_weight", "sori_weight_ratio", "sori_weight_rank",
                     "sori_weight_normalized", "sori_weight_vs_class_avg"],
        "馬体重関連": ["horse_weight_banei", "weight_diff_banei", "weight_trend",
                    "power_index", "optimal_weight_gap"],
        "水分量・馬場": ["moisture_level", "moisture_aptitude", "is_light_track", "is_heavy_track"],
        "騎手": ["jockey_win_rate", "jockey_place_rate", "jockey_year_rank",
               "jockey_heavy_win_rate", "jockey_moisture_apt", "jockey_horse_combo"],
        "過去成績": ["avg_rank_last3", "avg_rank_last5", "win_rate", "place_rate",
                  "show_rate", "days_since_last", "last_result", "best_rank"],
        "オッズ": ["odds", "log_odds", "popularity"],
    }

    for cat_name, features in categories.items():
        cat_importance = importance[importance['feature'].isin(features)]['importance'].sum()
        total_importance = importance['importance'].sum()
        pct = cat_importance / total_importance * 100 if total_importance > 0 else 0
        bar_len = int(pct / 5)
        bar = '#' * bar_len
        print(f"  {cat_name:15s}: {pct:5.1f}% {bar}")


def show_sample_predictions(db, predictor, test_date):
    """サンプル予測を表示"""
    # 最新のばんえいレースを取得
    stmt = (
        select(Race)
        .where(Race.race_type == "banei")
        .where(Race.entries.any(Entry.result.isnot(None)))
    )
    if test_date:
        stmt = stmt.where(Race.date >= test_date)
    stmt = stmt.order_by(Race.date.desc()).limit(3)

    races = list(db.execute(stmt).scalars().all())

    if not races:
        print("  No recent races found for prediction display.")
        return

    extractor = BaneiFeatureExtractor(db, use_cache=False)

    for race in races:
        print(f"\n  Race: {race.race_name or race.race_id}")
        print(f"  Date: {race.date}, Grade: {race.grade}")
        print("  " + "-" * 50)

        df = extractor.extract_race_features(race)
        if df.empty:
            continue

        # 予測
        try:
            from app.services.predictor.features_banei import get_banei_feature_columns
            feature_cols = get_banei_feature_columns()
            X = df[feature_cols].fillna(0)
            probs = predictor.predict_proba(X)
        except Exception as e:
            print(f"  Error predicting: {e}")
            continue

        # 結果を結合
        df['predicted_prob'] = probs
        df['predicted_rank'] = df['predicted_prob'].rank(ascending=False).astype(int)

        # 実際の着順を取得
        results = []
        for _, row in df.iterrows():
            entry_stmt = select(Entry).where(
                Entry.race_id == race.race_id,
                Entry.horse_number == row["horse_number"]
            )
            entry = db.execute(entry_stmt).scalar_one_or_none()
            results.append(entry.result if entry else None)
        df['actual_result'] = results

        # 表示
        df_display = df[['horse_number', 'predicted_prob', 'predicted_rank', 'actual_result']].copy()
        df_display = df_display.sort_values('predicted_rank')

        print(f"  {'馬番':>4s} {'予測確率':>10s} {'予測順位':>8s} {'実着順':>6s}")
        for _, row in df_display.iterrows():
            actual = str(int(row['actual_result'])) if pd.notna(row['actual_result']) else '-'
            hit_mark = '*' if row['predicted_rank'] == 1 and actual == '1' else ''
            print(f"  {int(row['horse_number']):4d} {row['predicted_prob']:10.4f} {int(row['predicted_rank']):8d} {actual:>6s} {hit_mark}")


if __name__ == "__main__":
    sys.exit(main())
