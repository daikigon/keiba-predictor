#!/usr/bin/env python3
"""
期待値ベース馬券シミュレーション

過去のレースデータを使って、期待値ベースの買い方をした場合の
回収率をシミュレーションします。

Usage:
    python ml/simulate.py                         # デフォルト設定
    python ml/simulate.py --ev-threshold 1.2      # 期待値閾値を変更
    python ml/simulate.py --bet-type all          # 単勝と馬連両方
    python ml/simulate.py --start-date 2024-01-01 # 開始日指定
"""

import argparse
import sys
from datetime import datetime, date
from pathlib import Path
from itertools import combinations
from typing import Optional

import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.db.base import SessionLocal
from app.models import Race, Entry
from app.services.predictor import FeatureExtractor, get_model


def calculate_umaren_probability(probabilities: dict, h1: int, h2: int, n_horses: int) -> float:
    """馬連の的中確率を計算"""
    p1 = probabilities.get(h1, 0)
    p2 = probabilities.get(h2, 0)

    if p1 == 0 or p2 == 0:
        return 0.0

    correction = n_horses / 2 if n_horses > 2 else 1
    umaren_prob = (p1 * p2 * correction) * 2

    return min(umaren_prob, 1.0)


def simulate_race(
    db,
    predictor,
    extractor,
    race: Race,
    ev_threshold: float = 1.0,
    umaren_ev_threshold: float = 1.2,
    bet_amount: int = 100,
    bet_type: str = "all",
) -> Optional[dict]:
    """
    1レースのシミュレーションを行う

    Args:
        db: データベースセッション
        predictor: 予測モデル
        extractor: 特徴量抽出器
        race: Raceオブジェクト
        ev_threshold: 単勝の期待値閾値
        umaren_ev_threshold: 馬連の期待値閾値
        bet_amount: 1点あたりの賭け金
        bet_type: "tansho", "umaren", or "all"

    Returns:
        シミュレーション結果
    """
    # 特徴量抽出
    df = extractor.extract_race_features(race)
    if df.empty:
        return None

    # 実際の着順とオッズを取得
    actual_results = {}
    odds_data = {}
    for entry in race.entries:
        if entry.result:
            actual_results[entry.horse_number] = entry.result
        if entry.odds:
            odds_data[entry.horse_number] = entry.odds

    if not actual_results or not odds_data:
        return None

    # 予測
    try:
        scores = predictor.predict(df)
    except RuntimeError:
        return None

    # 確率計算（ソフトマックス）
    exp_scores = np.exp(scores - np.max(scores))
    probabilities_arr = exp_scores / exp_scores.sum()

    df["pred_score"] = scores
    df["probability"] = probabilities_arr
    df["pred_rank"] = df["pred_score"].rank(ascending=False).astype(int)

    # 馬番→確率のマッピング
    probabilities = dict(zip(df["horse_number"].astype(int), df["probability"]))

    result = {
        "race_id": race.race_id,
        "race_name": race.race_name,
        "date": race.date,
        "course": race.course,
        "grade": race.grade,
        "field_size": len(df),
        "bets": [],
        "total_bet": 0,
        "total_payout": 0,
    }

    # === 単勝シミュレーション ===
    if bet_type in ("tansho", "all"):
        for _, row in df.iterrows():
            horse_num = int(row["horse_number"])
            prob = row["probability"]
            odds = odds_data.get(horse_num, 0)

            if odds <= 0:
                continue

            ev = prob * odds

            if ev >= ev_threshold:
                actual_rank = actual_results.get(horse_num, 999)
                is_hit = actual_rank == 1
                payout = int(odds * bet_amount) if is_hit else 0

                result["bets"].append({
                    "type": "単勝",
                    "detail": str(horse_num),
                    "ev": round(ev, 3),
                    "prob": round(prob, 4),
                    "odds": odds,
                    "bet": bet_amount,
                    "is_hit": is_hit,
                    "payout": payout,
                })
                result["total_bet"] += bet_amount
                result["total_payout"] += payout

    # === 馬連シミュレーション ===
    if bet_type in ("umaren", "all"):
        # 上位5頭の組み合わせを検討
        top5 = df.nsmallest(5, "pred_rank")

        for (_, h1), (_, h2) in combinations(top5.iterrows(), 2):
            num1, num2 = int(h1["horse_number"]), int(h2["horse_number"])

            # 馬連確率
            umaren_prob = calculate_umaren_probability(probabilities, num1, num2, len(df))

            # オッズ推定（単勝オッズから推定）
            o1 = odds_data.get(num1, 10)
            o2 = odds_data.get(num2, 10)
            estimated_odds = (o1 * o2) / 3

            ev = umaren_prob * estimated_odds

            if ev >= umaren_ev_threshold:
                # 実際の結果を確認
                r1 = actual_results.get(num1, 999)
                r2 = actual_results.get(num2, 999)
                is_hit = (r1 <= 2 and r2 <= 2)
                payout = int(estimated_odds * bet_amount) if is_hit else 0

                result["bets"].append({
                    "type": "馬連",
                    "detail": f"{min(num1,num2)}-{max(num1,num2)}",
                    "ev": round(ev, 3),
                    "prob": round(umaren_prob, 4),
                    "odds": round(estimated_odds, 1),
                    "bet": bet_amount,
                    "is_hit": is_hit,
                    "payout": payout,
                })
                result["total_bet"] += bet_amount
                result["total_payout"] += payout

    return result


def main():
    parser = argparse.ArgumentParser(description="Expected Value Betting Simulation")
    parser.add_argument(
        "--version",
        type=str,
        default="v1",
        help="Model version (default: v1)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--ev-threshold",
        type=float,
        default=1.0,
        help="Expected value threshold for tansho (default: 1.0)",
    )
    parser.add_argument(
        "--umaren-ev-threshold",
        type=float,
        default=1.2,
        help="Expected value threshold for umaren (default: 1.2)",
    )
    parser.add_argument(
        "--bet-type",
        type=str,
        choices=["tansho", "umaren", "all"],
        default="all",
        help="Bet type to simulate (default: all)",
    )
    parser.add_argument(
        "--bet-amount",
        type=int,
        default=100,
        help="Bet amount per ticket (default: 100)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of races (default: 200)",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Show detailed bet results",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("期待値ベース馬券シミュレーション")
    print("=" * 70)
    print(f"モデルバージョン: {args.version}")
    print(f"期間: {args.start_date or '全期間'} ~ {args.end_date or '現在'}")
    print(f"賭け種別: {args.bet_type}")
    print(f"単勝EV閾値: {args.ev_threshold}")
    print(f"馬連EV閾値: {args.umaren_ev_threshold}")
    print(f"1点賭け金: {args.bet_amount}円")
    print("=" * 70)

    db = SessionLocal()

    try:
        # モデル読み込み
        print("\n[1/3] モデル読み込み...")
        predictor = get_model(args.version)

        if predictor.model is None:
            print("エラー: モデルが見つかりません。先にモデルを学習してください。")
            print("  実行: python ml/train.py")
            return 1

        print(f"  - モデルバージョン: {predictor.model_version}")
        print(f"  - 特徴量数: {len(predictor.feature_columns)}")

        # テストデータ取得
        print("\n[2/3] レースデータ読み込み...")
        stmt = (
            select(Race)
            .where(Race.entries.any(Entry.result.isnot(None)))
            .order_by(Race.date.desc())
            .limit(args.limit)
        )

        if args.start_date:
            start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
            stmt = stmt.where(Race.date >= start)

        if args.end_date:
            end = datetime.strptime(args.end_date, "%Y-%m-%d").date()
            stmt = stmt.where(Race.date <= end)

        races = list(db.execute(stmt).scalars().all())
        print(f"  - 対象レース数: {len(races)}")

        if not races:
            print("エラー: 対象レースがありません。")
            return 1

        # シミュレーション
        print("\n[3/3] シミュレーション実行中...")
        extractor = FeatureExtractor(db)
        results = []

        for i, race in enumerate(races):
            if (i + 1) % 50 == 0:
                print(f"  - {i + 1}/{len(races)} レース処理完了")

            result = simulate_race(
                db, predictor, extractor, race,
                ev_threshold=args.ev_threshold,
                umaren_ev_threshold=args.umaren_ev_threshold,
                bet_amount=args.bet_amount,
                bet_type=args.bet_type,
            )
            if result and result["bets"]:
                results.append(result)

        if not results:
            print("結果: 条件を満たす賭けがありませんでした。")
            print("  → EV閾値を下げてみてください")
            return 0

        # 集計
        total_bet = sum(r["total_bet"] for r in results)
        total_payout = sum(r["total_payout"] for r in results)
        total_bets_count = sum(len(r["bets"]) for r in results)
        total_hits = sum(1 for r in results for b in r["bets"] if b["is_hit"])

        roi = ((total_payout / total_bet) - 1) * 100 if total_bet > 0 else 0
        hit_rate = (total_hits / total_bets_count) * 100 if total_bets_count > 0 else 0

        # 馬券種別ごとの集計
        tansho_bets = [b for r in results for b in r["bets"] if b["type"] == "単勝"]
        umaren_bets = [b for r in results for b in r["bets"] if b["type"] == "馬連"]

        print("\n" + "=" * 70)
        print("シミュレーション結果")
        print("=" * 70)
        print(f"対象レース数: {len(results)}")
        print(f"総賭け数: {total_bets_count}点")
        print(f"的中数: {total_hits}点")
        print(f"的中率: {hit_rate:.1f}%")
        print()
        print(f"総投資額: {total_bet:,}円")
        print(f"総払戻額: {total_payout:,}円")
        print(f"収支: {total_payout - total_bet:+,}円")
        print(f"回収率: {100 * total_payout / total_bet if total_bet > 0 else 0:.1f}%")
        print(f"ROI: {roi:+.1f}%")
        print()

        # 馬券種別ごと
        if tansho_bets:
            t_bet = sum(b["bet"] for b in tansho_bets)
            t_pay = sum(b["payout"] for b in tansho_bets)
            t_hit = sum(1 for b in tansho_bets if b["is_hit"])
            print(f"[単勝]")
            print(f"  賭け数: {len(tansho_bets)}点, 的中: {t_hit}点 ({100*t_hit/len(tansho_bets):.1f}%)")
            print(f"  投資: {t_bet:,}円, 払戻: {t_pay:,}円, 回収率: {100*t_pay/t_bet if t_bet > 0 else 0:.1f}%")

        if umaren_bets:
            u_bet = sum(b["bet"] for b in umaren_bets)
            u_pay = sum(b["payout"] for b in umaren_bets)
            u_hit = sum(1 for b in umaren_bets if b["is_hit"])
            print(f"[馬連]")
            print(f"  賭け数: {len(umaren_bets)}点, 的中: {u_hit}点 ({100*u_hit/len(umaren_bets):.1f}%)")
            print(f"  投資: {u_bet:,}円, 払戻: {u_pay:,}円, 回収率: {100*u_pay/u_bet if u_bet > 0 else 0:.1f}%")

        # EV別分析
        print("\n[期待値帯別分析]")
        ev_ranges = [(1.0, 1.2), (1.2, 1.5), (1.5, 2.0), (2.0, 999)]
        all_bets = [b for r in results for b in r["bets"]]

        for ev_min, ev_max in ev_ranges:
            range_bets = [b for b in all_bets if ev_min <= b["ev"] < ev_max]
            if range_bets:
                r_bet = sum(b["bet"] for b in range_bets)
                r_pay = sum(b["payout"] for b in range_bets)
                r_hit = sum(1 for b in range_bets if b["is_hit"])
                label = f"EV {ev_min}~{ev_max}" if ev_max < 999 else f"EV {ev_min}+"
                print(f"  {label}: {len(range_bets)}点, 的中率 {100*r_hit/len(range_bets):.1f}%, 回収率 {100*r_pay/r_bet if r_bet > 0 else 0:.1f}%")

        # 詳細表示
        if args.detail:
            print("\n[的中レース詳細 (上位10件)]")
            hit_results = [r for r in results if any(b["is_hit"] for b in r["bets"])]
            for r in hit_results[:10]:
                hit_bets = [b for b in r["bets"] if b["is_hit"]]
                for b in hit_bets:
                    print(f"  {r['date']} {r['course']} {r['race_name']}")
                    print(f"    {b['type']} {b['detail']}: EV={b['ev']}, オッズ={b['odds']}, 払戻={b['payout']}円")

        print("\n" + "=" * 70)
        print("シミュレーション完了!")
        print("=" * 70)

        return 0

    except Exception as e:
        print(f"\nエラー: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
