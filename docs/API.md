# API設計書

## Base URL

```
http://localhost:8000/api/v1
```

---

## 1. レース関連 API

### GET /races
開催レース一覧を取得

**Query Parameters:**
| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| date | string | No | 開催日 (YYYY-MM-DD) |
| course | string | No | 競馬場名 |
| limit | int | No | 取得件数 (default: 50) |
| offset | int | No | オフセット (default: 0) |

**Response:**
```json
{
  "total": 36,
  "races": [
    {
      "race_id": "202405050811",
      "date": "2024-12-22",
      "course": "中山",
      "race_number": 11,
      "race_name": "有馬記念",
      "distance": 2500,
      "track_type": "芝",
      "grade": "G1",
      "post_time": "15:40"
    }
  ]
}
```

---

### GET /races/{race_id}
レース詳細を取得

**Path Parameters:**
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| race_id | string | レースID |

**Response:**
```json
{
  "race_id": "202405050811",
  "date": "2024-12-22",
  "course": "中山",
  "race_number": 11,
  "race_name": "有馬記念",
  "distance": 2500,
  "track_type": "芝",
  "weather": "晴",
  "condition": "良",
  "grade": "G1",
  "entries": [
    {
      "horse_number": 1,
      "frame_number": 1,
      "horse": {
        "horse_id": "2019104308",
        "name": "ドウデュース",
        "sex": "牡",
        "age": 5
      },
      "jockey": {
        "jockey_id": "01167",
        "name": "武豊"
      },
      "weight": 57.0,
      "odds": 3.5,
      "popularity": 1
    }
  ]
}
```

---

## 2. 予測関連 API

### POST /predictions
レースの予測を実行

**Request Body:**
```json
{
  "race_id": "202405050811"
}
```

**Response:**
```json
{
  "prediction_id": 123,
  "race_id": "202405050811",
  "model_version": "v1.0.0",
  "created_at": "2024-12-22T10:00:00",
  "predictions": [
    {
      "horse_number": 1,
      "horse_name": "ドウデュース",
      "score": 0.85,
      "predicted_rank": 1
    },
    {
      "horse_number": 5,
      "horse_name": "スターズオンアース",
      "score": 0.72,
      "predicted_rank": 2
    }
  ],
  "recommended_bets": [
    {
      "bet_type": "単勝",
      "target": "1",
      "confidence": "high"
    },
    {
      "bet_type": "馬連",
      "target": "1-5",
      "confidence": "medium"
    }
  ]
}
```

---

### GET /predictions/{race_id}
レースの予測結果を取得

**Path Parameters:**
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| race_id | string | レースID |

**Response:**
同上

---

## 3. 履歴関連 API

### GET /history
予想履歴一覧を取得

**Query Parameters:**
| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| from_date | string | No | 開始日 (YYYY-MM-DD) |
| to_date | string | No | 終了日 (YYYY-MM-DD) |
| limit | int | No | 取得件数 (default: 50) |
| offset | int | No | オフセット (default: 0) |

**Response:**
```json
{
  "total": 100,
  "summary": {
    "total_bets": 100,
    "total_hits": 32,
    "hit_rate": 0.32,
    "total_bet_amount": 100000,
    "total_payout": 125000,
    "roi": 1.25
  },
  "history": [
    {
      "id": 1,
      "race": {
        "race_id": "202405050811",
        "date": "2024-12-22",
        "race_name": "有馬記念"
      },
      "bet_type": "単勝",
      "bet_detail": "1",
      "bet_amount": 1000,
      "is_hit": true,
      "payout": 3500,
      "created_at": "2024-12-22T10:00:00"
    }
  ]
}
```

---

### POST /history
予想履歴を登録

**Request Body:**
```json
{
  "prediction_id": 123,
  "bet_type": "単勝",
  "bet_detail": "1",
  "bet_amount": 1000
}
```

**Response:**
```json
{
  "id": 1,
  "message": "History created successfully"
}
```

---

### PUT /history/{id}/result
予想結果を更新 (的中/不的中)

**Path Parameters:**
| パラメータ | 型 | 説明 |
|-----------|-----|------|
| id | int | 履歴ID |

**Request Body:**
```json
{
  "is_hit": true,
  "payout": 3500
}
```

---

## 4. データ管理 API

### POST /scrape/races
レースデータをスクレイピング

**Request Body:**
```json
{
  "date": "2024-12-22",
  "course": "中山"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Scraped 12 races",
  "races_count": 12
}
```

---

### GET /scrape/status
スクレイピング状況を取得

**Response:**
```json
{
  "last_updated": "2024-12-22T08:00:00",
  "total_races": 15000,
  "total_horses": 8000,
  "today_races": 36
}
```

---

## 5. 統計 API

### GET /stats/accuracy
予測精度の統計を取得

**Query Parameters:**
| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| period | string | No | 期間 (week/month/year/all) |

**Response:**
```json
{
  "period": "month",
  "accuracy": {
    "top1": 0.25,
    "top3": 0.65,
    "top5": 0.82
  },
  "by_grade": {
    "G1": {"top1": 0.30, "top3": 0.70},
    "G2": {"top1": 0.28, "top3": 0.68},
    "G3": {"top1": 0.26, "top3": 0.66}
  },
  "by_track": {
    "芝": {"top1": 0.27, "top3": 0.67},
    "ダート": {"top1": 0.23, "top3": 0.63}
  }
}
```

---

## 6. 一括データ更新 API

### POST /data/scrape/races
指定日のレース情報を一括スクレイピング

**Query Parameters:**
| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| target_date | string | Yes | 対象日 (YYYY-MM-DD) |
| skip_existing | bool | No | 既存レースをスキップ (default: true) |

**Response:**
```json
{
  "status": "success",
  "message": "Scraped races for 2024-12-22",
  "result": {
    "success_count": 12,
    "skipped_count": 0,
    "error_count": 0,
    "errors": [],
    "saved_items": ["202405050801", "202405050802"]
  }
}
```

---

### POST /data/scrape/results
指定日のレース結果を一括スクレイピング

**Query Parameters:**
| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| target_date | string | Yes | 対象日 (YYYY-MM-DD) |

---

### POST /data/scrape/training
指定日の全レースの調教データを一括スクレイピング

**Query Parameters:**
| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| target_date | string | Yes | 対象日 (YYYY-MM-DD) |

---

## 7. モデル管理 API

### POST /model/retrain
モデルの再学習を開始（バックグラウンド実行）

**Query Parameters:**
| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| min_date | string | No | 学習データの最小日付 (YYYY-MM-DD) |
| num_boost_round | int | No | ブースティング回数 (default: 1000) |
| early_stopping | int | No | 早期停止回数 (default: 50) |
| valid_fraction | float | No | 検証データ割合 (default: 0.2) |

**Response:**
```json
{
  "status": "success",
  "message": "Retraining started",
  "started_at": "2024-12-22T10:00:00"
}
```

---

### GET /model/status
再学習の状態を取得

**Response:**
```json
{
  "status": "success",
  "retraining_status": {
    "is_running": false,
    "started_at": null,
    "progress": "completed",
    "last_result": {
      "success": true,
      "model_version": "v20241222_100000",
      "train_rmse": 2.45,
      "valid_rmse": 2.68
    }
  }
}
```

---

### GET /model/versions
利用可能なモデルバージョン一覧を取得

**Response:**
```json
{
  "status": "success",
  "count": 3,
  "versions": [
    {
      "version": "v20241222_100000",
      "file_path": "/path/to/model_v20241222_100000.pkl",
      "size_bytes": 1234567,
      "created_at": "2024-12-22T10:00:00"
    }
  ]
}
```

---

### GET /model/current
現在使用中のモデル情報を取得

**Response:**
```json
{
  "status": "success",
  "model": {
    "version": "v1",
    "is_loaded": true,
    "num_features": 34,
    "best_iteration": 250
  }
}
```

---

### POST /model/switch
使用するモデルを切り替え

**Query Parameters:**
| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| version | string | Yes | 切り替え先のバージョン |

---

### GET /model/feature-importance
特徴量重要度を取得

**Query Parameters:**
| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| limit | int | No | 取得件数 (default: 20) |

**Response:**
```json
{
  "status": "success",
  "model_version": "v1",
  "features": [
    {"feature": "odds", "importance": 1250.5},
    {"feature": "popularity", "importance": 980.3}
  ]
}
```

---

## エラーレスポンス

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Race not found",
    "detail": "Race with id '202405050811' does not exist"
  }
}
```

| HTTPステータス | code | 説明 |
|---------------|------|------|
| 400 | BAD_REQUEST | リクエスト不正 |
| 404 | NOT_FOUND | リソースなし |
| 409 | CONFLICT | 再学習が既に実行中 |
| 500 | INTERNAL_ERROR | サーバーエラー |
| 503 | SERVICE_UNAVAILABLE | スクレイピング中など |
