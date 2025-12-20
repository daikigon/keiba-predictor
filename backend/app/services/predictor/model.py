"""
予測モデルモジュール

LightGBMを使用した競馬予測モデル
"""
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.preprocessing import StandardScaler

from .features import get_feature_columns


# モデル保存ディレクトリ
MODEL_DIR = Path(__file__).parent.parent.parent.parent / "ml" / "models"


class HorseRacingPredictor:
    """競馬予測モデル"""

    def __init__(self, model_version: str = "v1"):
        self.model_version = model_version
        self.model: Optional[lgb.Booster] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_columns = get_feature_columns()

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        params: Optional[dict] = None,
        num_boost_round: int = 1000,
        early_stopping_rounds: int = 50,
        valid_fraction: float = 0.2,
    ) -> dict:
        """
        モデルを学習する

        Args:
            X: 特徴量DataFrame
            y: ターゲット（着順）
            params: LightGBMパラメータ
            num_boost_round: ブースティング回数
            early_stopping_rounds: 早期停止回数
            valid_fraction: 検証データの割合

        Returns:
            学習結果（メトリクス等）
        """
        # デフォルトパラメータ
        if params is None:
            params = {
                "objective": "lambdarank",
                "metric": "ndcg",
                "ndcg_eval_at": [1, 3, 5],
                "boosting_type": "gbdt",
                "num_leaves": 31,
                "learning_rate": 0.05,
                "feature_fraction": 0.8,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "verbose": -1,
                "seed": 42,
            }

        # スケーリング
        self.scaler = StandardScaler()
        X_scaled = pd.DataFrame(
            self.scaler.fit_transform(X),
            columns=X.columns,
            index=X.index,
        )

        # 訓練・検証データ分割（時系列を考慮）
        split_idx = int(len(X_scaled) * (1 - valid_fraction))
        X_train = X_scaled.iloc[:split_idx]
        X_valid = X_scaled.iloc[split_idx:]
        y_train = y.iloc[:split_idx]
        y_valid = y.iloc[split_idx:]

        # ランキング学習用のグループ作成
        # 着順を反転（1位が最高スコア）
        y_train_rank = y_train.max() - y_train + 1
        y_valid_rank = y_valid.max() - y_valid + 1

        # LightGBMデータセット作成
        # NOTE: ランキング学習ではグループ情報が必要だが、
        # ここでは回帰として学習し、予測値でソートする簡易版を使用
        params["objective"] = "regression"
        params["metric"] = "rmse"
        del params["ndcg_eval_at"]

        train_data = lgb.Dataset(X_train, label=y_train_rank)
        valid_data = lgb.Dataset(X_valid, label=y_valid_rank, reference=train_data)

        # 学習
        callbacks = [
            lgb.early_stopping(stopping_rounds=early_stopping_rounds),
            lgb.log_evaluation(period=100),
        ]

        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=num_boost_round,
            valid_sets=[train_data, valid_data],
            valid_names=["train", "valid"],
            callbacks=callbacks,
        )

        # 評価
        train_pred = self.model.predict(X_train)
        valid_pred = self.model.predict(X_valid)

        results = {
            "train_rmse": np.sqrt(np.mean((train_pred - y_train_rank) ** 2)),
            "valid_rmse": np.sqrt(np.mean((valid_pred - y_valid_rank) ** 2)),
            "best_iteration": self.model.best_iteration,
            "num_features": len(self.feature_columns),
            "num_train_samples": len(X_train),
            "num_valid_samples": len(X_valid),
        }

        return results

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        予測を行う

        Args:
            X: 特徴量DataFrame

        Returns:
            予測スコア（高いほど上位予想）
        """
        if self.model is None:
            raise RuntimeError("Model not trained or loaded")

        if self.scaler is None:
            raise RuntimeError("Scaler not available")

        # 必要な特徴量のみを選択
        X_features = X[self.feature_columns].copy()

        # 欠損値を埋める
        X_features = X_features.fillna(0)

        # スケーリング
        X_scaled = pd.DataFrame(
            self.scaler.transform(X_features),
            columns=X_features.columns,
            index=X_features.index,
        )

        return self.model.predict(X_scaled)

    def predict_ranking(self, X: pd.DataFrame) -> list[int]:
        """
        順位予測を行う

        Args:
            X: 特徴量DataFrame（レース内の全出走馬）

        Returns:
            予測順位のリスト（馬番順）
        """
        scores = self.predict(X)

        # スコアの高い順にランク付け
        rankings = np.argsort(-scores) + 1

        return rankings.tolist()

    def save(self, path: Optional[Path] = None) -> Path:
        """
        モデルを保存する

        Args:
            path: 保存先パス

        Returns:
            保存したパス
        """
        if self.model is None:
            raise RuntimeError("Model not trained")

        if path is None:
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            path = MODEL_DIR / f"model_{self.model_version}.pkl"

        model_data = {
            "model": self.model,
            "scaler": self.scaler,
            "feature_columns": self.feature_columns,
            "model_version": self.model_version,
        }

        with open(path, "wb") as f:
            pickle.dump(model_data, f)

        return path

    def load(self, path: Optional[Path] = None) -> None:
        """
        モデルを読み込む

        Args:
            path: モデルファイルパス
        """
        if path is None:
            path = MODEL_DIR / f"model_{self.model_version}.pkl"

        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        with open(path, "rb") as f:
            model_data = pickle.load(f)

        self.model = model_data["model"]
        self.scaler = model_data["scaler"]
        self.feature_columns = model_data["feature_columns"]
        self.model_version = model_data["model_version"]

    def get_feature_importance(self) -> pd.DataFrame:
        """
        特徴量重要度を取得

        Returns:
            特徴量重要度のDataFrame
        """
        if self.model is None:
            raise RuntimeError("Model not trained or loaded")

        importance = pd.DataFrame({
            "feature": self.feature_columns,
            "importance": self.model.feature_importance(importance_type="gain"),
        })

        return importance.sort_values("importance", ascending=False)


def get_model(version: str = "v1") -> HorseRacingPredictor:
    """
    学習済みモデルを取得

    Args:
        version: モデルバージョン

    Returns:
        学習済みのHorseRacingPredictor
    """
    predictor = HorseRacingPredictor(model_version=version)

    try:
        predictor.load()
    except FileNotFoundError:
        # モデルファイルがない場合は未学習のモデルを返す
        pass

    return predictor
