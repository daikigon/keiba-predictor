# Keiba Predictor Backend

中央競馬予想アプリのバックエンドAPI

## 技術スタック

- **Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy 2.0
- **Migration**: Alembic
- **Scraping**: BeautifulSoup4 + Requests

## セットアップ

### 1. 前提条件

- Python 3.11+
- PostgreSQL 14+

### 2. 仮想環境の作成

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 4. 環境変数の設定

`.env` ファイルをbackendディレクトリに作成:

```bash
cp ../.env.example .env
```

`.env` を編集して環境に合わせて設定:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/keiba_db
DEBUG=true
```

### 5. データベースの作成

```bash
# PostgreSQLでデータベースを作成
createdb keiba_db
```

### 6. マイグレーションの実行

```bash
alembic upgrade head
```

## 開発サーバーの起動

```bash
# 開発モード
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# または
python -m app.main
```

## API ドキュメント

サーバー起動後、以下のURLでAPIドキュメントを確認できます:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API エンドポイント

### レース関連
| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/v1/races` | レース一覧取得 |
| GET | `/api/v1/races/{race_id}` | レース詳細取得 |
| POST | `/api/v1/races/scrape` | レースデータスクレイピング |
| POST | `/api/v1/races/scrape/{race_id}` | レース詳細スクレイピング |

### 予測関連
| Method | Endpoint | 説明 |
|--------|----------|------|
| POST | `/api/v1/predictions` | 予測を作成 |
| GET | `/api/v1/predictions/{race_id}` | 予測を取得 |

### 履歴関連
| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/v1/history` | 予想履歴一覧 |
| POST | `/api/v1/history` | 履歴を作成 |
| PUT | `/api/v1/history/{id}/result` | 結果を更新 |

### データ取得
| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/v1/data/horse/{horse_id}` | 馬情報取得 |
| GET | `/api/v1/data/jockey/{jockey_id}` | 騎手情報取得 |
| GET | `/api/v1/data/odds/{race_id}` | オッズ取得 |
| GET | `/api/v1/data/training/{race_id}` | 調教データ取得（スクレイピング） |
| GET | `/api/v1/data/training/{race_id}/db` | 調教データ取得（DB） |
| POST | `/api/v1/data/training/{race_id}/scrape` | 調教データをスクレイピングしてDB保存 |

### 統計
| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/v1/stats/accuracy` | 予測精度統計 |
| GET | `/api/v1/stats/scrape` | スクレイピング状況 |

## テストの実行

```bash
# 全テストを実行
pytest

# カバレッジ付きで実行
pytest --cov=app

# 特定のテストファイルを実行
pytest tests/test_models.py

# 詳細出力
pytest -v
```

## プロジェクト構造

```
backend/
├── alembic/              # マイグレーション
│   ├── versions/         # マイグレーションファイル
│   └── env.py
├── app/
│   ├── api/
│   │   ├── routes/       # APIエンドポイント
│   │   └── deps.py       # 依存関係
│   ├── db/
│   │   ├── base.py       # SQLAlchemy Base
│   │   └── session.py    # セッション管理
│   ├── models/           # SQLAlchemyモデル
│   ├── schemas/          # Pydanticスキーマ
│   ├── services/
│   │   ├── scraper/      # スクレイピング
│   │   └── predictor/    # 予測モデル
│   ├── config.py         # 設定
│   └── main.py           # アプリケーションエントリ
├── tests/                # テスト
├── ml/                   # 機械学習スクリプト
├── requirements.txt
├── alembic.ini
└── pyproject.toml
```

## 初期データ投入

```bash
# デモデータを作成
python scripts/init_data.py --demo

# 過去7日分のデータをスクレイピング
python scripts/init_data.py --days 7

# 期間指定でスクレイピング
python scripts/init_data.py --from 2024-12-01 --to 2024-12-22

# 調教データを除外してスクレイピング
python scripts/init_data.py --days 7 --no-training

# 特定日のレースをスクレイピング
python scripts/scrape_races.py --date 2024-12-22
```

## 開発コマンド

```bash
# コードフォーマット
black app tests

# Linting
ruff check app tests

# 型チェック
mypy app

# マイグレーション作成
alembic revision --autogenerate -m "description"

# マイグレーション適用
alembic upgrade head

# マイグレーションを1つ戻す
alembic downgrade -1
```

## スクレイピングの使用例

```python
from datetime import date
from app.services.scraper import RaceListScraper, RaceDetailScraper

# 日付のレース一覧を取得
list_scraper = RaceListScraper()
races = list_scraper.scrape(date(2024, 12, 22))

# レース詳細を取得
detail_scraper = RaceDetailScraper()
race_detail = detail_scraper.scrape("202406050811")
```

## データリセット

スクレイピングで取得したデータをクリアして、最初からやり直したい場合に使用します。

### コマンド

```bash
psql -U daikigon -d keiba_db -c "TRUNCATE entries, trainings, predictions, history, races, horses, jockeys CASCADE;"
```

### 解説

| 項目 | 説明 |
|------|------|
| `psql` | PostgreSQLのコマンドラインツール |
| `-U daikigon` | 接続するユーザー名（環境に合わせて変更） |
| `-d keiba_db` | 接続するデータベース名 |
| `-c "..."` | 実行するSQLコマンド |
| `TRUNCATE` | テーブルの全データを高速削除（DELETEより速い） |
| `CASCADE` | 外部キー制約のある関連データも一緒に削除 |

### 削除されるテーブル

| テーブル | 内容 |
|---------|------|
| `races` | レース情報 |
| `entries` | 出走馬情報（馬番、オッズ、着順など） |
| `horses` | 馬情報（血統、戦績など） |
| `jockeys` | 騎手情報 |
| `trainings` | 調教データ |
| `predictions` | AI予測結果 |
| `history` | 予想履歴・成績 |

### 確認方法

削除後、データが空になったか確認：

```bash
psql -U daikigon -d keiba_db -c "SELECT 'races' as table_name, COUNT(*) FROM races UNION ALL SELECT 'entries', COUNT(*) FROM entries UNION ALL SELECT 'horses', COUNT(*) FROM horses;"
```

### 注意

- **この操作は取り消せません** - 実行前に本当にリセットして良いか確認してください
- テーブル構造（スキーマ）は残ります。データのみ削除されます
- リセット後は再度スクレイピングでデータを取得してください

## 注意事項

- スクレイピングは1.5秒以上の間隔を空けて実行されます
- 取得データは個人利用の範囲内で使用してください
- netkeibaの利用規約を遵守してください
