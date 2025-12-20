#!/usr/bin/env python3
"""
モデル学習スクリプト

Usage:
    python ml/train.py                    # デフォルト設定で学習
    python ml/train.py --version v2       # バージョン指定
    python ml/train.py --min-date 2024-01-01  # 日付指定
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.base import SessionLocal
from app.services.predictor import prepare_training_data, HorseRacingPredictor


def main():
    parser = argparse.ArgumentParser(description="Train horse racing prediction model")
    parser.add_argument(
        "--version",
        type=str,
        default="v1",
        help="Model version (default: v1)",
    )
    parser.add_argument(
        "--min-date",
        type=str,
        help="Minimum date for training data (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--num-boost-round",
        type=int,
        default=1000,
        help="Number of boosting rounds (default: 1000)",
    )
    parser.add_argument(
        "--early-stopping",
        type=int,
        default=50,
        help="Early stopping rounds (default: 50)",
    )
    parser.add_argument(
        "--valid-fraction",
        type=float,
        default=0.2,
        help="Validation data fraction (default: 0.2)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Horse Racing Prediction Model Training")
    print("=" * 60)
    print(f"Model version: {args.version}")
    print(f"Minimum date: {args.min_date or 'All data'}")
    print(f"Boosting rounds: {args.num_boost_round}")
    print(f"Early stopping: {args.early_stopping}")
    print(f"Validation fraction: {args.valid_fraction}")
    print("=" * 60)

    # データベース接続
    db = SessionLocal()

    try:
        # 学習データの準備
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
        predictor = HorseRacingPredictor(model_version=args.version)

        results = predictor.train(
            X,
            y,
            num_boost_round=args.num_boost_round,
            early_stopping_rounds=args.early_stopping,
            valid_fraction=args.valid_fraction,
        )

        print(f"  - Train RMSE: {results['train_rmse']:.4f}")
        print(f"  - Valid RMSE: {results['valid_rmse']:.4f}")
        print(f"  - Best iteration: {results['best_iteration']}")

        # モデル保存
        print("\n[3/3] Saving model...")
        model_path = predictor.save()
        print(f"  - Model saved to: {model_path}")

        # 特徴量重要度を表示
        print("\n[Feature Importance (Top 10)]")
        importance = predictor.get_feature_importance()
        for idx, row in importance.head(10).iterrows():
            print(f"  {row['feature']}: {row['importance']:.2f}")

        print("\n" + "=" * 60)
        print("Training completed successfully!")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\nError during training: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
