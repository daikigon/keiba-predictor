# データベース設計書

## 1. ER図

```
+----------------+       +----------------+       +----------------+
|     races      |       |    entries     |       |     horses     |
+----------------+       +----------------+       +----------------+
| PK race_id     |<------| FK race_id     |------>| PK horse_id    |
|    date        |       | FK horse_id    |       |    name        |
|    course      |       | FK jockey_id   |       |    sex         |
|    race_number |       |    frame_num   |       |    birth_year  |
|    race_name   |       |    horse_num   |       |    father      |
|    distance    |       |    weight      |       |    mother      |
|    track_type  |       |    odds        |       |    trainer     |
|    weather     |       |    popularity  |       +----------------+
|    condition   |       |    result      |
|    grade       |       |    finish_time |       +----------------+
+----------------+       |    margin      |       |    jockeys     |
                         |    corner_pos  |       +----------------+
                         +----------------+       | PK jockey_id   |
                                |                 |    name        |
                                v                 |    win_rate    |
                         +----------------+       |    place_rate  |
                         |  past_results  |       +----------------+
                         +----------------+
                         | PK id          |
                         | FK horse_id    |
                         | FK race_id     |
                         |    result      |
                         |    time        |
                         +----------------+

+----------------+       +----------------+
|  predictions   |       |    features    |
+----------------+       +----------------+
| PK id          |       | PK id          |
| FK race_id     |       | FK entry_id    |
|    created_at  |       |    feature_json|
|    model_ver   |       |    created_at  |
|    results_json|       +----------------+
+----------------+

+----------------+
|    history     |
+----------------+
| PK id          |
| FK prediction_id|
|    bet_type    |
|    bet_amount  |
|    is_hit      |
|    payout      |
+----------------+
```

## 2. テーブル定義

### races (レース情報)

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| race_id | VARCHAR(20) | NO | PK, netkeiba race_id |
| date | DATE | NO | 開催日 |
| course | VARCHAR(10) | NO | 競馬場 (東京, 中山等) |
| race_number | INTEGER | NO | レース番号 (1-12) |
| race_name | VARCHAR(100) | YES | レース名 |
| distance | INTEGER | NO | 距離 (m) |
| track_type | VARCHAR(10) | NO | 芝/ダート |
| weather | VARCHAR(10) | YES | 天候 |
| condition | VARCHAR(10) | YES | 馬場状態 (良/稍重/重/不良) |
| grade | VARCHAR(10) | YES | グレード (G1, G2, G3, OP等) |
| created_at | TIMESTAMP | NO | 作成日時 |
| updated_at | TIMESTAMP | NO | 更新日時 |

### horses (馬情報)

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| horse_id | VARCHAR(20) | NO | PK, netkeiba horse_id |
| name | VARCHAR(50) | NO | 馬名 |
| sex | VARCHAR(5) | NO | 性別 (牡/牝/セ) |
| birth_year | INTEGER | NO | 生年 |
| father | VARCHAR(50) | YES | 父馬名 |
| mother | VARCHAR(50) | YES | 母馬名 |
| mother_father | VARCHAR(50) | YES | 母父馬名 |
| trainer | VARCHAR(50) | YES | 調教師名 |
| owner | VARCHAR(100) | YES | 馬主名 |
| created_at | TIMESTAMP | NO | 作成日時 |
| updated_at | TIMESTAMP | NO | 更新日時 |

### jockeys (騎手情報)

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| jockey_id | VARCHAR(20) | NO | PK, netkeiba jockey_id |
| name | VARCHAR(50) | NO | 騎手名 |
| win_rate | FLOAT | YES | 勝率 |
| place_rate | FLOAT | YES | 連対率 |
| show_rate | FLOAT | YES | 複勝率 |
| created_at | TIMESTAMP | NO | 作成日時 |
| updated_at | TIMESTAMP | NO | 更新日時 |

### entries (出走情報)

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | INTEGER | NO | PK, AUTO INCREMENT |
| race_id | VARCHAR(20) | NO | FK -> races |
| horse_id | VARCHAR(20) | NO | FK -> horses |
| jockey_id | VARCHAR(20) | YES | FK -> jockeys |
| frame_number | INTEGER | YES | 枠番 |
| horse_number | INTEGER | NO | 馬番 |
| weight | FLOAT | YES | 斤量 |
| horse_weight | INTEGER | YES | 馬体重 |
| weight_diff | INTEGER | YES | 馬体重増減 |
| odds | FLOAT | YES | 単勝オッズ |
| popularity | INTEGER | YES | 人気順 |
| result | INTEGER | YES | 着順 (レース後) |
| finish_time | VARCHAR(10) | YES | 走破タイム |
| margin | VARCHAR(20) | YES | 着差 |
| corner_position | VARCHAR(20) | YES | コーナー通過順 |
| last_3f | FLOAT | YES | 上がり3F |
| created_at | TIMESTAMP | NO | 作成日時 |
| updated_at | TIMESTAMP | NO | 更新日時 |

### predictions (予測結果)

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | INTEGER | NO | PK, AUTO INCREMENT |
| race_id | VARCHAR(20) | NO | FK -> races |
| model_version | VARCHAR(50) | NO | モデルバージョン |
| results_json | JSON | NO | 予測結果 (馬番: スコア) |
| created_at | TIMESTAMP | NO | 作成日時 |

### history (予想履歴)

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | INTEGER | NO | PK, AUTO INCREMENT |
| prediction_id | INTEGER | NO | FK -> predictions |
| bet_type | VARCHAR(20) | NO | 馬券種別 (単勝/複勝/馬連等) |
| bet_detail | VARCHAR(50) | NO | 買い目詳細 |
| bet_amount | INTEGER | YES | 賭け金 |
| is_hit | BOOLEAN | YES | 的中フラグ |
| payout | INTEGER | YES | 払戻金 |
| created_at | TIMESTAMP | NO | 作成日時 |

## 3. インデックス

```sql
-- races
CREATE INDEX idx_races_date ON races(date);
CREATE INDEX idx_races_course_date ON races(course, date);

-- entries
CREATE INDEX idx_entries_race_id ON entries(race_id);
CREATE INDEX idx_entries_horse_id ON entries(horse_id);

-- predictions
CREATE INDEX idx_predictions_race_id ON predictions(race_id);
CREATE INDEX idx_predictions_created_at ON predictions(created_at);
```

## 4. 開発ツール

| 用途 | ツール |
|------|--------|
| ORM | SQLAlchemy |
| マイグレーション | Alembic |
| DB確認・管理 | DBeaver |

---

## 5. データベース環境

### 5.1 ローカル開発環境

```
PostgreSQL (localhost:5432)
└── keiba_db
```

**設定:** `backend/.env`
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/keiba_db
```

**用途:**
- 開発・テスト
- スクレイピングによるデータ取得
- 一括補完処理
- モデル学習

### 5.2 本番環境 (Supabase)

```
Supabase (PostgreSQL)
├── Database: メインデータ
└── Storage: モデルファイル (.pkl)
```

**設定:** `frontend/.env.local`
```env
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

**用途:**
- 本番環境での読み取り
- Vercelからの直接接続

### 5.3 データ同期

現時点ではローカルDBとSupabaseのデータ同期機能は**未実装**です。

**運用方法:**
1. ローカル環境でスクレイピング・一括補完を実行
2. 必要に応じて手動でデータをエクスポート/インポート
3. 本番環境はSupabaseから読み取り

---

## 6. データ補完時のレコード作成

スクレイピングで取得した過去成績から、存在しないレコードを自動作成します。

### 6.1 作成されるレコード

| 条件 | 作成レコード |
|------|------------|
| race_idがracesテーブルに存在しない | 新規Raceレコード |
| horse_id + race_idの組み合わせがentriesに存在しない | 新規Entryレコード |
| jockey_idがjockeysテーブルに存在しない | 新規Jockeyレコード（名前空欄） |

### 6.2 注意事項

- 新規作成されたRaceは基本情報のみ（race_id, date, course, distance等）
- 詳細情報（天候、馬場状態等）は別途レース詳細スクレイピングが必要
- Jockeyは空の名前で作成後、騎手名更新バッチで補完可能
