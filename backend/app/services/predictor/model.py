"""
予測モデルモジュール

LightGBMを使用した競馬予測モデル
キャリブレーション機能付き
"""
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.preprocessing import StandardScaler
from sklearn.isotonic import IsotonicRegression
from sklearn.calibration import CalibratedClassifierCV

from .features import get_feature_columns


# モデル保存ディレクトリ
MODEL_DIR = Path(__file__).parent.parent.parent.parent / "ml" / "models"


class HorseRacingPredictor:
    """競馬予測モデル（キャリブレーション機能付き）"""

    def __init__(self, model_version: str = "v1"):
        self.model_version = model_version
        self.model: Optional[lgb.Booster] = None
        self.scaler: Optional[StandardScaler] = None
        self.calibrator: Optional[IsotonicRegression] = None
        self.feature_columns = get_feature_columns()
        self.use_calibration = True  # キャリブレーション使用フラグ

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

        # === キャリブレーションの学習 ===
        # 検証データを使ってキャリブレーターを学習
        self._train_calibrator(X_valid, y_valid, valid_pred)

        results = {
            "train_rmse": np.sqrt(np.mean((train_pred - y_train_rank) ** 2)),
            "valid_rmse": np.sqrt(np.mean((valid_pred - y_valid_rank) ** 2)),
            "best_iteration": self.model.best_iteration,
            "num_features": len(self.feature_columns),
            "num_train_samples": len(X_train),
            "num_valid_samples": len(X_valid),
            "calibrator_trained": self.calibrator is not None,
        }

        return results

    def train_with_validation(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_valid: pd.DataFrame,
        y_valid: pd.Series,
        params: Optional[dict] = None,
        num_boost_round: int = 1000,
        early_stopping_rounds: int = 50,
    ) -> dict:
        """
        事前に分割されたデータでモデルを学習する（時系列分割用）

        Args:
            X_train: 学習用特徴量DataFrame
            y_train: 学習用ターゲット（着順）
            X_valid: 検証用特徴量DataFrame
            y_valid: 検証用ターゲット（着順）
            params: LightGBMパラメータ
            num_boost_round: ブースティング回数
            early_stopping_rounds: 早期停止回数

        Returns:
            学習結果（メトリクス等）
        """
        # デフォルトパラメータ
        if params is None:
            params = {
                "objective": "regression",
                "metric": "rmse",
                "boosting_type": "gbdt",
                "num_leaves": 31,
                "learning_rate": 0.05,
                "feature_fraction": 0.8,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "verbose": -1,
                "seed": 42,
            }

        # スケーリング（学習データでfitし、検証データにはtransformのみ）
        self.scaler = StandardScaler()
        X_train_scaled = pd.DataFrame(
            self.scaler.fit_transform(X_train),
            columns=X_train.columns,
            index=X_train.index,
        )
        X_valid_scaled = pd.DataFrame(
            self.scaler.transform(X_valid),
            columns=X_valid.columns,
            index=X_valid.index,
        )

        # ランキング学習用: 着順を反転（1位が最高スコア）
        y_train_rank = y_train.max() - y_train + 1
        y_valid_rank = y_valid.max() - y_valid + 1

        # LightGBMデータセット作成
        train_data = lgb.Dataset(X_train_scaled, label=y_train_rank)
        valid_data = lgb.Dataset(X_valid_scaled, label=y_valid_rank, reference=train_data)

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
        train_pred = self.model.predict(X_train_scaled)
        valid_pred = self.model.predict(X_valid_scaled)

        # キャリブレーションの学習
        self._train_calibrator(X_valid_scaled, y_valid, valid_pred)

        results = {
            "train_rmse": np.sqrt(np.mean((train_pred - y_train_rank) ** 2)),
            "valid_rmse": np.sqrt(np.mean((valid_pred - y_valid_rank) ** 2)),
            "best_iteration": self.model.best_iteration,
            "num_features": len(self.feature_columns),
            "num_train_samples": len(X_train),
            "num_valid_samples": len(X_valid),
            "calibrator_trained": self.calibrator is not None,
        }

        return results

    def _train_calibrator(
        self,
        X_valid: pd.DataFrame,
        y_valid: pd.Series,
        valid_pred: np.ndarray,
    ) -> None:
        """
        キャリブレーターを学習する

        検証データでの予測値と実際の勝敗を使って、
        確率を補正するためのキャリブレーターを学習

        Args:
            X_valid: 検証用特徴量
            y_valid: 検証用ターゲット（着順）
            valid_pred: モデルの予測スコア
        """
        try:
            # 着順1位を正解ラベルとする（二値分類）
            y_binary = (y_valid == 1).astype(int)

            # 予測スコアを0-1に正規化
            pred_min = valid_pred.min()
            pred_max = valid_pred.max()
            if pred_max > pred_min:
                pred_normalized = (valid_pred - pred_min) / (pred_max - pred_min)
            else:
                pred_normalized = np.full_like(valid_pred, 0.5)

            # Isotonic Regressionでキャリブレーション
            self.calibrator = IsotonicRegression(
                y_min=0.0,
                y_max=1.0,
                out_of_bounds='clip'
            )
            self.calibrator.fit(pred_normalized, y_binary)

        except Exception as e:
            print(f"Calibrator training failed: {e}")
            self.calibrator = None

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

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        キャリブレーション済み確率を予測

        Args:
            X: 特徴量DataFrame

        Returns:
            キャリブレーション済み勝率（0-1）
        """
        scores = self.predict(X)

        if self.calibrator is not None and self.use_calibration:
            # スコアを0-1に正規化
            pred_min = scores.min()
            pred_max = scores.max()
            if pred_max > pred_min:
                scores_normalized = (scores - pred_min) / (pred_max - pred_min)
            else:
                scores_normalized = np.full_like(scores, 0.5)

            # キャリブレーション適用
            calibrated_probs = self.calibrator.predict(scores_normalized)

            # 確率の正規化（合計が1になるように）
            total = calibrated_probs.sum()
            if total > 0:
                calibrated_probs = calibrated_probs / total

            return calibrated_probs
        else:
            # キャリブレーターがない場合はソフトマックス
            exp_scores = np.exp(scores - np.max(scores))
            return exp_scores / exp_scores.sum()

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
            "calibrator": self.calibrator,
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
        self.calibrator = model_data.get("calibrator")  # 後方互換性
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
