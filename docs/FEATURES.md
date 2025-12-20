# 特徴量設計書

## 1. 特徴量一覧

機械学習モデルに使用する特徴量の定義。

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

## 10. 調教情報

| 特徴量名 | 型 | 説明 |
|---------|-----|------|
| training_rank | category | 調教評価 (A/B/C) |
| training_time | float | 調教タイム |
| training_course | category | 調教コース |

---

## 11. 特徴量生成パイプライン

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
   |
4. カテゴリ変数エンコーディング
   - LightGBM: そのまま (native support)
   - その他: Label Encoding / Target Encoding
   |
5. スケーリング (必要に応じて)
   - StandardScaler for NN
   |
6. 特徴量ベクトル生成
```

---

## 12. 特徴量重要度 (参考)

モデル学習後に更新予定。

| 順位 | 特徴量 | 重要度 |
|------|--------|--------|
| 1 | - | - |
| 2 | - | - |
| 3 | - | - |

---

## 13. 注意事項

- リークに注意: レース結果に関連する情報は特徴量に含めない
- オッズは予測時点で取得可能な情報のみ使用
- 未来情報の混入を防ぐため、時系列での分割を徹底
