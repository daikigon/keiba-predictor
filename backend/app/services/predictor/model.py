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

    def __init__(self, model_version: str = "v1", label_smoothing: float = 0.0):
        """
        Args:
            model_version: モデルバージョン
            label_smoothing: ラベルスムージングの強度（0.0-0.1推奨）
                           0.0: スムージングなし（従来通り）
                           0.05: 軽いスムージング（推奨）
                           参考PDFでは目的変数に「少し加工」を施していると記載
        """
        self.model_version = model_version
        self.model: Optional[lgb.Booster] = None
        self.scaler: Optional[StandardScaler] = None
        self.calibrator: Optional[IsotonicRegression] = None
        self.feature_columns = get_feature_columns()
        self.use_calibration = True  # キャリブレーション使用フラグ
        self.label_smoothing = label_smoothing  # ラベルスムージング

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        params: Optional[dict] = None,
        num_boost_round: int = 3000,
        early_stopping_rounds: int = 100,
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
        # デフォルトパラメータ（二値分類：1着か否か）
        if params is None:
            params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "boosting_type": "gbdt",
                "num_leaves": 63,
                "learning_rate": 0.01,
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

        # 二値分類用のラベル作成（1着=1, それ以外=0）
        y_train_binary = (y_train == 1).astype(float)
        y_valid_binary = (y_valid == 1).astype(float)

        # ラベルスムージング適用（学習データのみ）
        if self.label_smoothing > 0:
            y_train_smoothed = self._apply_label_smoothing(y_train_binary)
        else:
            y_train_smoothed = y_train_binary

        # LightGBMデータセット作成
        train_data = lgb.Dataset(X_train, label=y_train_smoothed)
        valid_data = lgb.Dataset(X_valid, label=y_valid_binary, reference=train_data)

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

        # 二値分類の評価指標（Log Loss）
        from sklearn.metrics import log_loss, roc_auc_score
        train_logloss = log_loss(y_train_binary, train_pred)
        valid_logloss = log_loss(y_valid_binary, valid_pred)

        # AUC（勝ち馬を上位に予測できているか）
        try:
            train_auc = roc_auc_score(y_train_binary, train_pred)
            valid_auc = roc_auc_score(y_valid_binary, valid_pred)
        except ValueError:
            train_auc = 0.0
            valid_auc = 0.0

        # キャリブレーションの学習（二値分類でも微調整用に維持）
        self._train_calibrator(X_valid, y_valid, valid_pred)

        results = {
            "train_logloss": train_logloss,
            "valid_logloss": valid_logloss,
            "train_auc": train_auc,
            "valid_auc": valid_auc,
            "best_iteration": self.model.best_iteration,
            "num_features": len(self.feature_columns),
            "num_train_samples": len(X_train),
            "num_valid_samples": len(X_valid),
            "calibrator_trained": self.calibrator is not None,
        }

        return results

    def train_with_test_split(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_valid: pd.DataFrame,
        y_valid: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        params: Optional[dict] = None,
        num_boost_round: int = 3000,
        early_stopping_rounds: int = 100,
    ) -> dict:
        """
        Train/Valid/Testの3分割でモデルを学習する

        - Train: 学習に使用
        - Valid: Early Stoppingのモニタリングに使用（学習には使わない）
        - Test: 最終的な精度確認に使用（学習・モニタリングには使わない）

        Args:
            X_train: 学習用特徴量DataFrame
            y_train: 学習用ターゲット（着順）
            X_valid: 検証用特徴量DataFrame（Early Stopping用）
            y_valid: 検証用ターゲット
            X_test: テスト用特徴量DataFrame（最終評価用）
            y_test: テスト用ターゲット
            params: LightGBMパラメータ
            num_boost_round: 最大ブースティング回数
            early_stopping_rounds: Early Stopping回数（validのloglossが改善しない回数）

        Returns:
            学習結果（train/valid/testの各メトリクス）
        """
        # デフォルトパラメータ（二値分類：1着か否か）
        if params is None:
            params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "boosting_type": "gbdt",
                "num_leaves": 63,
                "learning_rate": 0.01,
                "feature_fraction": 0.8,
                "bagging_fraction": 0.8,
                "bagging_freq": 5,
                "verbose": -1,
                "seed": 42,
            }

        # スケーリング（学習データでfitし、valid/testにはtransformのみ）
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
        X_test_scaled = pd.DataFrame(
            self.scaler.transform(X_test),
            columns=X_test.columns,
            index=X_test.index,
        )

        # 二値分類用のラベル作成（1着=1, それ以外=0）
        y_train_binary = (y_train == 1).astype(float)
        y_valid_binary = (y_valid == 1).astype(float)
        y_test_binary = (y_test == 1).astype(float)

        # ラベルスムージング適用（学習データのみ）
        # 参考PDFの「目的変数に少し加工」に対応
        if self.label_smoothing > 0:
            y_train_smoothed = self._apply_label_smoothing(y_train_binary)
        else:
            y_train_smoothed = y_train_binary

        # LightGBMデータセット作成（学習データにはスムージング適用）
        train_data = lgb.Dataset(X_train_scaled, label=y_train_smoothed)
        valid_data = lgb.Dataset(X_valid_scaled, label=y_valid_binary, reference=train_data)

        # 学習（Early StoppingはValidデータで監視）
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

        # 各データセットで予測
        train_pred = self.model.predict(X_train_scaled)
        valid_pred = self.model.predict(X_valid_scaled)
        test_pred = self.model.predict(X_test_scaled)

        # 評価指標の計算
        from sklearn.metrics import log_loss, roc_auc_score

        # Log Loss
        train_logloss = log_loss(y_train_binary, train_pred)
        valid_logloss = log_loss(y_valid_binary, valid_pred)
        test_logloss = log_loss(y_test_binary, test_pred)

        # AUC
        try:
            train_auc = roc_auc_score(y_train_binary, train_pred)
            valid_auc = roc_auc_score(y_valid_binary, valid_pred)
            test_auc = roc_auc_score(y_test_binary, test_pred)
        except ValueError:
            train_auc = 0.0
            valid_auc = 0.0
            test_auc = 0.0

        # キャリブレーションの学習（Validデータを使用）
        self._train_calibrator(X_valid_scaled, y_valid, valid_pred)

        results = {
            # Train metrics
            "train_logloss": train_logloss,
            "train_auc": train_auc,
            "num_train_samples": len(X_train),
            # Valid metrics（Early Stopping監視用）
            "valid_logloss": valid_logloss,
            "valid_auc": valid_auc,
            "num_valid_samples": len(X_valid),
            # Test metrics（最終評価、学習には未使用）
            "test_logloss": test_logloss,
            "test_auc": test_auc,
            "num_test_samples": len(X_test),
            # Model info
            "best_iteration": self.model.best_iteration,
            "num_features": len(self.feature_columns),
            "calibrator_trained": self.calibrator is not None,
            # 過学習チェック
            "overfit_gap": valid_logloss - train_logloss,
            "generalization_gap": test_logloss - valid_logloss,
        }

        return results

    def train_with_validation(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_valid: pd.DataFrame,
        y_valid: pd.Series,
        params: Optional[dict] = None,
        num_boost_round: int = 3000,
        early_stopping_rounds: int = 100,
    ) -> dict:
        """
        事前に分割されたデータでモデルを学習する（時系列分割用）
        ※ train_with_test_split の使用を推奨

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
        # デフォルトパラメータ（二値分類：1着か否か）
        if params is None:
            params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "boosting_type": "gbdt",
                "num_leaves": 63,
                "learning_rate": 0.01,
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

        # 二値分類用のラベル作成（1着=1, それ以外=0）
        y_train_binary = (y_train == 1).astype(float)
        y_valid_binary = (y_valid == 1).astype(float)

        # ラベルスムージング適用（学習データのみ）
        if self.label_smoothing > 0:
            y_train_smoothed = self._apply_label_smoothing(y_train_binary)
        else:
            y_train_smoothed = y_train_binary

        # LightGBMデータセット作成
        train_data = lgb.Dataset(X_train_scaled, label=y_train_smoothed)
        valid_data = lgb.Dataset(X_valid_scaled, label=y_valid_binary, reference=train_data)

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

        # 二値分類の評価指標（Log Loss）
        from sklearn.metrics import log_loss, roc_auc_score
        train_logloss = log_loss(y_train_binary, train_pred)
        valid_logloss = log_loss(y_valid_binary, valid_pred)

        # AUC（勝ち馬を上位に予測できているか）
        try:
            train_auc = roc_auc_score(y_train_binary, train_pred)
            valid_auc = roc_auc_score(y_valid_binary, valid_pred)
        except ValueError:
            train_auc = 0.0
            valid_auc = 0.0

        # キャリブレーションの学習（二値分類でも微調整用に維持）
        self._train_calibrator(X_valid_scaled, y_valid, valid_pred)

        results = {
            "train_logloss": train_logloss,
            "valid_logloss": valid_logloss,
            "train_auc": train_auc,
            "valid_auc": valid_auc,
            "best_iteration": self.model.best_iteration,
            "num_features": len(self.feature_columns),
            "num_train_samples": len(X_train),
            "num_valid_samples": len(X_valid),
            "calibrator_trained": self.calibrator is not None,
        }

        return results

    def _apply_label_smoothing(self, y: pd.Series) -> pd.Series:
        """
        ラベルスムージングを適用

        参考PDFの「目的変数に少し加工」に対応。
        過学習を防ぎ、キャリブレーションを改善する効果がある。

        Args:
            y: 二値ラベル（0 or 1）

        Returns:
            スムージングされたラベル
        """
        # y=1 → 1-smoothing, y=0 → smoothing
        # 例: smoothing=0.05の場合、1→0.95, 0→0.05
        return y * (1 - self.label_smoothing) + (1 - y) * self.label_smoothing

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
        勝率を予測（二値分類モデルの出力）

        Args:
            X: 特徴量DataFrame

        Returns:
            勝率（0-1）、レース内で合計が1になるよう正規化
        """
        # 二値分類モデルは直接確率を出力
        probs = self.predict(X)

        if self.calibrator is not None and self.use_calibration:
            # キャリブレーション適用（微調整）
            calibrated_probs = self.calibrator.predict(probs)
            probs = calibrated_probs

        # 確率の正規化（レース内で合計が1になるように）
        total = probs.sum()
        if total > 0:
            probs = probs / total

        return probs

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
            "label_smoothing": self.label_smoothing,
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
        self.label_smoothing = model_data.get("label_smoothing", 0.0)  # 後方互換性

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
