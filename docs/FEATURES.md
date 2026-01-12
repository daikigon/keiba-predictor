# 特徴量設計書

## 1. 特徴量一覧

機械学習モデルに使用する特徴量の定義。現在のモデルは**97個の特徴量**を使用。

---

## 2. 馬の基本情報

| 特徴量名 | 型 | 説明 | 例 |
|---------|-----|------|-----|
| horse_age | int | 馬齢 | 4 |
| horse_sex | category | 性別 | 牡/牝/セ |
| weight | float | 斤量 | 57.0 |
| horse_weight | int | 馬体重 | 480 |
| weight_diff | int | 馬体重増減 | -4 |

---

## 3. レース条件

| 特徴量名 | 型 | 説明 | 例 |
|---------|-----|------|-----|
| distance | int | 距離 | 2000 |
| track_type | category | 芝/ダート | 芝 |
| course | category | 競馬場 | 東京 |
| condition | category | 馬場状態 | 良 |
| weather | category | 天候 | 晴 |
| grade | category | グレード | G1 |
| race_number | int | レース番号 | 11 |
| field_size | int | 出走頭数 | 16 |
| frame_number | int | 枠番 | 3 |
| horse_number | int | 馬番 | 5 |

---

## 4. 過去成績 (直近N走)

| 特徴量名 | 型 | 説明 |
|---------|-----|------|
| avg_rank_last3 | float | 直近3走平均着順 |
| avg_rank_last5 | float | 直近5走平均着順 |
| win_rate | float | 勝率 |
| place_rate | float | 連対率 |
| show_rate | float | 複勝率 |
| best_rank | int | 最高着順 |
| days_since_last | int | 前走からの日数 |
| last_result | int | 前走着順 |
| last_margin | float | 前走着差 (秒) |

---

## 5. コース適性

| 特徴量名 | 型 | 説明 |
|---------|-----|------|
| course_win_rate | float | 同コース勝率 |
| distance_win_rate | float | 同距離勝率 |
| track_win_rate | float | 同芝/ダート勝率 |
| condition_win_rate | float | 同馬場状態勝率 |

---

## 6. 騎手情報

| 特徴量名 | 型 | 説明 |
|---------|-----|------|
| jockey_win_rate | float | 騎手勝率 |
| jockey_place_rate | float | 騎手連対率 |
| jockey_course_win_rate | float | 騎手の同コース勝率 |
| jockey_horse_combo | float | 同馬との相性 (過去成績) |

---

## 7. 血統

| 特徴量名 | 型 | 説明 |
|---------|-----|------|
| father_id | category | 父馬ID (埋め込み用) |
| mother_father_id | category | 母父馬ID (埋め込み用) |
| father_distance_apt | float | 父系の距離適性スコア |
| father_track_apt | float | 父系の芝/ダート適性スコア |

---

## 8. オッズ・人気

| 特徴量名 | 型 | 説明 |
|---------|-----|------|
| odds | float | 単勝オッズ |
| popularity | int | 人気順 |
| odds_rank | int | オッズ順位 |

---

## 9. タイム関連

| 特徴量名 | 型 | 説明 |
|---------|-----|------|
| avg_last3f | float | 直近走の平均上がり3F |
| best_last3f | float | 最高上がり3F |
| avg_time_diff | float | 平均タイム差 (勝ち馬との差) |
| speed_index | float | スピード指数 (距離補正後) |

---

## 10. 脚質・走法特徴量 (新規追加)

corner_positionから算出する脚質関連の特徴量。

| 特徴量名 | 型 | 説明 |
|---------|-----|------|
| running_style | int | 脚質分類 (1:逃げ, 2:先行, 3:差し, 4:追込) |
| avg_first_corner_position | float | 平均1コーナー通過順位 |
| avg_final_corner_position | float | 平均最終コーナー通過順位 |
| position_change | float | 平均順位変動（最終-1コーナー） |
| front_rate | float | 前方レート（先行率） |
| is_front_runner | int | 逃げ馬フラグ |
| is_closer | int | 追込馬フラグ |
| position_consistency | float | 脚質の安定性 |

---

## 11. 季節特徴量 (新規追加)

レース日付から算出する季節関連の特徴量。

| 特徴量名 | 型 | 説明 |
|---------|-----|------|
| month | int | レース月 |
| quarter | int | 四半期 (1-4) |
| is_spring | int | 春フラグ (3-5月) |
| is_summer | int | 夏フラグ (6-8月) |
| is_autumn | int | 秋フラグ (9-11月) |
| is_winter | int | 冬フラグ (12-2月) |
| is_g1_season | int | G1シーズンフラグ (春秋) |
| day_of_week | int | 曜日 (0:月-6:日) |

---

## 12. ペース特徴量 (新規追加)

過去レースのペース情報から算出。

| 特徴量名 | 型 | 説明 |
|---------|-----|------|
| avg_pace | float | 平均ペース |
| slow_pace_win_rate | float | スローペース時の勝率 |
| fast_pace_win_rate | float | ハイペース時の勝率 |
| pace_adaptability | float | ペース適応力 |

---

## 13. 人気別パフォーマンス特徴量 (新規追加)

人気帯別の過去成績から算出。

| 特徴量名 | 型 | 説明 |
|---------|-----|------|
| low_pop_win_rate | float | 低人気時(6位以下)の勝率 |
| mid_pop_win_rate | float | 中人気時(3-5位)の勝率 |
| high_pop_win_rate | float | 高人気時(1-2位)の勝率 |
| pop_performance_ratio | float | 人気と着順の乖離度 |
| favorite_success_rate | float | 1番人気時の成功率 |
| upset_rate | float | 穴馬(6位以下)で3着以内率 |
| consistency_by_pop | float | 人気帯別成績の安定性 |
| overperform_rate | float | 人気を上回る率 |
| underperform_rate | float | 人気を下回る率 |
| avg_odds_when_win | float | 勝利時の平均オッズ |

---

## 14. 特徴量生成パイプライン

```python
# 処理フロー
1. 生データ取得 (DB)
   |
2. 欠損値処理
   - 数値: 中央値で補完
   - カテゴリ: "unknown" で補完
   |
3. 過去成績集計
   - 直近N走のwindow計算
   - キャッシュによる高速化 (preload_horse_history)
   |
4. 新規特徴量計算
   - 脚質特徴量 (corner_position)
   - 季節特徴量 (race_date)
   - ペース特徴量 (pace)
   - 人気別パフォーマンス (popularity, result)
   |
5. カテゴリ変数エンコーディング
   - LightGBM: そのまま (native support)
   - その他: Label Encoding / Target Encoding
   |
6. スケーリング (必要に応じて)
   - StandardScaler for NN
   |
7. 特徴量ベクトル生成
```

---

## 15. ターゲット変数の設計

### target_strategy パラメータ

| 値 | 説明 | 正例の定義 |
|----|------|-----------|
| 0 | 従来方式 | 1着のみ |
| 2 | タイム同着を含む (推奨) | 1着 + 1着と同タイムの馬 |

**target_strategy=2 の効果:**
- 僅差で負けた馬も正例として扱うことでモデルの学習能力を向上
- 正例サンプルが約20%増加
- 参考PDF「完成した競馬AIのソースコード + 使い方まとめ」で推奨される設定

---

## 16. 特徴量重要度 (参考)

モデル学習後に更新予定。

| 順位 | 特徴量 | 重要度 |
|------|--------|--------|
| 1 | - | - |
| 2 | - | - |
| 3 | - | - |

---

## 17. 注意事項

- リークに注意: レース結果に関連する情報は特徴量に含めない
- オッズは予測時点で取得可能な情報のみ使用
- 未来情報の混入を防ぐため、時系列での分割を徹底
- 過去成績の取得は `preload_horse_history()` でキャッシュを活用し高速化
