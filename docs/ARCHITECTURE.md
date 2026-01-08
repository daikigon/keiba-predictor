# アーキテクチャ設計書

## 1. ディレクトリ構成

```
keiba-predictor/
├── backend/                    # Python バックエンド
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI エントリーポイント
│   │   ├── config.py          # 設定管理
│   │   ├── api/               # APIエンドポイント
│   │   │   ├── __init__.py
│   │   │   ├── routes/
│   │   │   │   ├── races.py
│   │   │   │   ├── predictions.py
│   │   │   │   └── history.py
│   │   │   └── deps.py        # 依存性注入
│   │   ├── models/            # SQLAlchemyモデル
│   │   │   ├── __init__.py
│   │   │   ├── race.py
│   │   │   ├── horse.py
│   │   │   ├── jockey.py
│   │   │   └── prediction.py
│   │   ├── schemas/           # Pydanticスキーマ
│   │   │   ├── __init__.py
│   │   │   ├── race.py
│   │   │   └── prediction.py
│   │   ├── services/          # ビジネスロジック
│   │   │   ├── __init__.py
│   │   │   ├── scraper/       # スクレイピング
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── race.py
│   │   │   │   ├── horse.py
│   │   │   │   └── odds.py
│   │   │   └── predictor/     # 予測ロジック
│   │   │       ├── __init__.py
│   │   │       ├── features.py
│   │   │       └── model.py
│   │   └── db/                # データベース
│   │       ├── __init__.py
│   │       ├── session.py
│   │       └── base.py
│   ├── ml/                    # 機械学習関連
│   │   ├── notebooks/         # Jupyter Notebook
│   │   ├── models/            # 学習済みモデル保存
│   │   ├── train.py           # 学習スクリプト
│   │   └── evaluate.py        # 評価スクリプト
│   ├── tests/
│   ├── alembic/               # マイグレーション
│   ├── pyproject.toml
│   └── requirements.txt
│
├── frontend/                   # Next.js フロントエンド
│   ├── src/
│   │   ├── app/               # App Router
│   │   │   ├── page.tsx       # ダッシュボード
│   │   │   ├── races/
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx
│   │   │   ├── history/
│   │   │   │   └── page.tsx
│   │   │   └── data/
│   │   │       └── page.tsx
│   │   ├── components/        # UIコンポーネント
│   │   │   ├── common/
│   │   │   ├── race/
│   │   │   └── prediction/
│   │   ├── lib/               # ユーティリティ
│   │   │   ├── api.ts         # APIクライアント
│   │   │   └── utils.ts
│   │   └── types/             # 型定義
│   ├── public/
│   ├── package.json
│   └── tsconfig.json
│
├── docs/                       # ドキュメント
│   ├── requirements.md
│   ├── TASKS.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   └── API.md
│
├── docker-compose.yml          # Docker設定
├── .env.example
├── .gitignore
└── README.md
```

## 2. システムフロー

### 2.1 データ取得フロー

```
[Scheduler/Manual Trigger]
         |
         v
    [Scraper Service]
         |
         +---> netkeiba (HTTP Request)
         |
         v
    [Data Parser]
         |
         v
    [Database Storage]
```

### 2.2 予測フロー

```
[User Request] ---> [Frontend]
                        |
                        v
                   [FastAPI]
                        |
         +--------------+--------------+
         |              |              |
         v              v              v
    [Get Race]   [Get Features]  [Load Model]
         |              |              |
         +--------------+--------------+
                        |
                        v
                  [Prediction]
                        |
                        v
                   [Response]
```

## 3. 技術選定理由

### バックエンド: FastAPI
- 非同期処理対応で高速
- 自動APIドキュメント生成
- Pydanticによる型安全性

### フロントエンド: Next.js
- SSR/SSGによる高速表示
- TypeScriptによる型安全性
- App Routerによるモダンな構成

### 機械学習: LightGBM
- 高速な学習・推論
- カテゴリ変数の直接扱い
- 特徴量重要度の可視化

### データベース: PostgreSQL
- 高機能で堅牢なRDBMS
- JSON型や全文検索など拡張機能が豊富
- 将来的な拡張性も確保

## 4. 外部連携

### netkeiba
- スクレイピング対象
- リクエスト間隔: 最低1秒以上
- User-Agent設定必須

---

## 5. 接続モード

フロントエンドは2つの接続モードをサポートしています。

### 5.1 ローカルバックエンドモード（開発環境）

```
[Frontend] ---> [FastAPI Backend] ---> [Local PostgreSQL]
```

**設定方法:** `frontend/.env.local`
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**特徴:**
- FastAPIバックエンドを経由して全機能が利用可能
- スクレイピング、一括補完など書き込み系機能が利用可能
- ローカルPostgreSQLにデータが保存される

### 5.2 Supabase直接接続モード（本番環境）

```
[Frontend] ---> [Supabase (PostgreSQL)]
```

**設定方法:** `frontend/.env.local`
```env
NEXT_PUBLIC_API_URL=
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

**特徴:**
- Vercelなど本番環境向け
- 読み取り専用（スクレイピング機能は利用不可）
- Supabaseに直接接続してデータを表示

### 5.3 モード判定ロジック

```typescript
// frontend/src/lib/api.ts
const useSupabase = !API_BASE_URL && isSupabaseConfigured;
```

- `API_BASE_URL`が設定されている場合: ローカルバックエンドモード
- `API_BASE_URL`が空かつSupabase設定がある場合: Supabase直接接続モード

### 5.4 データ管理ページの表示

データ管理ページ（`/data`）は実際にバックエンドへヘルスチェックを行い、動的に状態を表示します。

| バックエンド状態 | 表示 | スクレイピング |
|----------------|------|--------------|
| 稼働中 | 緑色「ローカルバックエンド接続中」 | 利用可能 |
| 停止中/未設定 | 黄色「Supabase直接接続モード」 | 利用不可 |

---

## 6. Supabase Storage

機械学習モデルファイル（.pkl）の保存にSupabase Storageを使用。

### 6.1 設定

```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your_service_key
SUPABASE_MODEL_BUCKET=models
```

### 6.2 機能

- モデルのアップロード・ダウンロード
- バージョン管理
- 署名付きURL生成（一時的なダウンロードリンク）

**注意:** データベース同期機能は未実装。ローカルDBとSupabaseのデータは別々に管理されます。
