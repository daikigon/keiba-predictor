# 変更履歴 (CHANGELOG)

すべての重要な変更はこのファイルに記録されます。

## [Unreleased]

### Added (追加)

#### 特徴量エンジニアリング
- **脚質・走法特徴量** (8個): `corner_position`から脚質を推定
  - `running_style`: 脚質分類 (逃げ/先行/差し/追込)
  - `avg_first_corner_position`: 平均1コーナー通過順位
  - `avg_final_corner_position`: 平均最終コーナー通過順位
  - `position_change`: 順位変動
  - `front_rate`: 先行率
  - `is_front_runner`: 逃げ馬フラグ
  - `is_closer`: 追込馬フラグ
  - `position_consistency`: 脚質の安定性

- **季節特徴量** (8個): レース日付から季節性を抽出
  - `month`, `quarter`
  - `is_spring`, `is_summer`, `is_autumn`, `is_winter`
  - `is_g1_season`, `day_of_week`

- **ペース特徴量** (4個): 過去レースのペース情報
  - `avg_pace`: 平均ペース
  - `slow_pace_win_rate`, `fast_pace_win_rate`
  - `pace_adaptability`: ペース適応力

- **人気別パフォーマンス特徴量** (10個): 人気帯別の成績分析
  - `low_pop_win_rate`, `mid_pop_win_rate`, `high_pop_win_rate`
  - `pop_performance_ratio`: 人気と着順の乖離度
  - `favorite_success_rate`, `upset_rate`
  - `consistency_by_pop`
  - `overperform_rate`, `underperform_rate`
  - `avg_odds_when_win`

#### ターゲット変数の改善
- **target_strategy=2**: タイム同着馬を正例に含める機能
  - `finish_time`が1着と同じ馬を正例として扱う
  - 正例サンプルが約20%増加
  - 参考PDF推奨の設定をデフォルトに

#### 閾値スイープ分析
- **レース数表示**: 各閾値で賭けが発生したレース数を表示
  - 詳細テーブルに「レース数」列を追加
  - 最高回収率サマリにレース数を追加

### Fixed (修正)

- **閾値スイープ分析のEV上限バグ**: `ev_max`パラメータがフィルタリング上限として正しく機能するよう修正
  - 修正前: UIの「EV最大」はスイープ範囲のみに影響、フィルタリング上限は固定で10.0
  - 修正後: UIの「EV最大」がスイープ範囲とフィルタリング上限の両方に適用

### Changed (変更)

- **特徴量数**: 67個 → 97個に増加
- **デフォルトtarget_strategy**: 0 → 2（タイム同着を正例に含む）

### Performance (パフォーマンス改善)

- **馬の過去成績キャッシュ**: `preload_horse_history()`による一括取得
  - 学習時のDBクエリ数を大幅削減（約21万クエリ → 1クエリ）
  - 特徴量抽出時の性能向上

---

## [v1.0.0] - 2024-12-19

### Added
- 初期リリース
- netkeibaからのスクレイピング機能
- LightGBMによる予測モデル
- 期待値シミュレーション機能
- 閾値スイープ分析機能
- Supabase連携（DB/Storage）
- Next.jsフロントエンド

---

## バージョニング方針

このプロジェクトは [Semantic Versioning](https://semver.org/lang/ja/) に従います。

- **MAJOR**: 互換性のない変更
- **MINOR**: 後方互換性のある機能追加
- **PATCH**: 後方互換性のあるバグ修正
