#!/usr/bin/env python3
"""
モデル学習スクリプト

Usage:
    # 従来モード（フラクションで分割）
    python ml/train.py                    # デフォルト設定で学習
    python ml/train.py --version v2       # バージョン指定

    # 時系列分割モード（推奨）
    python ml/train.py --time-split \
        --train-end 2023-11-17 \
        --valid-end 2024-02-17

    # 完全な期間指定
    python ml/train.py --time-split \
        --train-start 2019-02-17 \
        --train-end 2023-11-17 \
        --valid-end 2024-02-17 \
        --version v2
"""

import argparse
import sys
from datetime import datetime, date
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.base import SessionLocal
from app.services.predictor import (
    prepare_training_data,
    prepare_time_split_data,
    HorseRacingPredictor,
)


def main():
    parser = argparse.ArgumentParser(description="Train horse racing prediction model")
    parser.add_argument(
        "--version",
        type=str,
        default="v1",
        help="Model version (default: v1)",
    )
    parser.add_argument(
        "--num-boost-round",
        type=int,
        default=3000,
        help="Number of boosting rounds (default: 3000)",
    )
    parser.add_argument(
        "--early-stopping",
        type=int,
        default=100,
        help="Early stopping rounds (default: 100)",
    )

    # 従来モード用引数
    parser.add_argument(
        "--min-date",
        type=str,
        help="[Legacy mode] Minimum date for training data (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--valid-fraction",
        type=float,
        default=0.2,
        help="[Legacy mode] Validation data fraction (default: 0.2)",
    )

    # 時系列分割モード用引数
    parser.add_argument(
        "--time-split",
        action="store_true",
        help="Use time-based train/valid/test split (recommended)",
    )
    parser.add_argument(
        "--train-start",
        type=str,
        help="[Time-split mode] Training data start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--train-end",
        type=str,
        help="[Time-split mode] Training data end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--valid-end",
        type=str,
        help="[Time-split mode] Validation data end date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--label-smoothing",
        type=float,
        default=0.05,
        help="Label smoothing strength (0.0-0.1 recommended, default: 0.05)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Horse Racing Prediction Model Training")
    print("=" * 60)
    print(f"Model version: {args.version}")
    print(f"Boosting rounds: {args.num_boost_round}")
    print(f"Early stopping: {args.early_stopping}")
    print(f"Label smoothing: {args.label_smoothing}")

    if args.time_split:
        if not args.train_end or not args.valid_end:
            print("\nError: --time-split requires --train-end and --valid-end")
            print("\nExample:")
            print("  python ml/train.py --time-split --train-end 2023-11-17 --valid-end 2024-02-17")
            return 1
        print("\nMode: Time-based split (recommended)")
        print(f"  Train: {args.train_start or 'earliest'} ~ {args.train_end}")
        print(f"  Valid: {args.train_end} ~ {args.valid_end}")
        print(f"  Test:  {args.valid_end} ~ latest (for evaluation only)")
    else:
        print("\nMode: Legacy (fraction-based split)")
        print(f"  Minimum date: {args.min_date or 'All data'}")
        print(f"  Validation fraction: {args.valid_fraction}")

    print("=" * 60)

    # データベース接続
    db = SessionLocal()

    try:
        if args.time_split:
            # 時系列分割モード
            return train_with_time_split(db, args)
        else:
            # 従来モード
            return train_legacy_mode(db, args)

    except Exception as e:
        print(f"\nError during training: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        db.close()


def train_legacy_mode(db, args):
    """従来の学習モード（フラクションで分割）"""
    print("\n[1/3] Preparing training data...")
    min_date = None
    if args.min_date:
        min_date = datetime.strptime(args.min_date, "%Y-%m-%d").date()

    X, y = prepare_training_data(db, min_date=min_date)

    if X.empty:
        print("Error: No training data found.")
        print("Please run the scraping script first to collect race data.")
        return 1

    print(f"  - Features shape: {X.shape}")
    print(f"  - Target shape: {y.shape}")
    print(f"  - Feature columns: {len(X.columns)}")

    # モデル学習
    print("\n[2/3] Training model...")
    predictor = HorseRacingPredictor(
        model_version=args.version,
        label_smoothing=args.label_smoothing,
    )

    results = predictor.train(
        X,
        y,
        num_boost_round=args.num_boost_round,
        early_stopping_rounds=args.early_stopping,
        valid_fraction=args.valid_fraction,
    )

    print(f"  - Train LogLoss: {results['train_logloss']:.4f}")
    print(f"  - Valid LogLoss: {results['valid_logloss']:.4f}")
    print(f"  - Train AUC: {results['train_auc']:.4f}")
    print(f"  - Valid AUC: {results['valid_auc']:.4f}")
    print(f"  - Best iteration: {results['best_iteration']}")

    # モデル保存
    print("\n[3/3] Saving model...")
    model_path = predictor.save()
    print(f"  - Model saved to: {model_path}")

    # 特徴量重要度を表示
    print_feature_importance(predictor)

    print("\n" + "=" * 60)
    print("Training completed successfully!")
    print("=" * 60)

    return 0


def train_with_time_split(db, args):
    """時系列分割モードで学習"""
    print("\n[1/4] Preparing time-split data...")

    train_start = None
    if args.train_start:
        train_start = datetime.strptime(args.train_start, "%Y-%m-%d").date()

    train_end = datetime.strptime(args.train_end, "%Y-%m-%d").date()
    valid_end = datetime.strptime(args.valid_end, "%Y-%m-%d").date()

    data = prepare_time_split_data(
        db,
        train_end_date=train_end,
        valid_end_date=valid_end,
        train_start_date=train_start,
    )

    X_train, y_train = data['train']
    X_valid, y_valid = data['valid']
    X_test, y_test = data['test']

    print(f"  - Train samples: {data['counts']['train']}")
    print(f"  - Valid samples: {data['counts']['valid']}")
    print(f"  - Test samples:  {data['counts']['test']} (held out)")

    if X_train.empty:
        print("Error: No training data found.")
        return 1

    if X_valid.empty:
        print("Error: No validation data found.")
        print("  → Check if there are races between train_end and valid_end")
        return 1

    print(f"\n  Date ranges:")
    dr = data['date_ranges']
    print(f"    Train: {dr['train'][0] or 'earliest'} ~ {dr['train'][1]}")
    print(f"    Valid: {dr['valid'][0]} ~ {dr['valid'][1]}")
    print(f"    Test:  {dr['test'][0]} ~ latest")

    # モデル学習（Train/Valid/Testの3分割）
    print("\n[2/4] Training model with train/valid/test split...")
    print("       - Train: 学習に使用")
    print("       - Valid: Early Stoppingのモニタリング（学習に使用しない）")
    print("       - Test:  最終評価用（学習・モニタリングに使用しない）")
    print(f"       - Label smoothing: {args.label_smoothing}")
    predictor = HorseRacingPredictor(
        model_version=args.version,
        label_smoothing=args.label_smoothing,
    )

    if X_test.empty:
        # テストデータがない場合は従来のtrain_with_validationを使用
        print("\n  [Warning] No test data available, using train/valid split only")
        results = predictor.train_with_validation(
            X_train,
            y_train,
            X_valid,
            y_valid,
            num_boost_round=args.num_boost_round,
            early_stopping_rounds=args.early_stopping,
        )
    else:
        # 3分割で学習
        results = predictor.train_with_test_split(
            X_train,
            y_train,
            X_valid,
            y_valid,
            X_test,
            y_test,
            num_boost_round=args.num_boost_round,
            early_stopping_rounds=args.early_stopping,
        )

    # 評価結果の表示
    print("\n[3/4] Evaluation results...")
    print(f"  [Train] LogLoss: {results['train_logloss']:.4f}, AUC: {results['train_auc']:.4f}")
    print(f"  [Valid] LogLoss: {results['valid_logloss']:.4f}, AUC: {results['valid_auc']:.4f}")
    if 'test_logloss' in results:
        print(f"  [Test]  LogLoss: {results['test_logloss']:.4f}, AUC: {results['test_auc']:.4f}")
    print(f"  Best iteration: {results['best_iteration']}")

    # 過学習チェック
    if 'overfit_gap' in results:
        print(f"\n  [Overfitting Check]")
        print(f"    Train→Valid gap: {results['overfit_gap']:.4f}")
        print(f"    Valid→Test gap:  {results['generalization_gap']:.4f}")
        if results['overfit_gap'] > 0.1:
            print("    ⚠️  Warning: Model may be overfitting (train→valid gap > 0.1)")

    # モデル保存
    print("\n[4/4] Saving model...")
    model_path = predictor.save()
    print(f"  - Model saved to: {model_path}")

    # 特徴量重要度を表示
    print_feature_importance(predictor)

    print("\n" + "=" * 60)
    print("Training completed successfully!")
    print(f"Model version: {args.version}")
    print("=" * 60)

    return 0


def print_feature_importance(predictor):
    """特徴量重要度を表示"""
    print("\n[Feature Importance (Top 10)]")
    importance = predictor.get_feature_importance()
    for idx, row in importance.head(10).iterrows():
        print(f"  {row['feature']}: {row['importance']:.2f}")


if __name__ == "__main__":
    sys.exit(main())
